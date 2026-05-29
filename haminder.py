import os
import sys
import math
import threading
import subprocess
import requests
import urllib3
from PIL import Image, ImageDraw
import pystray

# Optional .env file support — no error if python-dotenv isn't installed
try:
    # pyrefly: ignore [missing-import]
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import objc
from AppKit import NSWorkspace
from Foundation import NSObject


def _parse_env_file(filepath: str) -> dict[str, str]:
    """Parse a .env or env.sh file and return a dict of key-value pairs."""
    env_vars = {}
    if not os.path.isfile(filepath):
        return env_vars
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('export '):
                    line = line[7:].strip()
                if '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                env_vars[key] = val
    except Exception as e:
        print(f"Error reading env file {filepath}: {e}")
    return env_vars


def _load_robust_config() -> None:
    """Search for config files in various directories and load them into os.environ."""
    dirs_to_check = []
    
    # 1. Current working directory
    try:
        dirs_to_check.append(os.getcwd())
    except Exception:
        pass
        
    # 2. User's home directory
    home = os.path.expanduser('~')
    dirs_to_check.append(home)
    dirs_to_check.append(os.path.join(home, '.config', 'haminder'))
    
    # 3. Directory of the current script / executable and its parent directories up to root
    try:
        entry_file = __file__ if '__file__' in globals() else sys.argv[0]
        target = os.path.abspath(entry_file)
        curr = os.path.dirname(target)
        while curr and curr != os.path.dirname(curr):
            dirs_to_check.append(curr)
            curr = os.path.dirname(curr)
        if curr:
            dirs_to_check.append(curr)
    except Exception:
        pass

    # Unique list while preserving order
    seen = set()
    unique_dirs = []
    for d in dirs_to_check:
        if d and d not in seen:
            seen.add(d)
            unique_dirs.append(d)

    # Load from the first .env / env.sh files we find (or any of them to populate missing values)
    for d in unique_dirs:
        for filename in ('.env', 'env.sh'):
            filepath = os.path.join(d, filename)
            if os.path.isfile(filepath):
                for k, v in _parse_env_file(filepath).items():
                    if not os.environ.get(k):
                        os.environ[k] = v


# Suppress insecure request warnings since verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Robustly load config
_load_robust_config()

HA_HOST   = os.environ.get('HA_HOST')
HA_AUTH   = os.environ.get('HA_AUTH')
HA_LIGHT_ENTITY = os.environ.get('HA_LIGHT_ENTITY', os.environ.get('HA_ENTITY', 'light.tp_link_smart_bulb_1bb7'))
HA_FAN_ENTITY   = os.environ.get('HA_FAN_ENTITY', 'switch.marc_office_fan')


_missing = [v for v in ('HA_HOST', 'HA_AUTH') if not os.environ.get(v)]
if _missing:
    msg = (
        f"Required environment variable(s) not set: {', '.join(_missing)}.\n\n"
        "Please create a '.env' or 'env.sh' file with your HA_HOST and HA_AUTH "
        "and place it in your home directory (~/.env or ~/.haminder.env), in ~/.config/haminder/env, "
        "or in the repository root."
    )
    print(f"ERROR: {msg}", file=sys.stderr)
    try:
        # Escaping title and message for AppleScript
        escaped_title = "HA-Minder Configuration Error".replace('"', '\\"')
        escaped_msg = msg.replace('"', '\\"')
        script = f'display alert "{escaped_title}" message "{escaped_msg}" as critical buttons {{"OK"}} default button "OK"'
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception:
        pass
    sys.exit(1)


HA_ENTITY = HA_LIGHT_ENTITY

_ICON_SIZE = 64


def _make_icon(lit: bool) -> Image.Image:
    """
    Generate a 64×64 RGBA tray icon.
      lit=False → crescent moon  (light is off)
      lit=True  → glowing sun    (light is on)
    """
    size = _ICON_SIZE
    bg   = (30, 30, 46, 255)        # dark navy background
    img  = Image.new('RGBA', (size, size), bg)
    draw = ImageDraw.Draw(img)

    if lit:
        # Warm golden sun circle
        draw.ellipse([10, 10, 54, 54], fill=(255, 210, 30, 255))
        # Eight subtle rays
        cx = cy = size / 2
        for i in range(8):
            angle = math.radians(i * 45)
            x1 = cx + 30 * math.cos(angle)
            y1 = cy + 30 * math.sin(angle)
            x2 = cx + 30 * math.cos(angle)
            y2 = cy + 30 * math.sin(angle)
            # draw a short thick tick at each ray position
            draw.ellipse(
                [x1 - 3, y1 - 3, x1 + 3, y1 + 3],
                fill=(255, 235, 100, 255)
            )
    else:
        # Crescent moon: full lavender circle, then carve a bite with bg color
        draw.ellipse([ 8,  8, 56, 56], fill=(180, 180, 230, 255))
        draw.ellipse([20,  4, 60, 44], fill=bg)

    return img


class SleepWakeObserver(NSObject):
    def initWithApp_(self, app):
        self = objc.super(SleepWakeObserver, self).init()
        if self:
            self._app = app
            self._was_on_before_sleep = False
            
            nc = NSWorkspace.sharedWorkspace().notificationCenter()
            nc.addObserver_selector_name_object_(
                self,
                "receiveSleepNotification:",
                "NSWorkspaceWillSleepNotification",
                None
            )
            nc.addObserver_selector_name_object_(
                self,
                "receiveWakeNotification:",
                "NSWorkspaceDidWakeNotification",
                None
            )
        return self

    def receiveSleepNotification_(self, notification):
        with self._app._lock:
            was_on = self._app._light_on
        
        if was_on:
            self._was_on_before_sleep = True
            self._app._set_state(False)
            # Synchronously turn off the light so the request completes before sleep
            self._app.toggle_indicator(False)
        else:
            self._was_on_before_sleep = False

    def receiveWakeNotification_(self, notification):
        if self._was_on_before_sleep:
            self._app.start_minder()
            self._was_on_before_sleep = False


class HAMinderApp:
    def __init__(self):
        self._light_on = False
        self._fan_on   = False
        self._lock     = threading.Lock()

        self._headers = {
            'Authorization': f'Bearer {HA_AUTH}',
            'Content-Type':  'application/json',
        }

        menu = pystray.Menu(
            pystray.MenuItem(
                'Light On',
                self.start_minder,
                enabled=lambda item: not self._light_on,
            ),
            pystray.MenuItem(
                'Light Off',
                self.stop_minder,
                enabled=lambda item: self._light_on,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                'Fan On',
                self.turn_fan_on,
                enabled=lambda item: not self._fan_on,
            ),
            pystray.MenuItem(
                'Fan Off',
                self.turn_fan_off,
                enabled=lambda item: self._fan_on,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', self.quit_app),
        )


        self.icon = pystray.Icon(
            name='HA-Minder',
            icon=_make_icon(False),
            title='HA-Minder',
            menu=menu,
        )

        self._observer = SleepWakeObserver.alloc().initWithApp_(self)

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _set_state(self, lit: bool) -> None:
        """Update icon image and menu enabled-states atomically."""
        with self._lock:
            self._light_on = lit
        self.icon.icon = _make_icon(lit)
        self.icon.update_menu()

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def start_minder(self, icon=None, item=None) -> None:
        self._set_state(True)
        threading.Thread(
            target=self.toggle_indicator, args=(True,), daemon=True
        ).start()

    def stop_minder(self, icon=None, item=None) -> None:
        self._set_state(False)
        threading.Thread(
            target=self.toggle_indicator, args=(False,), daemon=True
        ).start()

    def turn_fan_on(self, icon=None, item=None) -> None:
        with self._lock:
            self._fan_on = True
        self.icon.update_menu()
        threading.Thread(
            target=self.toggle_device, args=(HA_FAN_ENTITY, True), daemon=True
        ).start()

    def turn_fan_off(self, icon=None, item=None) -> None:
        with self._lock:
            self._fan_on = False
        self.icon.update_menu()
        threading.Thread(
            target=self.toggle_device, args=(HA_FAN_ENTITY, False), daemon=True
        ).start()

    def quit_app(self, icon=None, item=None) -> None:
        """Turn light off synchronously, then stop the tray icon."""
        self.toggle_indicator(False)
        self.icon.stop()


    # ------------------------------------------------------------------
    # HA API
    # ------------------------------------------------------------------

    def toggle_device(self, entity_id: str, mode: bool) -> None:
        domain = entity_id.split('.')[0] if '.' in entity_id else 'homeassistant'
        service = 'turn_on' if mode else 'turn_off'
        url = f"{HA_HOST}/api/services/{domain}/{service}"
        payload = f'{{"entity_id": "{entity_id}"}}'
        try:
            response = requests.post(
                url, data=payload, headers=self._headers, verify=False
            )
            response.raise_for_status()
            print(f"Successfully toggled {entity_id} {'ON' if mode else 'OFF'}")
        except requests.exceptions.RequestException as e:
            print(f"Error toggling {entity_id}: {e}")

    def toggle_indicator(self, mode: bool = False) -> None:
        self.toggle_device(HA_LIGHT_ENTITY, mode)


    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        # Ensure light starts off, then hand control to the tray event loop
        threading.Thread(
            target=self.toggle_indicator, args=(False,), daemon=True
        ).start()
        self.icon.run()


if __name__ == '__main__':
    app = HAMinderApp()
    app.run()

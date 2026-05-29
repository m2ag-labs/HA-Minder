import os
import sys
import math
import threading
import subprocess
import time
import requests
import urllib3
from PIL import Image, ImageDraw, ImageFont, ImageChops

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


def _draw_propeller(
    angle_deg: float,
    blade_color: tuple[int, int, int, int] = (225, 225, 230, 255),
    hub_color: tuple[int, int, int, int] = (130, 130, 135, 255)
) -> Image.Image:
    """
    Generate a transparent 64x64 RGBA canvas with a centered,
    rotated 2-blade propeller and central hub.
    """
    size = _ICON_SIZE
    prop_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(prop_img)
    
    cx = cy = size / 2  # 32
    r_hub = 3.5
    L = 30  # blade length from center (max width)
    w = 3.5  # blade half-width
    
    # Left blade (rounded ellipse capsule)
    draw.ellipse([cx - L, cy - w, cx - r_hub, cy + w], fill=blade_color)
    # Right blade
    draw.ellipse([cx + r_hub, cy - w, cx + L, cy + w], fill=blade_color)
    # Central hub circle
    draw.ellipse([cx - r_hub, cy - r_hub, cx + r_hub, cy + r_hub], fill=hub_color)
    
    try:
        resample = Image.Resampling.BICUBIC
    except AttributeError:
        resample = Image.BICUBIC
        
    rotated = prop_img.rotate(-angle_deg, resample=resample)
    return rotated


def _draw_beach_scene(sway_angle_rad: float) -> Image.Image:
    """
    Draw a colorful, full 64x64 RGBA beach scene cropped inside a
    circular spyglass frame (with dark metallic outer barrel ring):
      - Sky-blue background with a glowing orange sun
      - Turquoise ocean
      - Golden sand island dune
      - Centered palm tree with curved trunk and palm leaves swaying dynamically
    """
    size = _ICON_SIZE
    # 1. First draw the raw beach scene on a temporary base image
    beach_base = Image.new('RGBA', (size, size), (135, 206, 235, 255))  # Sky blue background
    draw_beach = ImageDraw.Draw(beach_base)
    
    # Sunset/Orange Sun (x=12, y=12, radius=7)
    draw_beach.ellipse([5, 5, 19, 19], fill=(255, 120, 0, 255))
    
    # Turquoise/Cyan Ocean (y=36 to y=52)
    draw_beach.rectangle([0, 36, 64, 52], fill=(32, 178, 170, 255))
    
    # Golden Sand Island (drawn at bottom)
    draw_beach.ellipse([-10, 48, 74, 75], fill=(238, 214, 175, 255))
    
    # Swaying Palm Tree (Trunk base at (40, 52), height ~24 pixels)
    sway_offset = 6 * math.sin(sway_angle_rad)
    trunk_top_x = 40 + sway_offset
    trunk_top_y = 28
    
    # Draw curved trunk using quadratic Bezier interpolation
    steps = 10
    for i in range(steps + 1):
        t = i / steps
        bx = (1 - t)**2 * 40 + 2 * (1 - t) * t * (43 + sway_offset/2) + t**2 * trunk_top_x
        by = (1 - t)**2 * 52 + 2 * (1 - t) * t * 40 + t**2 * trunk_top_y
        r_trunk = 2.2 - 0.7 * t  # trunk tapers at top
        draw_beach.ellipse([bx - r_trunk, by - r_trunk, bx + r_trunk, by + r_trunk], fill=(120, 75, 45, 255))
        
    # Swaying Palm Leaves (curving outward from trunk top)
    leaf_color = (34, 139, 34, 255)
    leaf_angles = [-160, -120, -80, -40, 0]
    for angle_deg in leaf_angles:
        rad = math.radians(angle_deg + sway_offset * 1.5)
        leaf_steps = 8
        for j in range(1, leaf_steps + 1):
            lt = j / leaf_steps
            # Leaves curve downward under gravity
            lx = trunk_top_x + 12 * lt * math.cos(rad)
            ly = trunk_top_y + 12 * lt * math.sin(rad) + 4 * lt**2
            r_leaf = 1.8 * (1 - 0.7 * lt)
            draw_beach.ellipse([lx - r_leaf, ly - r_leaf, lx + r_leaf, ly + r_leaf], fill=leaf_color)
            
    # 2. Now apply the circular spyglass crop and metallic border
    spy_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))  # Transparent background
    
    # Create an anti-aliased circular mask of diameter 60 (from x=2 to x=61)
    mask_circle = Image.new('L', (size, size), 0)
    draw_mask = ImageDraw.Draw(mask_circle)
    draw_mask.ellipse([2, 2, 61, 61], fill=255)
    
    # Paste the beach scene using the circular mask
    spy_img.paste(beach_base, (0, 0), mask=mask_circle)
    
    # Draw a thin dark-steel metallic outer barrel ring
    draw_spy = ImageDraw.Draw(spy_img)
    draw_spy.ellipse([2, 2, 61, 61], outline=(45, 45, 55, 255), width=2)
    
    return spy_img








class SleepWakeObserver(NSObject):
    def initWithApp_(self, app):
        self = objc.super(SleepWakeObserver, self).init()
        if self:
            self._app = app
            self._was_on_before_sleep = False
            self._was_fan_on_before_sleep = False
            
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
            was_fan_on = self._app._fan_on
        
        if was_on:
            self._was_on_before_sleep = True
            self._app._set_state(False)
            # Synchronously turn off the light so the request completes before sleep
            self._app.toggle_indicator(False)
        else:
            self._was_on_before_sleep = False

        if was_fan_on:
            self._was_fan_on_before_sleep = True
            self._app._set_fan_state(False)
            # Synchronously turn off the fan so the request completes before sleep
            self._app.toggle_device(HA_FAN_ENTITY, False)
        else:
            self._was_fan_on_before_sleep = False

    def receiveWakeNotification_(self, notification):
        if self._was_on_before_sleep:
            self._app.start_minder()
            self._was_on_before_sleep = False

        if self._was_fan_on_before_sleep:
            self._app.turn_fan_on()
            self._was_fan_on_before_sleep = False



class HAMinderApp:
    def __init__(self):
        self._light_on = False
        self._fan_on   = False
        self._propeller_angle = 45.0
        self._away     = False
        self._sway_time = 0.0
        self._was_light_on_before_away = False
        self._was_fan_on_before_away = False
        self._lock     = threading.Lock()



        self._headers = {
            'Authorization': f'Bearer {HA_AUTH}',
            'Content-Type':  'application/json',
        }

        menu = pystray.Menu(
            pystray.MenuItem(
                'Light On',
                self.start_minder,
                enabled=lambda item: not self._light_on and not self._away,
            ),
            pystray.MenuItem(
                'Light Off',
                self.stop_minder,
                enabled=lambda item: self._light_on and not self._away,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                'Fan On',
                self.turn_fan_on,
                enabled=lambda item: not self._fan_on and not self._away,
            ),
            pystray.MenuItem(
                'Fan Off',
                self.turn_fan_off,
                enabled=lambda item: self._fan_on and not self._away,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Quit', self.quit_app),
        )


        self.icon = pystray.Icon(
            name='HA-Minder',
            icon=self._make_combined_icon(),
            title='HA-Minder',
            menu=menu,
        )

        self._observer = SleepWakeObserver.alloc().initWithApp_(self)



    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------

    def _make_combined_icon(self) -> Image.Image:
        """
        Generate a perfectly square 64×64 RGBA tray icon containing:
          - If Away: swaying palm tree beach scene
          - If At Desk: Moon/Sun status (Light) with superimposed propeller (Fan)
        """
        if self._away:
            return _draw_beach_scene(self._sway_time)
            
        base_img = _make_icon(self._light_on)
        
        if self._light_on:
            # We want: 
            # - Outer/default color (extends outside Sun): white (255, 255, 255, 255)
            # - Inner color (inside the Sun): dark blue (20, 35, 90, 255)
            
            # 1. Generate the base propeller in white
            prop_outer = _draw_propeller(self._propeller_angle, (255, 255, 255, 255), (255, 255, 255, 255))
            
            # 2. Create a mask representing the Sun circle (grows from 10 to 54)
            mask_inner = Image.new('L', (64, 64), 0)
            draw_mask = ImageDraw.Draw(mask_inner)
            draw_mask.ellipse([10, 10, 54, 54], fill=255)
            
            # 3. Intersect propeller transparency with the Sun circle mask
            prop_alpha = prop_outer.split()[3]
            composite_mask = ImageChops.multiply(prop_alpha, mask_inner)
            
            # 4. Paste dark blue onto the white propeller only inside the Sun bounds
            dark_blue_img = Image.new('RGBA', (64, 64), (20, 35, 90, 255))
            prop_outer.paste(dark_blue_img, (0, 0), mask=composite_mask)
            
            # 5. Redraw the central hub with a matching slate/dark hub color
            hub_mask = Image.new('L', (64, 64), 0)
            draw_hub = ImageDraw.Draw(hub_mask)
            draw_hub.ellipse([28, 28, 36, 36], fill=255)
            hub_color_img = Image.new('RGBA', (64, 64), (10, 20, 50, 255))
            prop_outer.paste(hub_color_img, (0, 0), mask=hub_mask)
            
            prop_img = prop_outer
        else:
            # Dark Navy Moon background -> Silver White propeller (max width)
            blade_color = (225, 225, 230, 255)
            hub_color = (130, 130, 135, 255)
            prop_img = _draw_propeller(self._propeller_angle, blade_color, hub_color)
            
        base_img.paste(prop_img, (0, 0), mask=prop_img)
        return base_img






    def _update_ui(self) -> None:
        """Re-draw the combined icon and refresh the menu bar status."""
        self.icon.icon = self._make_combined_icon()
        self.icon.update_menu()

    def _set_state(self, lit: bool) -> None:
        """Update light state and refresh the combined menu bar UI."""
        with self._lock:
            self._light_on = lit
        self._update_ui()

    def _set_fan_state(self, on: bool) -> None:
        """Update fan state and refresh the combined menu bar UI."""
        with self._lock:
            self._fan_on = on
        self._update_ui()


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

    def _animate_fan(self) -> None:
        """Increment propeller angle and update icon dynamically while the fan is ON."""
        while True:
            with self._lock:
                if not self._fan_on:
                    # Snap back to 45 degrees rest position
                    self._propeller_angle = 45.0
                    break
                # 20 degrees per 100ms creates a smooth, energetic spin
                self._propeller_angle = (self._propeller_angle + 20) % 360
            
            self.icon.icon = self._make_combined_icon()
            time.sleep(0.1)
        
        # Ensure we redraw the icon in its static horizontal rest state
        self.icon.icon = self._make_combined_icon()

    def turn_fan_on(self, icon=None, item=None) -> None:
        self._set_fan_state(True)
        threading.Thread(target=self._animate_fan, daemon=True).start()
        threading.Thread(
            target=self.toggle_device, args=(HA_FAN_ENTITY, True), daemon=True
        ).start()

    def turn_fan_off(self, icon=None, item=None) -> None:
        self._set_fan_state(False)
        threading.Thread(
            target=self.toggle_device, args=(HA_FAN_ENTITY, False), daemon=True
        ).start()

    def quit_app(self, icon=None, item=None) -> None:
        """Turn light and fan off synchronously, then stop the tray icon."""
        with self._lock:
            self._away = False
        self._set_fan_state(False)
        self.toggle_indicator(False)
        self.toggle_device(HA_FAN_ENTITY, False)
        self.icon.stop()

    def _animate_away(self) -> None:
        """Animate the swaying palm tree beach scene while the user is away."""
        while True:
            with self._lock:
                if not self._away:
                    break
                self._sway_time += 0.2  # Speed of the sway
                
            self.icon.icon = self._make_combined_icon()
            time.sleep(0.1)
        
        # Redraw standard icon on return
        self._update_ui()

    def _trigger_away_mode(self) -> None:
        print("Transitioning to AWAY mode (Unplugged)")
        with self._lock:
            # 1. Save states
            self._was_light_on_before_away = self._light_on
            self._was_fan_on_before_away = self._fan_on
            # 2. Turn off flags locally
            self._light_on = False
            self._fan_on = False
            self._away = True
            self._sway_time = 0.0
            
        # 3. Synchronously turn off HA devices so they shut down instantly
        self.toggle_indicator(False)
        self.toggle_device(HA_FAN_ENTITY, False)
        
        # 4. Start swaying animation background thread
        threading.Thread(target=self._animate_away, daemon=True).start()

    def _trigger_at_desk_mode(self) -> None:
        print("Transitioning to AT DESK mode (Plugged In)")
        with self._lock:
            self._away = False
            
        # 1. Redraw combined icon
        self._update_ui()
        
        # 2. Restore light state
        if getattr(self, '_was_light_on_before_away', False):
            self.start_minder()
            
        # 3. Restore fan state
        if getattr(self, '_was_fan_on_before_away', False):
            self.turn_fan_on()

    def _poll_battery(self) -> None:
        """Periodically check the power source and coordinate desk transition automations."""
        last_was_battery = False
        
        # Determine initial battery state to avoid redundant triggering on startup
        try:
            res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
            last_was_battery = "Battery Power" in res.stdout
            if last_was_battery:
                # If we start on battery, trigger away mode immediately
                self._trigger_away_mode()
        except Exception:
            pass
            
        while True:
            time.sleep(5.0)
            try:
                res = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
                current_is_battery = "Battery Power" in res.stdout
            except Exception:
                continue
                
            if current_is_battery != last_was_battery:
                last_was_battery = current_is_battery
                if current_is_battery:
                    self._trigger_away_mode()
                else:
                    self._trigger_at_desk_mode()






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
        # Ensure light and fan start off, then hand control to the tray event loop
        threading.Thread(
            target=self.toggle_indicator, args=(False,), daemon=True
        ).start()
        threading.Thread(
            target=self.toggle_device, args=(HA_FAN_ENTITY, False), daemon=True
        ).start()
        
        # Start the background battery polling thread
        threading.Thread(target=self._poll_battery, daemon=True).start()
        
        # Primary combined icon occupies the main Cocoa event loop
        self.icon.run()




if __name__ == '__main__':
    app = HAMinderApp()
    app.run()

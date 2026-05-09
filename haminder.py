import os
import sys
import math
import threading
import requests
import urllib3
from PIL import Image, ImageDraw
import pystray

# Optional .env file support — no error if python-dotenv isn't installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Suppress insecure request warnings since verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HA_HOST   = os.environ.get('HA_HOST')
HA_AUTH   = os.environ.get('HA_AUTH')
HA_ENTITY = os.environ.get('HA_ENTITY', 'light.tp_link_smart_bulb_1bb7')

_missing = [v for v in ('HA_HOST', 'HA_AUTH') if not os.environ.get(v)]
if _missing:
    sys.exit(f"ERROR: required environment variable(s) not set: {', '.join(_missing)}")

PAYLOAD = f'{{"entity_id": "{HA_ENTITY}"}}'
URL_ON  = f'{HA_HOST}/api/services/light/turn_on'
URL_OFF = f'{HA_HOST}/api/services/light/turn_off'

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


class HAMinderApp:
    def __init__(self):
        self._light_on = False
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
            pystray.MenuItem('Quit', self.quit_app),
        )

        self.icon = pystray.Icon(
            name='HA-Minder',
            icon=_make_icon(False),
            title='HA-Minder',
            menu=menu,
        )

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

    def quit_app(self, icon=None, item=None) -> None:
        """Turn light off synchronously, then stop the tray icon."""
        self.toggle_indicator(False)
        self.icon.stop()

    # ------------------------------------------------------------------
    # HA API
    # ------------------------------------------------------------------

    def toggle_indicator(self, mode: bool = False) -> None:
        url = URL_ON if mode else URL_OFF
        try:
            response = requests.post(
                url, data=PAYLOAD, headers=self._headers, verify=False
            )
            response.raise_for_status()
            print(f"Success: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error toggling light: {e}")

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

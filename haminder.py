import rumps
import requests
import threading
import urllib3

# Suppress insecure request warnings since verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

rumps.debug_mode(False)

HA_HOST = 'https://mnmhome.local:8123'
HA_AUTH = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJhN2ExMjk2ZjNkNDI0YTg5ODNhMDg0ZDYxNmNiYzM0MiIsImlhdCI6MTc3NzYwODk2NCwiZXhwIjoyMDkyOTY4OTY0fQ.pbUi4E3FKAot26C4P9hCdC6yzzeA7dN9LfoL_kdCLCs'
PAYLOAD = '{"entity_id": "light.tp_link_smart_bulb_1bb7"}'
URL_OFF = f'{HA_HOST}/api/services/light/turn_off'
URL_ON = f'{HA_HOST}/api/services/light/turn_on'


class HAMinderApp:
    def __init__(self):
        self.app = rumps.App("HA-Minder", "☾", quit_button=None)
        
        # Use requests.Session for connection pooling and default headers
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {HA_AUTH}',
            'Content-Type': 'application/json'
        })

        # Callbacks can reference the methods directly instead of using lambdas
        self.start_pause_button = rumps.MenuItem(title='Light On',
                                                 callback=self.start_minder)
        self.stop_button = rumps.MenuItem(title='Light Off',
                                          callback=None)

        self.quit_button = rumps.MenuItem(title='Quit', callback=self.quit_app)

        self.app.menu = [
            self.start_pause_button,
            None,
            self.stop_button,
            None,
            self.quit_button
        ]

    def run(self):
        self.toggle_indicator()
        self.app.run()

    def start_minder(self, _=None):
        self.stop_button.set_callback(self.stop_minder)
        self.start_pause_button.set_callback(None)
        self.app.title = "💡"
        threading.Thread(target=self.toggle_indicator, args=(True,), daemon=True).start()

    def stop_minder(self, _=None):
        self.app.title = "☾"
        self.stop_button.set_callback(None)
        self.start_pause_button.set_callback(self.start_minder)
        threading.Thread(target=self.toggle_indicator, daemon=True).start()

    def quit_app(self, _=None):
        """Turn off light synchronously then exit."""
        self.toggle_indicator(False)
        rumps.quit_application()

    def toggle_indicator(self, mode=False):
        url = URL_ON if mode else URL_OFF
        try:
            response = self.session.post(url, data=PAYLOAD, verify=False)
            response.raise_for_status()
            print(f"Success: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"Error toggling light: {e}")


if __name__ == '__main__':
    app = HAMinderApp()
    app.run()

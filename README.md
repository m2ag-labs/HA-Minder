# HA-Minder 🌙💡

A lightweight macOS menu bar app that controls a [Home Assistant](https://www.home-assistant.io/) smart light directly from the menu bar — no browser, no dashboard required.

---

## Overview

**HA-Minder** sits in your macOS menu bar and lets you turn a Home Assistant light on or off with a single click. It's designed to be minimal, always-available, and unobtrusive — perfect for a conference/status light, desk lamp, or any HA-controlled bulb you toggle frequently.

Key behaviours:
- **Light On** — turns the bulb on and updates the menu bar icon to 💡
- **Light Off** — turns the bulb off and restores the ☾ icon
- **Quit** — turns the light off automatically before the app exits
- API calls are made on a background thread so the UI stays responsive

---

## Requirements

| Requirement | Details |
|---|---|
| macOS | 11 (Big Sur) or later |
| Python | 3.10+ |
| [rumps](https://github.com/jaredks/rumps) | macOS menu bar framework |
| [requests](https://docs.python-requests.org/) | HTTP client for the HA API |
| Home Assistant | Instance reachable over the local network with a Long-Lived Access Token |

### Python dependencies

```
rumps
requests
```

Install into a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Edit the top of `haminder.py` to match your setup:

```python
HA_HOST   = 'https://<your-ha-host>:8123'
HA_AUTH   = '<your-long-lived-access-token>'
PAYLOAD   = '{"entity_id": "<your.light.entity_id>"}'
```

A Long-Lived Access Token can be created in Home Assistant under:  
**Profile → Long-Lived Access Tokens → Create Token**

---

## Running

```bash
source .venv/bin/activate
python haminder.py
```

---

## Building a macOS .app Bundle

[py2app](https://py2app.readthedocs.io/) is used to package the app. A convenience script handles everything:

```bash
./build.sh
```

The finished bundle is written to `dist/HA-Minder.app`. Copy it to `/Applications` or run it directly:

```bash
open dist/HA-Minder.app
```

> **Note:** Use `ditto` instead of `cp -r` when copying to `/Applications` to correctly preserve macOS framework symlinks:
> ```bash
> ditto dist/HA-Minder.app /Applications/HA-Minder.app
> ```

---

## Project Structure

```
haminder/
├── haminder.py       # Main application
├── setup.py          # py2app build configuration
├── build.sh          # Build script
├── requirements.txt  # Python dependencies
├── icon.icns         # App icon
└── .gitignore
```

---

## License

MIT

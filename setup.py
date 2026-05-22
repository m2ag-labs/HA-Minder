"""
py2app build configuration for HA-Minder.

Build:
    python setup.py py2app

Or use the provided build.sh helper script.
"""
from setuptools import setup

APP = ['haminder.py']
DATA_FILES = []

OPTIONS = {
    'argv_emulation': False,          # Must be False for menu-bar-only apps
    'iconfile': 'icon.icns',
    'plist': {
        'CFBundleName': 'HA-Minder',
        'CFBundleDisplayName': 'HA-Minder',
        'CFBundleIdentifier': 'com.haminder.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        # Hide from Dock — this is the critical key
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
    },
    'packages': ['pystray', 'PIL', 'requests', 'urllib3'],
}

setup(
    app=APP,
    name='HA-Minder',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

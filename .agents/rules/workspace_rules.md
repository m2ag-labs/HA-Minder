# HA-Minder Workspace Rules

These rules apply specifically to development work in the HA-Minder project.

## Architecture & Thread Safety
- **Cocoa Main Thread Safety:** pystray and Cocoa status items must only be modified and redrawn on the macOS main thread. Any modifications or UI updates initiated from background threads must be scheduled properly or thread-safe.
- **Non-blocking Daemons:** Ensure polling (every 5s), animation (every 100ms), and battery monitoring (every 5s) background threads use proper thread-locking and do not block the main Cocoa event loop.
- **Robust Exception Handling:** Background threads must catch errors (such as connection timeouts or DNS resolution failures when HA is offline) gracefully and log/indicate status without crashing the app.

## Configuration Management
- **Environment Discovery:** Do not hardcode URLs, tokens, or entity IDs. Utilize the multi-path environment config loader to fetch parameters from `.env`, `env.sh`, `env`, or `.haminder.env` starting from CWD and moving upwards to home/system config.
- **Credential Protection:** Never commit local `.env` or configuration files with actual tokens/passwords to git.

## Deployment & Packaging
- **Standalone App Testing:** When changes are made to drawing logic, package metadata, or system events, run `./build.sh` to package the app as `dist/HA-Minder.app` and test it locally.
- **Dock Icon Suppression:** Always preserve the `LSUIElement` key in plist configuration to ensure the application runs purely in the menu bar without showing in the Dock.

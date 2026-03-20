"""
Desktop entrypoint for packaging Sophia-Code with PyInstaller.

Runs the Flask app bound to localhost and opens the UI in the user's browser.
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser

from app import create_app


def main() -> None:
    # Keep it local-only for safety.
    host = "127.0.0.1"
    port = int(os.environ.get("SOPHIA_PORT", "5000"))

    # Disable auto-migrate in packaged desktop runs by default.
    os.environ.setdefault("AUTO_MIGRATE", "0")
    os.environ.setdefault("FLASK_DEBUG", "0")

    app = create_app()
    url = f"http://{host}:{port}/"

    def _open_browser() -> None:
        time.sleep(0.9)
        try:
            webbrowser.open(url, new=2, autoraise=True)
        except Exception:
            pass

    threading.Thread(target=_open_browser, daemon=True).start()

    # Werkzeug dev server is acceptable for a local desktop wrapper.
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()


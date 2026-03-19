from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _env_truthy(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    from app import create_app
    from app.utils.process_lock import single_instance_lock

    app = create_app()

    lock_path = os.environ.get("AUTO_MIGRATE_LOCK_PATH") or "/tmp/sophia-auto-migrate.lock"
    with single_instance_lock(lock_path) as acquired:
        if not acquired:
            print("Auto-migrate: lock not acquired, skipping.")
            return 0

        try:
            from flask_migrate import upgrade

            with app.app_context():
                print("Auto-migrate: running flask-migrate upgrade()...")
                upgrade()
                print("Auto-migrate: upgrade complete.")
        except Exception as e:
            print(f"Auto-migrate: failed: {e}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


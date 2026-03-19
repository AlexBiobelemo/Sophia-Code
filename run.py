# run.py

from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Snippet
import database_backup

load_dotenv() # Load environment variables from .env file

import os
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "0").strip() == "1"

app = create_app()

# Auto-migrate on startup (best-effort). Recommended for Render.
AUTO_MIGRATE = os.environ.get("AUTO_MIGRATE")
if AUTO_MIGRATE is None:
    AUTO_MIGRATE = "1" if os.environ.get("RENDER_EXTERNAL_URL") else "0"

if AUTO_MIGRATE.strip().lower() in {"1", "true", "yes", "on"}:
    try:
        from flask_migrate import upgrade
        from app.utils.process_lock import single_instance_lock

        lock_path = os.environ.get("AUTO_MIGRATE_LOCK_PATH") or "/tmp/sophia-auto-migrate.lock"
        with single_instance_lock(lock_path) as acquired:
            if acquired:
                with app.app_context():
                    upgrade()
    except Exception:
        pass

# Initialize backup system and run startup backup
backup_system = database_backup.init_backup_system()
backup_system.run_server_startup_backup()

@app.shell_context_processor
def make_shell_context():
    """Provides a shell context for 'flask shell' command."""
    return {'db': db, 'User': User, 'Snippet': Snippet}

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE, use_reloader=DEBUG_MODE)

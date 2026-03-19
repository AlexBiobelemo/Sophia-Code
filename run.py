# run.py

from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Snippet
import database_backup

load_dotenv() # Load environment variables from .env file

# Production mode (set to True for debugging)
DEBUG_MODE = True

app = create_app()

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

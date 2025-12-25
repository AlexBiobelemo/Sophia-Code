# run.py

from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Snippet, LeetcodeProblem, LeetcodeSolution
import database_backup

load_dotenv() # Load environment variables from .env file
app = create_app()

# Initialize backup system and run startup backup
backup_system = database_backup.init_backup_system()
backup_system.run_server_startup_backup()

@app.shell_context_processor
def make_shell_context():
    """Provides a shell context for 'flask shell' command."""
    return {'db': db, 'User': User, 'Snippet': Snippet, 'LeetcodeProblem': LeetcodeProblem, 'LeetcodeSolution': LeetcodeSolution}

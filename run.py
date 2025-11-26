# run.py

from dotenv import load_dotenv
from app import create_app, db
from app.models import User, Snippet, LeetcodeProblem, LeetcodeSolution

load_dotenv() # Load environment variables from .env file
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Provides a shell context for 'flask shell' command."""
    return {'db': db, 'User': User, 'Snippet': Snippet, 'LeetcodeProblem': LeetcodeProblem, 'LeetcodeSolution': LeetcodeSolution}

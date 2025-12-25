import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Set Flask configuration variables."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-super-secret-key-you-should-change'

    # This line was likely missing or incorrect
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY')

    POSTS_PER_PAGE = 10

    # Security settings for login
    LOGIN_ATTEMPTS_LIMIT = 5
    LOGIN_LOCKOUT_PERIOD_MINUTES = 30

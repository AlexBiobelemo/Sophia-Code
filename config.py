import os

basedir = os.path.abspath(os.path.dirname(__file__))

def _normalize_database_url(url: str) -> str:
    """
    Flask-SQLAlchemy uses SQLAlchemy's *synchronous* engine. If an async dialect
    is provided via env (e.g. sqlite+aiosqlite), SQLAlchemy will pick an async
    pool (AsyncAdaptedQueuePool) and crash at startup.
    """
    if not url:
        return url
    url = url.strip()

    # Common async dialects that should not be used with Flask-SQLAlchemy.
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("mysql+aiomysql://"):
        return url.replace("mysql+aiomysql://", "mysql+pymysql://", 1)
    return url


class Config:
    """Set Flask configuration variables."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-super-secret-key-you-should-change'

    _raw_db_url = os.environ.get('DATABASE_URL') or ('sqlite:///' + os.path.join(basedir, 'app.db'))
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(_raw_db_url)

    # Engine options: only apply sqlite-specific connect_args when using sqlite.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    if str(SQLALCHEMY_DATABASE_URI).startswith("sqlite:"):
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {'check_same_thread': False}

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    POSTS_PER_PAGE = 10

    # Security settings for login
    LOGIN_ATTEMPTS_LIMIT = 5
    LOGIN_LOCKOUT_PERIOD_MINUTES = 30

    # Maximum content length to prevent overly large requests (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Cookie/security defaults (can be overridden via env vars)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_SAMESITE = os.environ.get('REMEMBER_COOKIE_SAMESITE', 'Lax')

    # Prefer secure cookies in production (Render/Gunicorn), allow override for local dev.
    _secure_default = os.environ.get('FLASK_DEBUG', '0').strip() != '1'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '1' if _secure_default else '0').strip() == '1'
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', '1' if _secure_default else '0').strip() == '1'

    # CSRF hardening
    WTF_CSRF_TIME_LIMIT = 60 * 60  # 1 hour
    WTF_CSRF_SSL_STRICT = False  # set True when always behind HTTPS

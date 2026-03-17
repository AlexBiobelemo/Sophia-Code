# app/__init__.py

from flask import Flask, request, g

# Load environment variables from .env file before importing Config.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, continue without it
    pass

from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment # Import Flask-Moment
from flask_wtf.csrf import CSRFProtect
import sqlalchemy as sa # Import sqlalchemy
import time, uuid
import markdown


# CRITICAL FIX: Patch SQLAlchemy's SQLite dialect to use synchronous pysqlite
# This prevents the "No module named 'aiosqlite'" error in SQLAlchemy 2.0+
def _setup_synchronous_sqlite():
    """Force SQLAlchemy to use synchronous sqlite3 instead of async aiosqlite."""
    import sqlite3
    from sqlalchemy.dialects.sqlite import pysqlite
    from sqlalchemy.pool import QueuePool
    
    # Get the dialect registry
    from sqlalchemy.dialects import registry
    
    # Register pysqlite as the default 'sqlite' dialect
    # This must be done BEFORE any engine creation
    registry.register('sqlite', 'sqlalchemy.dialects.sqlite.pysqlite', 'dialect')
    registry.register('sqlite.pysqlite', 'sqlalchemy.dialects.sqlite.pysqlite', 'dialect')
    
    # Set pysqlite to use standard sqlite3 module
    pysqlite.dialect.dbapi = sqlite3
    pysqlite.dialect.is_async = False
    # Force use of synchronous pool
    pysqlite.dialect.poolclass = QueuePool
    
    # Also try to patch aiosqlite if it exists
    try:
        from sqlalchemy.dialects.sqlite import aiosqlite
        from sqlalchemy.pool import QueuePool
        
        # Override the import_dbapi static method to return sqlite3 instead of aiosqlite
        def _patched_import_dbapi():
            return sqlite3
        
        aiosqlite.dialect.import_dbapi = staticmethod(_patched_import_dbapi)
        aiosqlite.dialect.dbapi = sqlite3
        aiosqlite.dialect.is_async = False
        aiosqlite.dialect.poolclass = QueuePool
        
        # Re-register sqlite to point to pysqlite, not aiosqlite
        registry.register('sqlite', 'sqlalchemy.dialects.sqlite.pysqlite', 'dialect')
    except (ImportError, AttributeError) as e:
        pass  # aiosqlite not available, which is fine

# Apply the patch BEFORE initializing SQLAlchemy
_setup_synchronous_sqlite()

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login' # The route for the login page
login_manager.login_message_category = 'info' # Flash message category
moment = Moment() # Initialize Flask-Moment
csrf = CSRFProtect() # Initialize CSRFProtect

# Configure CSRF for API endpoints
csrf.exempt('app.routes.api_chat_new')
csrf.exempt('app.routes.api_chat_send')
csrf.exempt('app.routes.api_chat_stream')
csrf.exempt('app.routes.suggest_tags')
csrf.exempt('app.routes.format_code')
csrf.exempt('app.routes.refine')
csrf.exempt('app.routes.explain')
csrf.exempt('app.routes.api_chained_streaming_generation')
csrf.exempt('app.routes.api_save_streaming_result')
csrf.exempt('app.routes.save_streaming_as_snippet')


def create_app(config_class=Config):
    """Creates and configures an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure Flask session for better persistence
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    moment.init_app(app) # Initialize Flask-Moment
    csrf.init_app(app) # Initialize CSRFProtect

    with app.app_context():
        try:
            engine = db.get_engine(app)
        except (AttributeError, KeyError):
            engine = db.engine

        if not sa.inspect(engine).has_table('user'):
            app.logger.info('Creating missing database tables (fresh start).')
            db.create_all()

    # Register custom Jinja filters
    @app.template_filter('markdown_to_html')
    def markdown_to_html_filter(text):
        """Convert markdown text to HTML."""
        if not text:
            return ""
        # Convert markdown to HTML with safe extensions
        html = markdown.markdown(text, extensions=['extra', 'codehilite', 'fenced_code', 'nl2br'])
        return html

    @app.template_filter('markdown_preview')
    def markdown_preview_filter(text, length=200):
        """Convert markdown to HTML and create a safe preview."""
        if not text:
            return ""
        html = markdown.markdown(text, extensions=['extra', 'codehilite', 'fenced_code', 'nl2br'])
        
        # Remove HTML tags for length calculation, but keep the HTML for display
        import re
        text_only = re.sub('<[^<]+?>', '', html)
        
        if len(text_only) <= length:
            return html
        
        # Truncate text but preserve HTML structure by finding a safe break point
        truncated_text = text_only[:length].rsplit(' ', 1)[0] + '...'
        
        # Simple approach: just return first part of HTML and let it render
        # For a more sophisticated approach, you'd need HTML-aware truncation
        return html[:length*2] + '...'

    # Register blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Defaults for optional daily snapshots
    app.config.setdefault('AUTO_DAILY_SNAPSHOT', True)
    app.config.setdefault('SNAPSHOT_DIR', 'snapshots')

    # --- Security headers & request timing ---
    @app.before_request
    def _start_timer_and_request_id():
        g._start_time = time.perf_counter()
        g._request_id = str(uuid.uuid4())

    @app.after_request
    def _set_headers_and_log(response):
        # Security headers (minimal, CSP can be tuned if needed)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('X-XSS-Protection', '1; mode=block')
        # Lightweight CSP tuned for app assets; adjust as needed if blocking
        response.headers.setdefault('Content-Security-Policy', "default-src 'self' 'unsafe-inline' data: https:; script-src 'self' 'unsafe-inline' https:; style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https:;")

        # Request id and timing
        try:
            duration_ms = int((time.perf_counter() - getattr(g, '_start_time', time.perf_counter())) * 1000)
            response.headers['X-Request-ID'] = getattr(g, '_request_id', '')
            response.headers['X-Response-Time'] = f"{duration_ms}ms"
            app.logger.debug(f"{request.method} {request.path} [{response.status_code}] {duration_ms}ms req_id={getattr(g, '_request_id', '')}")
        except Exception:
            pass
        return response

    # Optional daily snapshot on first request per day per user - DISABLED due to async issues
    @app.before_request
    def _maybe_snapshot():
        # Snapshot feature disabled - causes greenlet/spawn errors with async SQLAlchemy
        pass
        # Original code commented out due to async/await compatibility issues
        # To re-enable, wrap in async-compatible context or run in background thread

    # Set user's preferred AI model for each request
    @app.before_request
    def _set_user_ai_preference():
        """Set the user's preferred AI model in Flask's g object for use in AI services."""
        try:
            from flask_login import current_user
            if current_user.is_authenticated and hasattr(current_user, 'preferred_ai_model'):
                g.user_preferred_model = current_user.preferred_ai_model
            else:
                # Default fallback
                g.user_preferred_model = 'gemini-2.5-flash'
        except Exception:
            # If anything fails, use default
            g.user_preferred_model = 'gemini-2.5-flash'

    # Import models here to ensure they are registered with the app
    from app import models

    # Add relationships for chat on User for convenience
    if not hasattr(models.User, 'chat_sessions'):
        models.User.chat_sessions = db.relationship('ChatSession', backref='user', lazy='dynamic')

    # Helper function for gamification
    def award_points(user, points, activity):
        from app.routes import check_and_award_badges # Import here to avoid circular dependency
        point_entry = models.Point(user_id=user.id, points=points, activity=activity)
        db.session.add(point_entry)
        db.session.commit()
        # Check for badges after awarding points
        check_and_award_badges(user)

    app.award_points = award_points

    return app

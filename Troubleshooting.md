# Troubleshooting Guide

## Table of Contents

- [Common Issues](#common-issues)
  - [Installation Issues](#installation-issues)
  - [Database Issues](#database-issues)
  - [Login/Authentication Issues](#loginauthentication-issues)
  - [AI Feature Issues](#ai-feature-issues)
  - [UI/Frontend Issues](#uifrontend-issues)
- [Error Messages](#error-messages)
- [Performance Issues](#performance-issues)
- [Backup & Recovery](#backup--recovery)
- [Getting Help](#getting-help)

## Common Issues

### Installation Issues

#### Problem: `ModuleNotFoundError: No module named 'flask'`

**Cause:** Dependencies not installed or virtual environment not activated.

**Solution:**
```bash
# Activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

#### Problem: `sqlite3.OperationalError: unable to open database file`

**Cause:** Database file permissions or path issues.

**Solution:**
1. Ensure the `instance` folder exists and is writable
2. Check that your user has write permissions to the project directory
3. On Windows, run as administrator if needed

#### Problem: `ImportError: No module named 'aiosqlite'`

**Cause:** SQLAlchemy trying to use async dialect.

**Solution:** This is automatically handled by the application. If you see this error:
1. Check your `DATABASE_URL` environment variable
2. Ensure it uses `sqlite:///` not `sqlite+aiosqlite://`
3. The app automatically normalizes this, but manual overrides can cause issues

### Database Issues

#### Problem: `sqlalchemy.exc.OperationalError: database is locked`

**Cause:** Another process is accessing the database file.

**Solution:**
1. Close any other instances of the application
2. Close database viewers (DB Browser, etc.)
3. Restart the Flask server
4. If persistent, check for zombie Python processes

#### Problem: Database tables missing after fresh install

**Cause:** Migrations not run.

**Solution:**
```bash
# Run migrations
flask db upgrade

# If that fails, create fresh tables
python -c "from app import create_app, db; app = create_app(); with app.app_context(): db.create_all()"
```

#### Problem: `sqlite3.DatabaseError: disk I/O error`

**Cause:** Corrupted database or disk space issues.

**Solution:**
1. Check available disk space
2. Restore from backup:
   ```bash
   python database_backup.py list
   python database_backup.py restore backup_YYYYMMDD_HHMMSS.db
   ```
3. If no backup exists, try database integrity check:
   ```bash
   sqlite3 app.db "PRAGMA integrity_check;"
   ```

### Login/Authentication Issues

#### Problem: Account locked after failed login attempts

**Cause:** Security feature - 5 failed attempts triggers 30-minute lockout.

**Solution:**
1. Wait 30 minutes for automatic unlock
2. If you have database access, manually reset:
   ```python
   from app import create_app, db
   from app.models import User
   app = create_app()
   with app.app_context():
       user = User.query.filter_by(username='your_username').first()
       user.failed_login_attempts = 0
       user.locked_until = None
       db.session.commit()
   ```

#### Problem: "Remember Me" not working

**Cause:** Cookie settings or browser configuration.

**Solution:**
1. Ensure cookies are enabled in your browser
2. Check that `SECRET_KEY` is set in environment variables
3. For production, ensure HTTPS is enabled (cookies may require secure context)

#### Problem: Session expires too quickly

**Cause:** Default session timeout is 1 hour.

**Solution:** Modify in `app/__init__.py`:
```python
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # Change to desired seconds
```

### AI Feature Issues

#### Problem: `Error: GEMINI_API_KEY is not configured`

**Cause:** API key not set.

**Solution:**
1. Set environment variable:
   ```bash
   # Windows
   set GEMINI_API_KEY=your_api_key_here
   
   # macOS/Linux
   export GEMINI_API_KEY=your_api_key_here
   ```
2. Or save in `.env` file:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
3. Or configure in User Settings → BYOK (Bring Your Own Key)

#### Problem: AI generation times out

**Cause:** Large input or slow API response.

**Solution:**
1. Reduce input size (split into smaller prompts)
2. Check internet connection
3. Verify API key has quota remaining
4. Increase timeout in `config.py`:
   ```python
   AI_REQUEST_TIMEOUT_SECONDS = 600  # Increase from default 300
   ```

#### Problem: AI returns incomplete code

**Cause:** Response exceeded token limits.

**Solution:**
1. The app automatically handles this with chunking
2. Look for `[Note: Response may be incomplete due to length limits]`
3. Try breaking request into smaller parts
4. Use multi-step generation for complex tasks

#### Problem: "Input blocked by API" error

**Cause:** Content flagged by safety filters.

**Solution:**
1. Rephrase your prompt
2. Avoid potentially sensitive topics
3. The app has safety settings set to BLOCK_NONE, but Google may still filter

### UI/Frontend Issues

#### Problem: Dark mode not persisting

**Cause:** Browser cache or cookies cleared.

**Solution:**
1. Check that cookies are enabled
2. Re-select dark mode in User Settings
3. Clear browser cache and reload

#### Problem: Tooltips not appearing

**Cause:** Tooltip system disabled or JavaScript error.

**Solution:**
1. Enable in User Settings → Enable Tooltips
2. Check browser console for JavaScript errors
3. Clear browser cache
4. Disable browser extensions that might interfere

#### Problem: Code syntax highlighting not working

**Cause:** Missing CSS/JS assets or unsupported language.

**Solution:**
1. Hard refresh page (Ctrl+F5 / Cmd+Shift+R)
2. Check browser console for 404 errors on static files
3. Ensure language is in the supported list in `forms.py`

## Error Messages

### "Page Not Found (404)"

**Cause:** Route doesn't exist or bookmark is outdated.

**Solution:** Navigate from homepage or clear browser cache.

### "Internal Server Error (500)"

**Cause:** Unhandled exception in application.

**Solution:**
1. Check application logs:
   ```bash
   # If running with gunicorn
   journalctl -u sophia
   
   # If running with flask run, check terminal output
   ```
2. Enable debug mode for more details:
   ```bash
   set FLASK_DEBUG=1  # Windows
   export FLASK_DEBUG=1  # macOS/Linux
   ```
3. Report bug with stack trace on GitHub

### "CSRF token missing"

**Cause:** Form submission without CSRF token.

**Solution:**
1. Refresh the page and try again
2. Ensure cookies are enabled
3. Check that `WTF_CSRF_ENABLED` is True in config

### "Request Entity Too Large (413)"

**Cause:** File or code exceeds 16MB limit.

**Solution:**
1. Reduce file size
2. Split large code into multiple snippets
3. Increase limit in `config.py` (not recommended):
   ```python
   MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
   ```

## Performance Issues

### Slow page loads

**Possible causes and solutions:**

1. **Large number of snippets:**
   - Use pagination (enabled by default, 20 per page)
   - Use filters to narrow results
   - Export and archive old snippets

2. **Slow AI responses:**
   - Use faster model (gemini-2.5-flash-lite)
   - Check internet connection
   - Use shorter prompts

3. **Database queries slow:**
   - Ensure indexes exist (automatic with migrations)
   - Consider upgrading to PostgreSQL for large datasets

### High CPU usage during AI streaming

**Cause:** Real-time DOM updates during streaming.

**Solution:**
1. Disable animations in User Settings
2. The app uses requestAnimationFrame optimization
3. Close other browser tabs

## Backup & Recovery

### How to restore from backup

```bash
# List available backups
python database_backup.py list

# Restore specific backup
python database_backup.py restore backup_YYYYMMDD_HHMMSS.db
```

### Automatic backups not running

**Cause:** Backup system not initialized.

**Solution:**
1. Check that `database_backup.py` is imported in `run.py`
2. Verify backup directory exists and is writable
3. Check console output for backup messages

### Export snippets before major changes

Navigate to **Export** page and download all snippets as Markdown or ZIP.

## Getting Help

### In-App Help

- **User Profile** → Help & Tips section
- **Help** page with categorized guides:
  - Quick Start Guide
  - Search Tips
  - AI Features
  - Keyboard Shortcuts
  - Points & Badges

### Documentation

- [User Guide](User%20Guide.md) - Complete user manual
- [Developer Guide](Developer%20Guide.md) - Technical documentation
- [Features](Features.md) - Feature descriptions
- [README](README.md) - Installation and overview

### External Resources

- **GitHub Issues:** Report bugs and request features
- **Flask Documentation:** https://flask.palletsprojects.com/
- **SQLAlchemy Documentation:** https://docs.sqlalchemy.org/
- **Google Gemini API:** https://ai.google.dev/docs

### Contact

For support issues not covered here:
1. Check existing GitHub issues
2. Create new issue with detailed description
3. Include environment information:
   - Python version
   - Operating system
   - Browser (if UI issue)
   - Steps to reproduce

## Debug Mode

For development and troubleshooting, enable debug mode:

```bash
# Windows
set FLASK_DEBUG=1
set FLASK_ENV=development

# macOS/Linux
export FLASK_DEBUG=1
export FLASK_ENV=development

# Run the app
python run.py
```

**Warning:** Never run in debug mode in production!

## Logs

Application logs appear in:
- Terminal/console where Flask is running
- `logs/` directory (if configured)
- Render/Heroku logs (if deployed)

To increase log verbosity, modify `app/__init__.py`:
```python
app.logger.setLevel(logging.DEBUG)
```

# Troubleshooting Guide

This guide covers common issues and their solutions for Project Sophia.

## Installation Issues

### Python Version Not Supported

**Error:** `Python 3.9+ is required`

**Solution:**
1. Check your Python version:
   ```bash
   python --version
   ```
2. If version is below 3.9, install a newer version from [python.org](https://www.python.org/downloads/)
3. On Windows, check "Add Python to PATH" during installation
4. Restart your terminal after installation

### pip Install Fails

**Error:** `Could not find a version that satisfies the requirement` or installation errors

**Solutions:**
1. Upgrade pip:
   ```bash
   pip install --upgrade pip
   ```
2. Clear pip cache:
   ```bash
   pip cache purge
   ```
3. Install packages individually:
   ```bash
   pip install Flask Flask-Login Flask-SQLAlchemy
   ```
4. Check for conflicting packages in your environment
5. Create a fresh virtual environment

### Virtual Environment Issues

**Error:** `venv` command not found or activation fails

**Solutions:**
1. Create virtual environment with `python -m venv venv` instead of `virtualenv venv`
2. On Windows, use PowerShell or Command Prompt as Administrator
3. On macOS/Linux, ensure virtualenv is installed: `pip install virtualenv`
4. Check that your terminal supports the script type (.ps1 for PowerShell, .sh for bash)

### Database Migration Errors

**Error:** `alembic.util.exc.CommandError: Can't locate revision identified by`

**Solutions:**
1. Initialize the database:
   ```bash
   flask db upgrade
   ```
2. If migrations are missing, create initial migration:
   ```bash
   flask db migrate -m "initial migration"
   flask db upgrade
   ```
3. Reset the database (warning: deletes all data):
   ```bash
   rm app.db
   flask db init
   flask db migrate -m "initial"
   flask db upgrade
   ```

### Badge System Not Initialized

**Error:** Badges not appearing or badge errors

**Solutions:**
1. Initialize badges manually:
   ```bash
   python -c "from app.badge_system import initialize_default_badges; from app import create_app, db; app = create_app(); with app.app_context(): initialize_default_badges()"
   ```

## Configuration Issues

### Missing API Key Errors

**Error:** `GEMINI_API_KEY is not configured` or `Error: Could not generate code`

**Solutions:**
1. Create a `.env` file in the project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
2. Get an API key from [Google AI Studio](https://aistudio.google.com/)
3. Restart the application after adding the API key
4. For Minimax features, also add:
   ```
   MINIMAX_API_KEY=your_minimax_api_key_here
   ```

### Environment Variables Not Loading

**Error:** Configuration values not recognized

**Solutions:**
1. Install python-dotenv: `pip install python-dotenv`
2. Ensure `.env` file is in the project root directory
3. Check for syntax errors in `.env` file (no quotes, no spaces around `=`)
4. Restart the Flask server after changes
5. Verify environment variables are loaded:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   import os
   print(os.environ.get('GEMINI_API_KEY'))
   ```

### Secret Key Warning

**Error:** Warning about default secret key

**Solutions:**
1. Generate a strong secret key:
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```
2. Add to your `.env` file:
   ```
   SECRET_KEY=your_generated_secret_key
   ```

## Authentication Issues

### Login Failed After Account Lockout

**Error:** `Account locked. Please try again in X minutes.`

**Solution:**
1. Wait for the lockout period to expire (30 minutes by default)
2. If urgent, manually reset the lockout in the database:
   ```python
   from app import create_app, db
   from app.models import User
   app = create_app()
   with app.app_context():
       user = User.query.filter_by(username='your_username').first()
       user.locked_until = None
       user.failed_login_attempts = 0
       db.session.commit()
   ```

### Session Not Persisting

**Error:** Logged out immediately or session lost

**Solutions:**
1. Check browser cookies are enabled
2. Clear browser cache and cookies
3. Try incognito/private browsing mode
4. Check `PERMANENT_SESSION_LIFETIME` setting (default: 1 hour)

### Password Reset Not Working

**Error:** Can't reset password

**Solution:**
Password reset via email is not implemented. Contact database administrator to reset password manually:
```python
from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    user = User.query.filter_by(username='your_username').first()
    user.set_password('new_password')
    db.session.commit()
```

## AI Feature Issues

### AI Generation Timeout

**Error:** `Error: Operation timed out` or no response

**Solutions:**
1. Check your internet connection
2. Reduce the complexity of your prompt
3. Try again (transient errors are common)
4. Check API status at Google AI status page
5. Switch to a different AI model in User Settings
6. Increase timeout in config (if applicable)

### Poor Quality AI Results

**Error:** Generated code is incorrect or low quality

**Solutions:**
1. Be more specific in your prompt
2. Provide examples of desired output
3. Try the Multi-Step Thinking feature for complex problems
4. Use the Refine feature to fix errors
5. Try a different AI model
6. Break down complex requests into smaller parts

### AI Service Unavailable

**Error:** `Error: Could not generate code. Service unavailable`

**Solutions:**
1. Check if API keys are valid and have quota remaining
2. Try the fallback model (gemini-1.5-flash)
3. Wait and retry later
4. Check API provider status pages
5. Switch to Minimax if Gemini is unavailable

### Embedding Generation Failed

**Error:** `embedding generation failed` in logs

**Solutions:**
1. This is a warning, not an error—snippet is still saved
2. Check GEMINI_API_KEY is valid
3. Semantic search will use keyword-only mode
4. Restart the application if issue persists

## Database Issues

### Database Locked

**Error:** `database is locked` or concurrent access errors

**Solutions:**
1. Close other connections to the database
2. Restart the Flask server
3. On Windows, ensure no other process is using the file
4. Use SQLite in memory for development (not recommended for production)

### Data Not Saving

**Error:** Changes not persisted or lost on restart

**Solutions:**
1. Check `db.session.commit()` is called after changes
2. Ensure `app.db` file is writable
3. Check disk space is available
4. Verify database is not in memory mode

### Corrupted Database

**Error:** `database disk image is malformed` or data corruption

**Solutions:**
1. Restore from backup:
   ```bash
   cp backup/backup_*.db app.db
   ```
2. If no backup, try SQLite integrity check:
   ```python
   import sqlite3
   conn = sqlite3.connect('app.db')
   conn.execute('PRAGMA integrity_check')
   ```
3. Dump and restore:
   ```bash
   sqlite3 app.db .dump > backup.sql
   sqlite3 new_app.db < backup.sql
   ```

## UI/Display Issues

### Page Not Loading

**Error:** Blank page, 404, or 500 error

**Solutions:**
1. Check Flask is running (`flask run`)
2. Check the correct port (default 5000)
3. Clear browser cache
4. Check browser console for JavaScript errors
5. View Flask logs for server-side errors

### CSS/Styles Not Loading

**Error:** Unstyled pages or missing styles

**Solutions:**
1. Check static files are being served
2. Clear browser cache
3. Try a different browser
4. Check for CSP errors in browser console
5. Ensure no ad blocker is interfering

### Dark Mode Not Working

**Error:** Theme doesn't switch or flashes

**Solutions:**
1. Refresh the page after changing settings
2. Check browser supports CSS variables
3. Clear browser cache
4. Check User Settings are saved

### Code Highlighting Missing

**Error:** Code displays without syntax highlighting

**Solutions:**
1. Check the language is correctly selected
2. Try a different language option
3. Check Pygments is installed
4. Refresh the page

### Animations Not Working

**Error:** UI animations disabled or jerky

**Solutions:**
1. Check "Enable Animations" in User Settings
2. Check browser supports CSS animations
3. Disable browser hardware acceleration
4. Try a different browser

## Performance Issues

### Slow Page Loads

**Error:** Pages take too long to load

**Solutions:**
1. Reduce POSTS_PER_PAGE in config (default: 10)
2. Limit exported snippets in bulk operations
3. Clear old snapshots in the snapshots folder
4. Archive old snippets to collections
5. Check for large embeddings slowing search

### High Memory Usage

**Error:** Application uses too much RAM

**Solutions:**
1. Limit snippet history retention
2. Clear old chat sessions
3. Reduce snapshot retention
4. Use SQLite database optimization:
   ```sql
   VACUUM;
   ```

### Search Is Slow

**Error:** Search takes too long

**Solutions:**
1. Reduce search result limit
2. Use more specific search terms
3. Add indexes to frequently searched fields
4. Consider upgrading to PostgreSQL for large datasets

## Export/Import Issues

### Export Fails

**Error:** Export hangs or fails

**Solutions:**
1. Reduce the number of snippets being exported
2. Try exporting filtered subsets
3. Check disk space is available
4. Increase Flask response timeout

### ZIP Export Issues

**Error:** ZIP file corrupted or incomplete

**Solutions:**
1. Try Markdown export instead
2. Reduce number of selected snippets
3. Check disk space
4. Try a different compression method

### Import Not Available

**Error:** No import functionality

**Solution:**
Import feature is not yet implemented. Manually create snippets or convert from exported format.

## Account Issues

### Username Already Taken

**Error:** Cannot register with desired username

**Solution:**
Choose a different username or log in if you already have an account.

### Email Already Registered

**Error:** Email address already in use

**Solution:**
Use a different email or log in to existing account.

### Cannot Change Username/Email

**Error:** Change fails or reverts

**Solutions:**
1. Ensure current password is correct
2. Check new values are unique
3. Try logging out and back in
4. Check for typos in the form

### Avatar Upload Fails

**Error:** Avatar not saving or displaying

**Solutions:**
1. Check file format (PNG, JPG, GIF, WebP only)
2. Check file size limit
3. Ensure upload directory exists and is writable
4. Check file permissions on `app/static/uploads/avatars`

## Browser-Specific Issues

### Chrome Issues

- Disable hardware acceleration if rendering is slow
- Clear site data if logged in state persists incorrectly

### Firefox Issues

- Check Enhanced Tracking Protection isn't blocking features
- Disable惜性跟踪保护如果功能不正常

### Safari Issues

- Enable Develop menu for JavaScript debugging
- Check cross-site tracking restrictions

### Edge Issues

- Check IE mode is not enabled
- Disable hardware acceleration if slow

## Logging and Debugging

### Enable Debug Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
flask run
```

### View Logs

Logs are written to:
1. Terminal output when running `flask run`
2. Check `logs/` directory if configured
3. Browser console for JavaScript errors

### Enable SQL Logging

```python
# In config.py or before first request
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

### Test API Connection

```python
from app import create_app, db
from app.models import User
from app import ai_services

app = create_app()
with app.app_context():
    # Test Gemini connection
    result = ai_services.generate_code_from_prompt("print('test')")
    print("AI Test:", "Success" if "Error" not in result else "Failed")
```

## Getting More Help

### Check Application Health

1. Run `flask shell` and check:
   ```python
   from app import create_app
   app = create_app()
   print(app.url_map)
   ```
2. Check all routes are registered

### Test Database Connection

```python
from app import create_app, db
app = create_app()
with app.app_context():
    print(db.session.execute(db.text("SELECT 1")).scalar())
```

### Verify AI Services

```python
from app import ai_services
print("Minimax available:", ai_services.MINIMAX_AVAILABLE)
print("Default model:", ai_services.MODEL_NAME)
```

### Report Issues

When reporting issues, include:
1. Error messages (full text)
2. Steps to reproduce
3. Browser and version
4. Operating system
5. Flask logs if applicable
6. Configuration (without API keys)

## Common Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| `Error: Could not generate code` | AI API error | Check API key, try again later |
| `Error: Input blocked by API` | Content policy violation | Reformulate prompt |
| `database is locked` | Concurrent access | Restart server, close other connections |
| `Account locked` | Security lockout | Wait 30 minutes or reset manually |
| `404 Not Found` | Page doesn't exist | Check URL, route may have changed |
| `500 Internal Server Error` | Server error | Check Flask logs |
| `Error: Missing code in request` | Client error | Reload page, try again |
| `Badge already earned` | Normal message | No action needed |
| `No snippets found` | Search result | Try different search terms |

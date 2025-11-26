# Troubleshooting Guide

This guide provides solutions to common issues you might encounter while using or developing Project Sophia.

## Quick Fixes

-   **Application Not Starting:**
    -   Ensure your virtual environment is activated (`.venv\Scripts\activate` on Windows or `source venv/bin/activate` on macOS/Linux).
    -   Check if all dependencies are installed (`pip install -r requirements.txt`).
    -   Verify your `.env` file exists and contains all required variables (`SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `FLASK_APP`, `FLASK_ENV`).
    -   Try re-initializing the database (`flask db upgrade`).
-   **No Syntax Highlighting for Code:**
    -   Ensure you have selected a valid language when creating/editing the snippet.
    -   Verify the browser's internet connection, as some highlighting libraries might fetch resources dynamically.

## Known Issues

-   **Large AI Generation Timeouts:** Generating very complex or lengthy code snippets via AI might occasionally time out, especially on slower connections or with high server load.
    -   **Workaround:** Try breaking down complex requests into smaller, more manageable prompts.
-   **AI Code Formatting Timeouts:** Formatting extremely large or complex code blocks via AI might also experience timeouts.
    -   **Workaround:** Try formatting smaller, more manageable code sections.
-   **Collection Reordering Visual Glitches:** In rare cases, rapid reordering of collections might cause minor visual inconsistencies before the next page refresh. The backend order remains correct.
    -   **Workaround:** Refresh the page to synchronize the visual order with the backend.

## Error Messages

### Error: `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked`
**Symptom:** You might see this error during database operations (e.g., saving snippets, user registration) or `flask db` commands.
**Cause:** This typically happens when multiple processes try to write to the SQLite database file (`app.db`) simultaneously. This can occur if:
    1.  The Flask development server is running and you try to run another `flask db` command.
    2.  An editor (like VS Code) has the `app.db` file open and is locking it.
**Solution:**
1.  Stop any running Flask development servers (`Ctrl+C` in the terminal).
2.  Close any applications (like database browsers or text editors) that might be accessing `app.db`.
3.  Try the operation again.

### Error: `KeyError: 'GEMINI_API_KEY'` or `ConfigurationError: Missing Gemini API Key`
**Symptom:** AI generation or formatting features fail with an error indicating a missing API key.
**Cause:** The `GEMINI_API_KEY` environment variable is either not set or incorrectly configured.
**Solution:**
1.  Open your `.env` file in the project root.
2.  Ensure you have a line like `GEMINI_API_KEY='your_gemini_api_key_here'` and that `your_gemini_api_key_here` is replaced with your actual Google Gemini API key.
3.  Restart the Flask development server after modifying the `.env` file.

### Error: `Address already in use`
**Symptom:** When running `flask run`, you get an error saying the address is already in use.
**Cause:** Another application (or a previous instance of your Flask app) is already using port 5000 (the default Flask port).
**Solution:**
1.  Find and terminate the process using port 5000. On Windows, you can use `netstat -ano | findstr :5000` to find the PID, then `taskkill /PID <PID> /F`. On Linux/macOS, use `lsof -i :5000` and `kill -9 <PID>`.
2.  Alternatively, start the Flask app on a different port by running `flask run --port 5001`.

## Logs & Debugging

-   **Enable Debug Mode:** Set `FLASK_ENV=development` in your `.env` file. This will provide more detailed error messages in your browser and terminal.
-   **Server Logs:** Check the terminal where your Flask application is running for any error messages or warnings.
-   **AI Service Logs (Celery):** If using Celery for background tasks, ensure your Celery worker is running (`celery -A run.celery worker --loglevel=info`) and check its output for errors related to AI generation.

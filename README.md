# Project Sophia v2.0

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Project Sophia is a comprehensive knowledge management system designed to help developers organize, manage, and share code snippets, solutions, and technical insights. It combines powerful AI capabilities with robust organization features to streamline your coding workflow.

## 🌟 What's New in v2.0

### AI-Powered Features
- ✨ **Modern Code Generation UI** - Beautiful gradient design with micro-animations
- ✨ **Streaming Code Display** - Real-time typewriter effect for generated code
- ✨ **Enhanced Code Explanation** - Formatted markdown with copy & apply features
- ✨ **Smart Tag Suggestions** - AI-powered tag generation with intelligent filtering
- ✨ **Chat Assistant** - Context-aware coding assistant with streaming responses

### UI/UX Improvements
- 🎨 Modern glassmorphism design
- 🎨 Micro-animations throughout
- 🎨 Syntax-highlighted code blocks
- 🎨 Custom scrollbars and themes
- 🎨 Responsive mobile design

## About the Project

Project Sophia addresses the common problem developers face in managing an ever-growing collection of code snippets, solutions to problems, and general technical knowledge. It provides a structured environment to:

- **Organize Code Snippets** - Create, categorize, and tag code snippets by language and collection
- **AI-Powered Development** - Generate code, explain existing code, format, and refactor using AI
- **Personal Knowledge Base** - Create notes and document your technical knowledge
- **Gamification** - Track progress with points, badges, and activity streaks
- **Advanced Search** - Find snippets using keyword and semantic search with embeddings

### Tech Stack

- **Backend:** Flask (Python)
- **Database:** SQLite (SQLAlchemy ORM) with automatic migrations
- **Frontend:** HTML, CSS (Bootstrap + custom styles), JavaScript
- **AI Integration:**
  - Google Gemini API (gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.5-pro, gemini-3-pro)
  - Multi-step thinking pipeline (Architecture → Coder → Tester → Refiner)
  - Streaming code generation with real-time display
  - BYOK (Bring Your Own Key) support for personal API keys
- **Authentication:** Flask-Login with password hashing (Werkzeug)
- **Forms:** WTForms with validation and CSRF protection
- **Database Migrations:** Alembic/Flask-Migrate
- **Syntax Highlighting:** Pygments
- **Markdown:** python-markdown for note rendering

## Documentation

- **[User Guide](User Guide.md)** - Complete user manual with tutorials and examples
- **[Developer Guide](Developer Guide.md)** - Technical documentation for contributors
- **[Features](Features.md)** - Detailed feature descriptions and demos
- **[Troubleshooting](Troubleshooting.md)** - Common issues and solutions (NEW)
- **[Updates](updates.md)** - Version history and migration guide (NEW)
- **[Performance](PERFORMANCE.md)** - Performance optimizations and benchmarks

## Getting Started

### Prerequisites

- Python 3.9+
- pip (Python package installer)
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AlexBiobelemo/Project-Sophia.git
   cd Project-Sophia
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   \venv\Scripts\activate  # On Windows
   source venv/bin/activate # On macOS/Linux
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory and add the following:
   ```
   SECRET_KEY='your_secret_key_here'
   DATABASE_URL='sqlite:///app.db'
   GEMINI_API_KEY='your_gemini_api_key_here'
   FLASK_APP=run.py
   FLASK_ENV=development
   ```
   - Replace `GEMINI_API_KEY` with your actual Google Gemini API key

5. **Initialize the database:**
   ```bash
   flask db upgrade
   ```

6. **Initialize badges:**
   ```bash
   python -c "from app.badge_system import initialize_default_badges; from app import create_app, db; app = create_app(); with app.app_context(): initialize_default_badges()"
   ```

### Usage

To run the application:
```bash
python run.py
```
The application will typically be available at `http://127.0.0.1:5000/`. Open this URL in your web browser.

## Render/Production Notes

- `run.py` runs best-effort automatic migrations on startup when `RENDER_EXTERNAL_URL` is present (override with `AUTO_MIGRATE=0`).
- Keep-alive self-ping auto-enables on Render (single-leader via lock) and pings `GET /health` every ~12 minutes.
  - Override with `SELF_PING_ENABLED=0` or customize with `SELF_PING_*` env vars.

## Maintenance Scripts

- Backfill missing snippet versions: `python scripts/backfill_snippet_versions.py`
- Auto-upgrade DB (manual run): `python scripts/auto_migrate.py`
- Import/merge another SQLite DB into your current user: `python scripts/import_merge_sqlite.py --help`

## Key Features

### Code Snippet Management
- Create, edit, delete code snippets
- Syntax highlighting for multiple programming languages
- Tag-based organization
- Version history with rollback capability
- AI-powered code explanation and formatting

### Collection Organization
- Hierarchical collections with nested folders
- Drag-and-drop reordering
- Move and copy snippets between collections
- Collection statistics

### AI-Powered Features
- **Code Generation:** Generate code from natural language prompts
- **Code Explanation:** Get detailed explanations for any code snippet
- **Code Formatting:** AI-powered code formatting for consistency
- **Tag Suggestion:** Automatic tag suggestions for code
- **Code Refinement:** Fix bugs and improve code based on error messages
- **Multi-Step Thinking:** Architecture → Coder → Tester → Refiner pipeline
- **Streaming Generation:** Real-time code and explanation streaming

### Notes System
- Create and manage personal notes
- AI-powered note explanation
- Rich text support with Markdown

### Chat Assistant
- AI-powered coding assistant
- Conversation history with multiple sessions
- Context-aware responses based on your snippets

### Gamification
- Points system for activities (snippet creation, solution approval, etc.)
- 25+ badges for achievements
- Activity streaks tracking
- User profile analytics and statistics

### Search & Discovery
- Advanced search with filters (language, tags, date, collection)
- Semantic search using vector embeddings
- Search highlighting and scoring

### Export & Backup
- Export snippets as Markdown files
- Export filtered snippets
- Bulk export to ZIP archive
- Automatic daily snapshots

### User Management
- Secure registration and login
- Account lockout after failed login attempts
- Profile customization with avatars
- User preferences (dark mode, AI model selection, UI settings)

## API Configuration

Project Sophia uses Google Gemini for all AI-powered features:

### Google Gemini
- Set `GEMINI_API_KEY` environment variable
- Default model: `gemini-2.5-flash`
- Available models: 
  - `gemini-2.5-flash` - Fast, good for simple tasks
  - `gemini-2.5-flash-lite` - Lightweight, fastest option
  - `gemini-2.5-pro` - Balanced, good for most tasks
  - `gemini-3-pro` - Advanced, best for complex tasks

### BYOK (Bring Your Own Key)
Users can optionally save and use their own Google Gemini API key:
1. Go to **User Settings** → **AI Settings**
2. Enter your API key in the "Gemini API Key" field
3. Toggle "Use my own API key instead of default"
4. Save settings

This allows users to:
- Use their own API quota
- Access premium features with their own subscription
- Have more control over API usage

Users can select their preferred AI model in the User Settings.

## Project Structure

```
Project-Sophia/
├── app/
│   ├── __init__.py          # Flask app factory and configuration
│   ├── routes.py            # All route handlers and view functions
│   ├── models.py            # SQLAlchemy database models
│   ├── forms.py             # WTForms for input validation
│   ├── ai_services.py       # Gemini AI service implementation
│   ├── badge_system.py      # Gamification and badge logic
│   ├── self_ping.py         # Self-ping keep-alive for production
│   ├── utils/               # Utility functions and helpers
│   │   ├── state_manager.py # Client-side state management
│   │   └── process_lock.py  # Process locking for auto-migration
│   ├── static/              # Static assets (CSS, JS, uploads)
│   └── templates/           # Jinja2 HTML templates
├── migrations/              # Alembic database migrations
├── snapshots/               # Automatic daily snapshots
├── backup/                  # Database backups (auto-generated)
├── scripts/                 # Maintenance scripts
│   ├── auto_migrate.py      # Manual database migration
│   ├── backfill_snippet_versions.py
│   └── import_merge_sqlite.py
├── config.py                # Application configuration
├── database_backup.py       # Automatic backup system
├── requirements.txt         # Python dependencies
├── run.py                   # Application entry point
└── initialize_badges.py     # Badge initialization script
```

## Security Features

- **Password Security:**
  - Password hashing with Werkzeug
  - Minimum 8 characters with complexity requirements
  - Current password required for changes

- **Session Management:**
  - Flask-Login with secure cookies
  - Configurable session timeout (default: 1 hour)
  - Remember Me functionality with HTTP-only cookies

- **Account Protection:**
  - Account lockout after 5 failed login attempts (30-minute lockout)
  - Rate limiting on authentication endpoints
  - CSRF protection via WTForms with time-limited tokens

- **Request Security:**
  - Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)
  - Content Security Policy (CSP)
  - Referrer-Policy headers
  - CSRF token stripping from query strings
  - Request timing and ID tracking for debugging

- **Input Validation:**
  - Form validation with WTForms
  - SQL injection prevention via SQLAlchemy ORM
  - XSS protection via Jinja2 auto-escaping
  - File upload restrictions (images only for avatars)
  - Maximum content length (16MB default)

- **API Security:**
  - API keys stored encrypted in database
  - BYOK support with user-controlled keys
  - Request timeouts and retry logic for AI services

## Advanced Features

### Multi-Step Thinking Generation
For complex coding tasks, the AI uses a 4-layer thinking process:
1. **Architecture Layer:** Analyzes the problem and designs the solution approach
2. **Coder Layer:** Generates the actual code implementation
3. **Tester Layer:** Verifies code against test cases and identifies bugs
4. **Refiner Layer:** Optimizes and polishes the final solution

Access via **AI Code Generation** → Enable "Multi-Step Thinking" option.

### Streaming Code Generation
Real-time code display as the AI generates:
- Typewriter effect for smooth viewing
- Syntax highlighting during streaming
- Copy and save while streaming
- Progress indicators

### Snippet Version History
Every edit creates an automatic snapshot:
- View all historical versions
- Compare changes with diff view
- Rollback to any previous version
- Track who made changes and when

### Semantic Search
AI-powered search using vector embeddings:
- Finds conceptually related snippets
- Works even without exact keyword matches
- Combines keyword and semantic search
- Search scoring and highlighting

### Automatic Backups
Comprehensive backup system:
- Server startup backups
- Post-save backups (every 5 snippet saves)
- Manual backup capability
- Configurable retention (default: 50 backups)
- One-click restore

### Chat Assistant
Context-aware AI coding assistant:
- Multiple chat sessions
- Conversation history
- Refers to your snippets
- Copy responses
- Session management (rename, delete)

### Gamification System
Track your progress with points and badges:
- **25+ Badges** across categories:
  - Snippet creation milestones
  - Collection organization
  - Points accumulation
  - Activity streaks (3, 7, 14, 30 days)
  - Language diversity (Polyglot, Universal Coder)
  - Notes and documentation
- **Points System:**
  - Create snippet: 10 points
  - Create note: 5 points
  - Copy snippet: 5 points
- **Streak Tracking:** Daily activity monitoring
- **Profile Statistics:** Analytics and insights

### Production Deployment (Render)
Optimized for Render deployment:
- **Auto-Migration:** `AUTO_MIGRATE=1` runs migrations on startup
- **Self-Ping Keep-Alive:** Prevents sleep on free tier
- **Health Check:** `/health` endpoint for monitoring
- **Environment Variables:** Easy configuration

## Configuration Options

### Environment Variables
```bash
# Required
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///app.db
GEMINI_API_KEY=your_gemini_api_key

# Optional - AI Configuration
AI_REQUEST_TIMEOUT_SECONDS=300
GEMINI_API_KEY=

# Optional - Security
SESSION_COOKIE_SECURE=1
REMEMBER_COOKIE_SECURE=1
WTF_CSRF_SSL_STRICT=False
SESSION_COOKIE_SAMESITE=Lax

# Optional - Render Deployment
AUTO_MIGRATE=1
AUTO_MIGRATE_LOCK_PATH=/tmp/sophia-auto-migrate.lock
SELF_PING_ENABLED=1
RENDER_EXTERNAL_URL=https://your-app.onrender.com

# Optional - Debug (Development Only)
FLASK_DEBUG=1
FLASK_ENV=development
```

### User Preferences
Configurable in **User Settings**:
- **AI Settings:**
  - Preferred AI model
  - Code generation style (balanced/detailed/concise)
  - Auto-explain code on creation
  - BYOK (Bring Your Own Key)

- **UI Preferences:**
  - Dark/Light mode
  - Show line numbers
  - Enable animations
  - Enable tooltips
  - Tooltip delay (1-10 seconds)

- **Privacy:**
  - Public profile toggle
  - Show activity on profile
  - Default snippet visibility

- **Notifications:**
  - Email notifications toggle

- **Auto-Save:**
  - Auto-save snippets while editing

## Contact/Acknowledgments

- Developed by Alex Biobelemo
- Inspired by personal needs for better code organization
- Uses Google Gemini API for AI capabilities
 

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
- **Database:** SQLite (SQLAlchemy ORM)
- **Frontend:** HTML, CSS (Bootstrap + custom styles), JavaScript
- **AI Integration:**
  - Google Gemini API (gemini-2.5-flash, gemini-2.5-pro, gemini-3-pro)
- **Authentication:** Flask-Login with password hashing (Werkzeug)
- **Forms:** WTForms with validation
- **Database Migrations:** Alembic/Flask-Migrate
- **Syntax Highlighting:** Pygments
- **Markdown:** python-markdown for note rendering

## Documentation

- **[User Guide](User Guide.md)** - Complete user manual with tutorials and examples
- **[Developer Guide](Developer Guide.md)** - Technical documentation for contributors
- **[Features](Features.md)** - Detailed feature descriptions and demos
- **[Troubleshooting](Troubleshooting.md)** - Common issues and solutions
- **[Updates](updates.md)** - Version history and migration guide

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
- Available models: gemini-2.5-flash, gemini-2.5-pro, gemini-3-pro

Users can select their preferred AI model in the User Settings.

## Project Structure

```
Project-Sophia/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes.py            # All route handlers
│   ├── models.py            # SQLAlchemy models
│   ├── forms.py             # WTForms forms
│   ├── ai_services.py       # Gemini AI service implementation
│   ├── badge_system.py      # Badge and gamification
│   ├── utils/               # Utility functions
│   ├── static/              # Static assets (CSS, JS, uploads)
│   └── templates/           # Jinja2 templates
├── migrations/              # Alembic migrations
├── snapshots/               # Automatic daily snapshots
├── config.py                # Configuration
├── requirements.txt         # Python dependencies
└── run.py                   # Application entry point
```

## Security Features

- Password hashing with Werkzeug
- Session management with Flask-Login
- Account lockout after 5 failed login attempts (30-minute lockout)
- CSRF protection via WTForms
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Input validation and sanitization

## Contact/Acknowledgments

- Developed by Alex Biobelemo
- Inspired by personal needs for better code organization
- Uses Google Gemini API for AI capabilities
 

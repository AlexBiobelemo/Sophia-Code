# Developer Guide

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [Application Structure](#application-structure)
  - [Key Components](#key-components)
- [Development Setup](#development-setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running the Application](#running-the-application)
- [Database Schema](#database-schema)
  - [Core Tables](#core-tables)
  - [Relationships](#relationships)
  - [Indexes](#indexes)
- [API Reference](#api-reference)
  - [Authentication Endpoints](#authentication-endpoints)
  - [Snippet Management](#snippet-management)
  - [AI Services](#ai-services)
- [Extending the Application](#extending-the-application)
  - [Adding New AI Providers](#adding-new-ai-providers)
  - [Adding New Models](#adding-new-models)
  - [Adding New Routes](#adding-new-routes)
  - [Customizing UI](#customizing-ui)
- [Testing](#testing)
  - [Unit Tests](#unit-tests)
  - [Running Tests](#running-tests)
- [Deployment](#deployment)
  - [Production Configuration](#production-configuration)
  - [Docker Deployment](#docker-deployment)
- [Security Considerations](#security-considerations)
  - [Authentication](#authentication)
  - [Input Validation](#input-validation)
  - [API Security](#api-security)
  - [AI Service Security](#ai-service-security)
- [Performance Optimization](#performance-optimization)
  - [Database Optimization](#database-optimization)
  - [Caching](#caching)
  - [AI Service Optimization](#ai-service-optimization)
- [Contributing](#contributing)
  - [Code Style](#code-style)
  - [Pull Request Process](#pull-request-process)
  - [Issue Reporting](#issue-reporting)
- [Troubleshooting](#troubleshooting)
  - [Common Development Issues](#common-development-issues)
- [License](#license)
- [Support](#support)

## Overview

This guide provides comprehensive information for developers who want to contribute to, extend, or maintain Project Sophia. Project Sophia is a Flask-based web application for code snippet management with AI-powered features.

## Architecture

### Application Structure

```
Project-Sophia/
├── app/
│   ├── __init__.py          # Flask app factory and configuration
│   ├── routes.py            # All route handlers and view functions (~3300 lines)
│   ├── models.py            # SQLAlchemy database models
│   ├── forms.py             # WTForms for input validation
│   ├── ai_services.py       # Gemini AI service implementation (~940 lines)
│   ├── badge_system.py      # Gamification and badge logic
│   ├── self_ping.py         # Self-ping keep-alive for production
│   ├── utils/               # Utility functions and helpers
│   │   ├── state_manager.py # Client-side state management (form preservation)
│   │   └── process_lock.py  # Process locking for auto-migration
│   ├── static/              # Static assets (CSS, JS, uploads)
│   │   ├── css/
│   │   │   └── style.css    # Main stylesheet with design system
│   │   ├── js/
│   │   │   ├── tooltip_system.js  # Tooltip with caching
│   │   │   ├── streaming-ai.js    # Streaming AI display
│   │   │   └── ...
│   │   └── uploads/         # User uploads (avatars, etc.)
│   └── templates/           # Jinja2 HTML templates
│       ├── _snippets_list.html  # Partial for infinite scroll
│       ├── base.html        # Base template
│       ├── index.html       # Homepage with infinite scroll
│       ├── generate.html    # AI code generation
│       ├── multi_step_results.html  # Multi-step results display
│       ├── view_snippet.html    # Snippet detail with version history
│       ├── version_diff.html    # Diff view between versions
│       ├── chat.html        # Chat assistant
│       └── ...
├── migrations/              # Alembic database migrations
├── snapshots/               # Automatic daily snapshots
├── backup/                  # Database backups (auto-generated)
├── scripts/                 # Maintenance scripts
│   ├── auto_migrate.py      # Manual database migration
│   ├── backfill_snippet_versions.py  # Backfill version history
│   └── import_merge_sqlite.py        # Import/merge databases
├── config.py                # Application configuration
├── database_backup.py       # Automatic backup system
├── requirements.txt         # Python dependencies
├── run.py                   # Application entry point
└── initialize_badges.py     # Badge initialization script
```

### Key Components

#### Flask Application Factory

The application uses the Flask application factory pattern in `app/__init__.py`. This allows for:
- Multiple application instances for testing
- Configuration-based setup
- Clean separation of concerns
- **New in v2.0:**
  - SQLite async dialect patch (prevents aiosqlite errors)
  - CSRF token stripping from query strings
  - Security headers middleware
  - Request timing and ID tracking
  - User AI preference injection per request
  - Jinja markdown filters

#### Database Models

All database models are defined in `app/models.py` using SQLAlchemy ORM. Key models include:

**Core Models:**
- **User**: User accounts with preferences and authentication
  - BYOK support (`gemini_api_key`, `use_own_api_key`)
  - UI preferences (dark mode, tooltips, animations)
  - AI preferences (preferred model, generation style)
  
- **Snippet**: Code snippets with metadata
  - `thought_steps` JSON for multi-step thinking
  - `embedding` JSON for semantic search
  - Relationship to versions
  
- **SnippetVersion**: Immutable version history
  - Automatic snapshots before edits
  - Diff and restore capabilities
  
- **Collection**: Hierarchical organization for snippets
  - Self-referential for nested collections
  
- **Note**: Personal note-taking with Markdown support

**AI & Chat Models:**
- **ChatSession/Message**: AI chat functionality
- **MultiStepResult**: Multi-step thinking results
  - 4-layer thinking process storage
  - Processing time tracking
  - Status tracking (processing/completed/error)

**Gamification Models:**
- **Point**: Points for activities
- **Badge**: Badge definitions
- **UserBadge**: User-badge associations

#### AI Services

The AI functionality is implemented in `app/ai_services.py`, which provides:

**Core Functions:**
- `generate_code_from_prompt()` - Code generation with streaming
- `explain_code()` - Code explanation with chunking support
- `format_code_with_ai()` - Code formatting
- `suggest_tags_for_code()` - Tag suggestions
- `chat_answer()` - Chat assistant responses
- `refine_code_with_feedback()` - Code refinement from errors
- `generate_embedding()` - Vector embeddings for semantic search
- `multi_step_complete_solver()` - 4-layer thinking pipeline

**New in v2.0:**
- Model tiering and fallback system
- Retry logic with exponential backoff
- Request timeouts with thread pool execution
- Input chunking for large inputs
- Streaming-friendly response handling
- BYOK support (user API keys)
- Heuristic language detection

#### Route Organization

Routes are organized in `app/routes.py` with clear separation:

**Authentication Routes:**
- `/login`, `/logout`, `/register`
- Rate limiting and account lockout

**Snippet Management:**
- `/create_snippet`, `/snippet/<id>`, `/snippet/<id>/edit`
- `/snippet/<id>/history`, `/snippet/<id>/revert`
- `/snippet/version/<id>/diff`, `/snippet/version/<id>/restore`
- `/snippet/<id>/delete`

**AI-Powered Features:**
- `/generate` - AI code generation page
- `/generate_multi_step` - Multi-step thinking API
- `/get_multi_step_result/<result_id>` - Retrieve results
- `/multi_step_results/<result_id>` - Display results
- `/explain` - Code explanation API
- `/api/stream-code-generation` - Streaming generation

**Chat:**
- `/chat` - Chat interface
- `/api/chat` - Chat API endpoint

**User Profile & Settings:**
- `/user_profile`, `/edit_profile`
- `/user_settings`

**API Endpoints:**
- `/api/note/<id>/explain`
- `/api/save_streaming_result`
- `/health` - Health check for monitoring

#### Backup System

Implemented in `database_backup.py`:
- Automatic server startup backups
- Post-save backups (every 5 snippet saves)
- Manual backup capability
- Configurable retention (default: 50)
- One-click restore
- Command-line interface

#### Self-Ping Keep-Alive

Implemented in `self_ping.py`:
- Prevents Render free tier sleep
- Single-leader election via file lock
- Configurable ping interval
- Health check endpoint integration

## Development Setup

### Prerequisites

- Python 3.9+
- pip
- Git
- SQLite (included with Python)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/AlexBiobelemo/Project-Sophia.git
   cd Project-Sophia
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env  # If example exists
   # Edit .env with your API keys
   ```

5. Initialize database:
   ```bash
   flask db upgrade
   python -c "from app.badge_system import initialize_default_badges; from app import create_app, db; app = create_app(); with app.app_context(): initialize_default_badges()"
   ```

### Running the Application

```bash
flask run
```

The application will be available at `http://127.0.0.1:5000/`

## Database Schema

### Core Tables

#### User Table
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256),
    avatar_filename VARCHAR(255),
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login DATETIME,
    locked_until DATETIME,
    
    -- AI Preferences
    preferred_ai_model VARCHAR(50) DEFAULT 'gemini-2.5-flash',
    code_generation_style VARCHAR(50) DEFAULT 'balanced',
    auto_explain_code BOOLEAN DEFAULT TRUE,
    gemini_api_key VARCHAR(512),  -- Encrypted
    use_own_api_key BOOLEAN DEFAULT FALSE,
    
    -- UI Preferences
    show_line_numbers BOOLEAN DEFAULT TRUE,
    enable_animations BOOLEAN DEFAULT TRUE,
    enable_tooltips BOOLEAN DEFAULT TRUE,
    tooltip_delay INTEGER DEFAULT 3,
    dark_mode BOOLEAN DEFAULT TRUE,
    
    -- Privacy & Other
    email_notifications BOOLEAN DEFAULT TRUE,
    auto_save_snippets BOOLEAN DEFAULT TRUE,
    public_profile BOOLEAN DEFAULT FALSE,
    show_activity BOOLEAN DEFAULT TRUE,
    snippet_visibility VARCHAR(20) DEFAULT 'private'
);

-- Indexes
CREATE UNIQUE INDEX ix_user_username ON user(username);
CREATE UNIQUE INDEX ix_user_email ON user(email);
CREATE INDEX ix_user_locked_until ON user(locked_until);
```

#### Snippet Table
```sql
CREATE TABLE snippet (
    id INTEGER PRIMARY KEY,
    title VARCHAR(140),
    code TEXT NOT NULL,
    description TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES user(id),
    tags VARCHAR(200),
    embedding JSON,  -- Vector embedding for semantic search
    collection_id INTEGER REFERENCES collection(id),
    language VARCHAR(50) DEFAULT 'python',
    thought_steps JSON  -- Multi-step thinking process
);

-- Indexes
CREATE INDEX ix_snippet_timestamp ON snippet(timestamp);
CREATE INDEX ix_snippet_user_id ON snippet(user_id);
CREATE INDEX ix_snippet_title ON snippet(title);
CREATE INDEX ix_snippet_language ON snippet(language);
```

#### SnippetVersion Table (NEW in v2.0)
```sql
CREATE TABLE snippet_version (
    id INTEGER PRIMARY KEY,
    snippet_id INTEGER REFERENCES snippet(id) NOT NULL,
    title VARCHAR(140),
    description TEXT,
    code TEXT,
    language VARCHAR(50) DEFAULT 'python',
    tags VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX ix_snippet_version_snippet_id ON snippet_version(snippet_id);
CREATE INDEX ix_snippet_version_created_at ON snippet_version(created_at);
```

#### MultiStepResult Table (NEW in v2.0)
```sql
CREATE TABLE multi_step_result (
    id INTEGER PRIMARY KEY,
    result_id VARCHAR(36) UNIQUE NOT NULL,  -- UUID
    user_id INTEGER REFERENCES user(id) NOT NULL,
    prompt TEXT NOT NULL,
    test_cases TEXT,
    status VARCHAR(20) DEFAULT 'processing',
    error_message TEXT,
    
    -- Multi-step thinking layers
    layer1_architecture TEXT,  -- Architecture analysis
    layer2_coder TEXT,         -- Code generation
    layer3_tester TEXT,        -- Testing/verification
    layer4_refiner TEXT,       -- Refinement
    
    -- Results
    final_code TEXT,
    processing_time FLOAT,
    
    -- Timestamps
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

-- Indexes
CREATE INDEX ix_multi_step_result_result_id ON multi_step_result(result_id);
CREATE INDEX ix_multi_step_result_user_id ON multi_step_result(user_id);
CREATE INDEX ix_multi_step_result_timestamp ON multi_step_result(timestamp);
CREATE INDEX ix_multi_step_result_status ON multi_step_result(status);
```

#### ChatSession & ChatMessage Tables (NEW in v2.0)
```sql
CREATE TABLE chat_session (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES user(id) NOT NULL,
    title VARCHAR(200) NOT NULL DEFAULT 'New Chat',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_message (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES chat_session(id) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Relationships

- **User → Snippets** (one-to-many)
- **User → Collections** (one-to-many)
- **Collection → Snippets** (one-to-many)
- **Collection → Sub-collections** (self-referential one-to-many)
- **Snippet → Versions** (one-to-many)
- **User → Notes** (one-to-many)
- **User → Chat Sessions** (one-to-many)
- **Chat Session → Messages** (one-to-many)
- **User → Points** (one-to-many)
- **User → Badges** (many-to-many via UserBadge)
- **User → MultiStepResults** (one-to-many)

### Indexes

Key indexes for performance:

**User:**
- `ix_user_username` - Unique username lookup
- `ix_user_email` - Unique email lookup
- `ix_user_locked_until` - Fast locked account queries

**Snippet:**
- `ix_snippet_timestamp` - Date-based sorting
- `ix_snippet_user_id` - User's snippets
- `ix_snippet_title` - Title search
- `ix_snippet_language` - Language filtering

**Collection:**
- `ix_collection_timestamp` - Date sorting
- `ix_collection_user_id` - User's collections
- `ix_collection_parent_id` - Nested collections

**SnippetVersion:**
- `ix_snippet_version_snippet_id` - Version lookup
- `ix_snippet_version_created_at` - Historical queries

**MultiStepResult:**
- `ix_multi_step_result_result_id` - Result lookup by UUID
- `ix_multi_step_result_user_id` - User's results
- `ix_multi_step_result_timestamp` - Date sorting
- `ix_multi_step_result_status` - Status filtering

**Chat:**
- `ix_chat_session_user_id` - User's sessions
- `ix_chat_session_updated_at` - Recent sessions
- `ix_chat_message_session_id` - Session messages

## API Reference

### Authentication Endpoints

#### POST /login
User login with rate limiting and account lockout.

**Request Body:**
```json
{
    "username": "string",
    "password": "string",
    "remember_me": "boolean"
}
```

**Response:**
```json
{
    "success": true,
    "redirect": "/index"
}
```

**Error Responses:**
- `400` - Validation error
- `429` - Rate limit exceeded
- Account locked: Flash message with remaining time

### Snippet Management

#### GET /snippet/{id}
Retrieve a specific snippet.

**Parameters:**
- `id` (path): Snippet ID

**Response:** HTML page with snippet details, version history, and navigation

#### POST /create_snippet
Create a new code snippet.

**Request Body (form-data):**
```
title: "New Snippet"
code: "def hello():\n    return 'world'"
language: "python"
description: "Greeting function"
tags: "function,greetings"
collection_id: "1"
```

**Features:**
- Automatic embedding generation
- Version snapshot creation
- Points award (10 points)
- Badge check
- Backup trigger (every 5 saves)

#### POST /snippet/{id}/edit
Edit an existing snippet.

**Features:**
- Automatic version snapshot before save
- Embedding regeneration
- Backup trigger

#### GET /snippet/{id}/history
View snippet version history.

**Response:** HTML page with all versions and rollback options

#### POST /snippet/{id}/revert/{version_id}
Revert snippet to previous version.

**Features:**
- Creates snapshot of current state
- Restores selected version

#### GET /snippet/version/{version_id}/diff (NEW in v2.0)
Show diff between current and historical version.

**Response:** HTML diff table with highlighted changes

#### POST /snippet/version/{version_id}/restore (NEW in v2.0)
Restore a specific version.

**Request:** JSON
**Response:**
```json
{
    "success": true,
    "message": "Version restored successfully",
    "snippet_id": 1
}
```

#### POST /snippet/{id}/update_code (NEW in v2.0)
Update snippet code via API (with auto-snapshot).

**Request Body:**
```json
{
    "code": "updated code here",
    "language": "python"
}
```

#### POST /snippet/{id}/update_description (NEW in v2.0)
Update snippet description via API.

**Request Body:**
```json
{
    "description": "Updated description"
}
```

### AI-Powered Features

#### POST /api/stream-code-generation (NEW in v2.0)
Stream code generation with real-time updates.

**Request Body:**
```json
{
    "prompt": "Write a function to calculate fibonacci numbers",
    "session_id": "uuid-string"
}
```

**Streaming Response (Server-Sent Events):**
```json
{
    "type": "code_chunk",
    "content": "def fibonacci(n):",
    "accumulated": "def fibonacci(n):\n    if n <= 1:",
    "status": "streaming"
}
```

#### POST /generate_multi_step (NEW in v2.0)
Multi-step thinking code generation.

**Request Body:**
```json
{
    "prompt": "Create a REST API for a todo app",
    "test_cases": "Should handle CRUD operations"
}
```

**Response:**
```json
{
    "success": true,
    "result_id": "uuid-string",
    "message": "Multi-step thinking completed!"
}
```

**Process:**
1. Creates `MultiStepResult` record
2. Runs 4-layer thinking pipeline
3. Updates record with results
4. Returns result ID for retrieval

#### GET /get_multi_step_result/{result_id} (NEW in v2.0)
Retrieve multi-step thinking results.

**Response:**
```json
{
    "success": true,
    "result": {
        "id": 1,
        "result_id": "uuid",
        "status": "completed",
        "layer1_architecture": "...",
        "layer2_coder": "...",
        "layer3_tester": "...",
        "layer4_refiner": "...",
        "final_code": "...",
        "processing_time": 12.5
    }
}
```

#### POST /explain
Get AI explanation for code.

**Request Body:**
```json
{
    "code": "print('Hello World')"
}
```

**Response:**
```json
{
    "explanation": "This code prints..."
}
```

#### POST /api/note/{id}/explain
Get AI explanation for a note.

#### POST /save_streaming_as_snippet (NEW in v2.0)
Save streaming AI result as snippet.

**Features:**
- Session-based code storage
- Avoids URL size limits
- Preserves thinking steps

### Chat Assistant (NEW in v2.0)

#### GET /chat
Chat interface page.

#### POST /api/chat
Chat API endpoint.

**Request Body:**
```json
{
    "session_id": 1,
    "message": "How do I sort a list in Python?"
}
```

**Response:**
```json
{
    "response": "You can use the sorted() function...",
    "session_id": 1
}
```

### User Settings

#### GET /user_settings
User settings page.

#### POST /user_settings
Save user preferences.

**Request Body (form-data):**
```
preferred_ai_model: "gemini-2.5-pro"
code_generation_style: "balanced"
dark_mode: "y"
enable_tooltips: "y"
tooltip_delay: "3"
gemini_api_key: "user-key-here"
use_own_api_key: "y"
```

### Utility Endpoints

#### GET /health (NEW in v2.0)
Health check for monitoring.

**Response:**
```json
{
    "status": "ok"
}
```

#### GET /index?page=1&language=python&sort=date_desc&q=search
Homepage with filters and pagination.

**Query Parameters:**
- `page`: Page number (for pagination)
- `language`: Filter by language
- `tag`: Filter by tag
- `sort`: Sort order (alpha, date_asc, date_desc)
- `q`: Search query
- `partial`: Return only snippet list fragment (for infinite scroll)

**Features:**
- Server-side pagination
- Infinite scroll support
- Combined filters

## Extending the Application

### Adding New AI Providers

1. Create a new module in `app/` (e.g., `ai_services_openai.py`)
2. Implement the required functions:
   - `generate_code_from_prompt()`
   - `explain_code()`
   - `format_code_with_ai()`
   - etc.
3. Update `ai_services.py` to include the new provider in `_resolve_provider_for_task()`
4. Add configuration variables for API keys

### Adding New Models

1. Define the model in `app/models.py`
2. Create database migration:
   ```bash
   flask db migrate -m "Add new model"
   flask db upgrade
   ```
3. Add relationships and methods as needed
4. Update forms in `app/forms.py`

### Adding New Routes

1. Add route function in `app/routes.py`
2. Create corresponding template in `app/templates/`
3. Update navigation if needed
4. Add form validation if required

### Customizing UI

1. Add CSS in `app/static/css/`
2. Add JavaScript in `app/static/js/`
3. Update templates to include new assets
4. Use existing CSS classes for consistency

## Testing

### Unit Tests

```python
# Example test structure
import pytest
from app import create_app, db
from app.models import User, Snippet

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

def test_create_snippet(app):
    with app.app_context():
        user = User(username='test', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        snippet = Snippet(
            title='Test Snippet',
            code='print("test")',
            author=user,
            language='python'
        )
        db.session.add(snippet)
        db.session.commit()

        assert snippet.id is not None
        assert snippet.title == 'Test Snippet'
```

### Running Tests

```bash
pytest
# or
python -m pytest
```

## Deployment

### Production Configuration

1. **Environment Setup:**
   - Set `FLASK_ENV=production`
   - Use a production WSGI server (gunicorn, uwsgi)
   - Configure proper database (PostgreSQL recommended for production)
   - Set up proper logging
   - Enable HTTPS
   - Configure backup systems

2. **Environment Variables:**
   ```bash
   # Required
   SECRET_KEY=<generate-strong-random-key>
   DATABASE_URL=postgresql://user:password@localhost/dbname
   GEMINI_API_KEY=your-api-key
   
   # Security
   SESSION_COOKIE_SECURE=1
   REMEMBER_COOKIE_SECURE=1
   SESSION_COOKIE_SAMESITE=Lax
   WTF_CSRF_SSL_STRICT=True
   
   # Performance
   MAX_CONTENT_LENGTH=16777216  # 16MB
   AI_REQUEST_TIMEOUT_SECONDS=300
   ```

3. **Operational Toggles (Render-specific):**
   - `AUTO_MIGRATE=1` - Runs `flask db upgrade` best-effort on startup
     - Auto-enabled when `RENDER_EXTERNAL_URL` is present
     - Override with `AUTO_MIGRATE=0`
   - `SELF_PING_ENABLED=1` - Enables in-app keepalive pings to `GET /health`
     - Auto-enabled on Render
     - Single-leader election via file lock
     - Pings every ~12 minutes
     - Override with `SELF_PING_ENABLED=0`
   - `AUTO_MIGRATE_LOCK_PATH` - Custom lock file path (default: `/tmp/sophia-auto-migrate.lock`)

4. **Backup System:**
   - Automatic server startup backups
   - Post-save backups (every 5 snippet saves)
   - Manual backup via `database_backup.py`
   - Configure retention with `max_backups` parameter
   - Store backups outside web root

### Render Deployment

Project Sophia is optimized for Render deployment:

1. **Create New Web Service:**
   - Connect GitHub repository
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `gunicorn run:app`

2. **Environment Variables:**
   ```bash
   SECRET_KEY=<random-secret>
   GEMINI_API_KEY=your-gemini-api-key
   FLASK_ENV=production
   AUTO_MIGRATE=1
   SELF_PING_ENABLED=1
   ```

3. **Database:**
   - SQLite works for small deployments
   - For production, use Render's PostgreSQL add-on
   - Update `DATABASE_URL` accordingly

4. **Keep-Alive:**
   - Self-ping automatically enabled on Render
   - Prevents free tier sleep
   - Health check at `/health`

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Initialize database
RUN flask db upgrade

# Initialize badges
RUN python -c "from app.badge_system import initialize_default_badges; from app import create_app, db; app = create_app(); with app.app_context(): initialize_default_badges()"

# Create backup directory
RUN mkdir -p backup

# Expose port
EXPOSE 5000

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--threads", "4", "run:app"]
```

**Docker Compose:**
```yaml
version: '3.8'

services:
  sophia:
    build: .
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DATABASE_URL=sqlite:///app.db
    volumes:
      - sophia-data:/app
      - sophia-backups:/app/backup
    restart: unless-stopped

volumes:
  sophia-data:
  sophia-backups:
```

### Kubernetes Deployment (Basic)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sophia
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sophia
  template:
    metadata:
      labels:
        app: sophia
    spec:
      containers:
      - name: sophia
        image: your-registry/sophia:latest
        ports:
        - containerPort: 5000
        env:
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: sophia-secrets
              key: secret-key
        - name: GEMINI_API_KEY
          valueFrom:
            secretKeyRef:
              name: sophia-secrets
              key: gemini-api-key
        volumeMounts:
        - name: data
          mountPath: /app/instance
        - name: backups
          mountPath: /app/backup
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: sophia-data-pvc
      - name: backups
        persistentVolumeClaim:
          claimName: sophia-backups-pvc
```

## Security Considerations

### Authentication
- **Password Security:**
  - Password hashing using Werkzeug with configurable salt
  - Minimum 8 characters with complexity requirements (lowercase, uppercase, digit, symbol)
  - Current password required for changes
  - Password strength validation
  
- **Account Protection:**
  - Account lockout after 5 failed attempts (30-minute lockout)
  - Rate limiting on authentication endpoints (10 per minute)
  - Failed login tracking with timestamps
  - Secure session management with Flask-Login

### Session Security
- HTTP-only cookies for session and remember tokens
- Secure flag enabled in production
- SameSite=Lax for CSRF protection
- Configurable session timeout (default: 1 hour)
- Session type: filesystem for persistence

### Input Validation
- All forms use WTForms validation
- SQL injection prevention via SQLAlchemy ORM
- XSS protection via Jinja2 auto-escaping
- File upload restrictions (images only for avatars)
- Maximum content length (16MB default)
- Custom language sanitization (regex, length limits)

### CSRF Protection
- WTForms CSRF tokens on all forms
- Time-limited tokens (1 hour)
- CSRF token stripping from query strings
- SSL strict mode (configurable)
- Unique request ID tracking

### Request Security
- **Security Headers:**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy` (tuned for app assets)
  
- **Request Tracking:**
  - UUID-based request ID
  - Response timing headers
  - Debug logging with request context

### API Security
- Rate limiting on authentication (Flask-Limiter)
- Rate limiting on AI endpoints (20 per minute)
- Input validation and size limits
- API key encryption in database
- BYOK support with user-controlled keys
- Error handling without exposing sensitive information
- Request timeouts for AI services

### AI Service Security
- API keys stored encrypted (user keys)
- Request validation before API calls
- Input size validation (token estimation)
- Timeout handling with thread pool
- Retry logic with exponential backoff
- Safety settings configuration
- Chunking for large inputs

### Database Security
- Connection pooling with pre-ping
- Thread-safe SQLite configuration
- Async dialect patching (prevents aiosqlite issues)
- Parameterized queries via ORM

## Performance Optimization

### Database Optimization

**Query Optimization:**
- Database-level aggregations (O(N) → O(1))
  - `User.get_total_points()` uses `SUM()` instead of loading all records
- Cached counts for badge calculations (80% query reduction)
- Proper indexing on frequently queried fields:
  - User: username, email, locked_until
  - Snippet: timestamp, user_id, title, language
  - Collection: parent_id, user_id
  - MultiStepResult: result_id, user_id, status
- Pagination for large result sets (default: 20 per page)
- Connection pooling with pre-ping for SQLite
- Lazy loading for relationships

**Version History:**
- Smart cleanup (keep last 10 results per user)
- Bulk deletion with `DELETE` instead of iterative
- Cleanup on creation (not retrieval) to avoid write in read path

### Caching

**Client-Side Caching:**
- User preferences cached for 60 seconds
  - Tooltip settings
  - UI preferences
- Eliminates redundant API calls
- Reduces latency from ~200ms to <1ms

**Server-Side Caching:**
- Template caching (Jinja2)
- Static asset caching with fingerprints
- Session-based code storage (avoids URL size limits)
- Database query result caching (configurable)

### Frontend Optimization

**DOM Observation:**
- Throttled MutationObserver (250ms)
- Prevents UI thrashing during dynamic updates
- Reduces CPU usage during AI streaming

**Rendering Pipeline:**
- requestAnimationFrame integration
- CSS-based markdown styling (vs. JS manipulation)
- 60% CPU reduction during AI streaming
- Smoother scrolling during generation

**Infinite Scroll:**
- Server-side pagination with `partial=1` parameter
- Loads only visible content
- Reduces initial page load time

### AI Service Optimization

**Model Tiering:**
- Task-appropriate model selection
  - Code generation: gemini-2.5-flash (primary)
  - Simple tasks: gemini-2.5-flash-lite (auto-selected for short inputs)
  - Complex tasks: gemini-2.5-pro, gemini-3-pro

**Request Handling:**
- Streaming responses for large content
- Token-efficient prompting
- Input chunking for large inputs (DEFAULT_MAX_INPUT_TOKENS)
- Combined responses for multi-chunk processing

**Retry Logic:**
- Exponential backoff (base: 1.5s, max: 8s)
- Jitter addition (0-0.5s random)
- Retryable exception detection (5xx errors, timeouts)
- Maximum 3 retries

**Timeout Handling:**
- Thread pool execution
- Configurable timeout (default: 300s)
- Graceful shutdown on interpreter finalization
- No hanging futures

### Content Delivery

**Static Assets:**
- Minified CSS/JS in production
- CDN integration ready
- Gzip compression

**Response Optimization:**
- Security headers without overhead
- Request timing for monitoring
- JSON responses for APIs
- Partial HTML for infinite scroll

### Monitoring

**Performance Metrics:**
- Response time headers (X-Response-Time)
- Request ID tracking
- Debug logging with timing
- Database query logging (development)

**Resource Usage:**
- Memory-efficient token counting
- ThreadPoolExecutor cleanup
- Database connection management
- Backup retention limits

## Contributing

### Code Style
- Follow PEP 8 for Python code
- Use descriptive variable names
- Add docstrings to all functions and classes
- Write clear commit messages

### Pull Request Process
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Ensure all tests pass
5. Update documentation if needed
6. Submit pull request

### Issue Reporting
- Use GitHub issues for bug reports
- Include steps to reproduce
- Provide environment information
- Attach relevant logs

## Troubleshooting

### Common Development Issues

#### Database Lock Errors
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
```
**Solution:** Ensure no other processes are accessing the database file.

#### Missing Dependencies
```
ImportError: No module named 'xyz'
```
**Solution:** Install missing dependencies with `pip install -r requirements.txt`

#### Template Not Found
```
jinja2.exceptions.TemplateNotFound: template.html
```
**Solution:** Check template file exists in `app/templates/` and path is correct

#### AI Service Errors
```
Error: Could not generate code. API key invalid
```
**Solution:** Verify API keys in `.env` file and check API quotas

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For development support:
- Check existing documentation
- Review GitHub issues
- Contact the maintainers

For user support:
- Refer to the User Guide
- Check Troubleshooting section
- Use the in-app help system

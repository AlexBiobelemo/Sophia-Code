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
│   ├── routes.py            # All route handlers and view functions
│   ├── models.py            # SQLAlchemy database models
│   ├── forms.py             # WTForms for input validation
│   ├── ai_services.py       # AI service router and implementations
│   ├── ai_services_minimax.py # Minimax AI provider implementation
│   ├── badge_system.py      # Gamification and badge logic
│   ├── utils/               # Utility functions and helpers
│   │   └── state_manager.py # Client-side state management
│   ├── static/              # Static assets (CSS, JS, uploads)
│   └── templates/           # Jinja2 HTML templates
├── migrations/              # Alembic database migrations
├── snapshots/               # Automatic database backups
├── config.py                # Application configuration
├── requirements.txt         # Python dependencies
└── run.py                   # Application entry point
```

### Key Components

#### Flask Application Factory

The application uses the Flask application factory pattern in `app/__init__.py`. This allows for:
- Multiple application instances for testing
- Configuration-based setup
- Clean separation of concerns

#### Database Models

All database models are defined in `app/models.py` using SQLAlchemy ORM. Key models include:

- **User**: User accounts with preferences and authentication
- **Snippet**: Code snippets with metadata
- **Collection**: Hierarchical organization for snippets
- **LeetcodeProblem/Solution**: Problem-solving features
- **Note**: Personal note-taking
- **ChatSession/Message**: AI chat functionality
- **Point/Badge**: Gamification system

#### AI Services

The AI functionality is abstracted through `app/ai_services.py`, which provides:
- Multi-provider support (Gemini, Minimax)
- Model tiering and fallback
- Streaming responses
- Token-efficient processing

#### Route Organization

Routes are organized in `app/routes.py` with clear separation:
- Authentication routes
- Snippet management
- Collection management
- AI-powered features
- User profile and settings
- API endpoints

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
    -- ... additional preference fields
);
```

#### Snippet Table
```sql
CREATE TABLE snippet (
    id INTEGER PRIMARY KEY,
    title VARCHAR(140),
    code TEXT,
    description TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES user(id),
    tags VARCHAR(200),
    embedding JSON,
    collection_id INTEGER REFERENCES collection(id),
    language VARCHAR(50) DEFAULT 'python',
    thought_steps JSON
);
```

### Relationships

- User → Snippets (one-to-many)
- User → Collections (one-to-many)
- Collection → Snippets (one-to-many)
- Collection → Sub-collections (self-referential)
- User → Notes (one-to-many)
- User → Chat Sessions (one-to-many)

### Indexes

Key indexes for performance:
- User: username, email, locked_until
- Snippet: timestamp, user_id, title, language
- Collection: timestamp, user_id, parent_id

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

### Snippet Management

#### GET /snippet/{id}
Retrieve a specific snippet.

**Parameters:**
- `id` (path): Snippet ID

**Response:**
```json
{
    "id": 1,
    "title": "Example Snippet",
    "code": "print('Hello World')",
    "language": "python",
    "tags": "example,basic",
    "description": "A simple example"
}
```

#### POST /create_snippet
Create a new code snippet.

**Request Body:**
```json
{
    "title": "New Snippet",
    "code": "def hello():\n    return 'world'",
    "language": "python",
    "description": "Greeting function",
    "tags": "function,greetings",
    "collection_id": 1
}
```

### AI Services

#### POST /api/stream-code-generation
Stream code generation with real-time updates.

**Request Body:**
```json
{
    "prompt": "Write a function to calculate fibonacci numbers",
    "session_id": "uuid-string"
}
```

**Streaming Response:**
```json
{
    "type": "code_chunk",
    "content": "def fibonacci(n):",
    "accumulated": "def fibonacci(n):\n    if n <= 1:",
    "status": "streaming"
}
```

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

1. Set `FLASK_ENV=production` in environment
2. Use a production WSGI server (gunicorn, uwsgi)
3. Configure proper database (PostgreSQL recommended)
4. Set up proper logging
5. Enable HTTPS
6. Configure backup systems

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN flask db upgrade

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
```

## Security Considerations

### Authentication
- Password hashing using Werkzeug
- Account lockout after failed attempts
- Session management with Flask-Login

### Input Validation
- All forms use WTForms validation
- SQL injection prevention via SQLAlchemy
- XSS protection via Jinja2 auto-escaping

### API Security
- Rate limiting on authentication
- CSRF protection on forms
- Input sanitization

### AI Service Security
- API key management via environment variables
- Request validation and size limits
- Error handling without exposing sensitive information

## Performance Optimization

### Database Optimization
- Proper indexing on frequently queried fields
- Pagination for large result sets
- Connection pooling for production

### Caching
- Template caching
- Static asset caching
- Database query result caching

### AI Service Optimization
- Streaming responses for large content
- Model tiering based on task complexity
- Token-efficient prompting

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
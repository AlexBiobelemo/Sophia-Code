# Updates & Version History

## Table of Contents

- [Version 2.0 (Current)](#version-20-current)
- [Version 1.0](#version-10)
- [Migration Guide](#migration-guide)
- [Changelog](#changelog)

---

## Version 2.0 (Current)

**Release Date:** March 2026

### Major Features

#### AI-Powered Enhancements
- **Streaming Code Generation:** Real-time typewriter effect for generated code with micro-animations
- **Multi-Step Thinking:** 4-layer AI pipeline (Architecture → Coder → Tester → Refiner)
- **Enhanced Code Explanation:** Formatted markdown with copy & apply features
- **Smart Tag Suggestions:** AI-powered tag generation with 100+ programming vocabulary
- **Chat Assistant:** Context-aware coding assistant with streaming responses
- **Code Refinement:** Fix bugs based on error messages
- **BYOK Support:** Bring Your Own Key for Google Gemini API

#### UI/UX Improvements
- Modern glassmorphism design system
- Micro-animations throughout the interface
- Syntax-highlighted code blocks with Prism.js
- Custom scrollbars and themes
- Responsive mobile design
- Dark/Light mode toggle
- Tooltip system with configurable delay
- Infinite scroll pagination

#### Performance Optimizations
- Database-level aggregations for points calculation (O(N) → O(1))
- Badge calculation efficiency (80% query reduction)
- Client-side preference caching (60-second cache)
- Throttled DOM observation (250ms)
- requestAnimationFrame integration for AI streaming
- CSS-based markdown styling (60% CPU reduction)

#### Security Enhancements
- CSRF token stripping from query strings
- Security headers (X-Content-Type-Options, X-Frame-Options, etc.)
- Content Security Policy (CSP)
- Request timing and ID tracking
- Account lockout after 5 failed attempts

#### Deployment Features
- **Render Integration:**
  - Auto-migration on startup (`AUTO_MIGRATE`)
  - Self-ping keep-alive (`SELF_PING`)
  - Health check endpoint (`/health`)
- **Backup System:**
  - Automatic server startup backups
  - Post-snippet-save backups (every 5 saves)
  - Manual backup capability
  - Configurable retention (default: 50 backups)

### New Models

#### MultiStepResult Model
Stores multi-step AI thinking process:
- Architecture analysis
- Code generation
- Testing/verification
- Refinement
- Processing time tracking

#### SnippetVersion Model
Version history for snippets:
- Automatic snapshots before edits
- Rollback capability
- Diff view between versions
- Restore functionality

### Database Changes

#### New Indexes
- `ix_user_locked_until` - Fast locked account lookup
- `ix_snippet_language` - Language filtering
- `ix_multi_step_result_*` - Multi-step result queries
- `ix_chat_*` - Chat session queries

#### Schema Updates
- Added `thought_steps` JSON column to Snippet
- Added `gemini_api_key` and `use_own_api_key` to User
- Added `tooltip_delay` preference
- Added `snippet_visibility` setting

### Configuration Changes

#### New Environment Variables
```bash
# Render deployment
AUTO_MIGRATE=1          # Auto-run migrations on startup
SELF_PING_ENABLED=1     # Enable keep-alive pings
RENDER_EXTERNAL_URL=    # Your Render app URL

# AI Configuration
AI_REQUEST_TIMEOUT_SECONDS=300
GEMINI_API_KEY=

# Security
SESSION_COOKIE_SECURE=1
REMEMBER_COOKIE_SECURE=1
WTF_CSRF_SSL_STRICT=False
```

### API Changes

#### New Endpoints
- `POST /api/stream-code-generation` - Streaming code generation
- `POST /generate_multi_step` - Multi-step thinking generation
- `GET /get_multi_step_result/<result_id>` - Retrieve multi-step results
- `GET /multi_step_results/<result_id>` - Display multi-step results
- `POST /save_multi_step_as_snippet` - Save multi-step results
- `POST /api/save_streaming_result` - Save streaming results to session
- `GET /snippet/version/<version_id>/diff` - Version diff view
- `POST /snippet/version/<version_id>/restore` - Restore version
- `POST /snippet/<id>/update_code` - Update code with auto-snapshot
- `POST /snippet/<id>/update_description` - Update description
- `GET /health` - Health check endpoint

#### Modified Endpoints
- `GET /index` - Now supports infinite scroll with `partial=1` parameter
- `POST /create_snippet` - Now handles session-based code storage

### Breaking Changes

#### For Upgraders from v1.x

1. **Database Migration Required:**
   ```bash
   flask db upgrade
   ```

2. **Environment Variables:**
   - `SECRET_KEY` is now required
   - `GEMINI_API_KEY` moved to environment/config

3. **API Key Configuration:**
   - Users can now save personal API keys in settings
   - App-level key configured via `GEMINI_API_KEY` env var

4. **Session Storage:**
   - Generated code now stored in session (not URL parameters)
   - Avoids URL size limits for large code blocks

---

## Version 1.0

**Release Date:** Initial release

### Core Features

- User authentication with Flask-Login
- Code snippet CRUD operations
- Collection organization (nested)
- Basic AI code generation
- AI code explanation
- AI code formatting
- Tag suggestions
- Notes system
- Simple search
- Export functionality
- Basic gamification (points, badges)

### Tech Stack

- Flask backend
- SQLite database
- Bootstrap frontend
- Google Gemini AI integration

---

## Migration Guide

### From v1.x to v2.0

#### 1. Backup Your Data
```bash
python database_backup.py create
```

#### 2. Update Dependencies
```bash
pip install -r requirements.txt
```

New dependencies in v2.0:
- `google-genai`
- `APScheduler`
- `gTTS`
- `gunicorn`

#### 3. Run Migrations
```bash
flask db upgrade
```

#### 4. Initialize Badges (if not exists)
```bash
python -c "from app.badge_system import initialize_default_badges; from app import create_app, db; app = create_app(); with app.app_context(): initialize_default_badges()"
```

#### 5. Update Environment Variables
Add to your `.env` file:
```bash
SECRET_KEY=your_secret_key_here
GEMINI_API_KEY=your_gemini_api_key_here
FLASK_DEBUG=0  # Set to 1 for development
```

#### 6. Clear Browser Cache
Due to new static assets and caching strategies.

#### 7. Test AI Features
Verify your API key works:
1. Go to User Settings
2. Test AI model selection
3. Optionally configure BYOK

---

## Changelog

### [2.0.0] - March 2026

#### Added
- Multi-step thinking AI generation with 4 layers
- Streaming code display with typewriter effect
- BYOK (Bring Your Own Key) support
- Snippet version history with rollback
- Diff view for snippet versions
- Semantic search with embeddings
- Chat assistant with conversation history
- Code refinement based on error messages
- Infinite scroll pagination
- Session-based code storage
- Auto-backup system
- Render deployment integration
- Self-ping keep-alive for production
- Security headers and CSP
- CSRF token stripping from URLs
- Request timing and ID tracking
- Tooltip system with caching
- Dark mode theme
- Custom language support
- Model tiering (flash, flash-lite, pro)
- Streak calculation and days active tracking

#### Changed
- Modernized UI with glassmorphism design
- Improved AI service with retry logic and timeouts
- Optimized database queries (points, badges)
- Enhanced error handling throughout
- Updated AI models to Gemini 2.5 series
- Improved code explanation formatting
- Better mobile responsiveness

#### Fixed
- SQLite async dialect issue (aiosqlite patch)
- Database lock errors with proper connection handling
- URL size limits with session storage
- High CPU usage during AI streaming
- Tooltip performance with throttling
- Badge calculation redundant queries

#### Deprecated
- URL-based code passing (use session-based)
- Simple code generation (use multi-step for complex tasks)

#### Removed
- None (backward compatible with v1.x data)

---

## Upgrade Path

### Recommended Upgrade Steps

1. **Test Environment First:**
   - Clone production database to test environment
   - Run migrations on test
   - Verify all features work

2. **Schedule Downtime:**
   - Plan for maintenance window
   - Notify users if applicable

3. **Execute Upgrade:**
   ```bash
   # Backup
   python database_backup.py create
   
   # Pull updates
   git pull origin main
   
   # Update dependencies
   pip install -r requirements.txt
   
   # Run migrations
   flask db upgrade
   
   # Restart application
   # (depends on deployment method)
   ```

4. **Verify:**
   - Test login
   - Test AI features
   - Check snippet viewing/creation
   - Verify backups running

5. **Monitor:**
   - Watch logs for errors
   - Check database performance
   - Monitor AI API usage

---

## Support

For upgrade issues:
1. Check [Troubleshooting.md](Troubleshooting.md)
2. Review migration steps above
3. Check GitHub issues
4. Contact support

## Future Roadmap

### Planned for v2.1
- [ ] Public snippet sharing
- [ ] Collaborative collections
- [ ] Advanced analytics dashboard
- [ ] Mobile app (React Native)
- [ ] VS Code extension
- [ ] API for third-party integrations
- [ ] Webhook support
- [ ] Advanced search filters
- [ ] Code snippet comments/discussions
- [ ] Team/organization support

### Under Consideration
- PostgreSQL support for larger deployments
- Redis caching layer
- Full-text search with Elasticsearch
- OAuth2 authentication (Google, GitHub)
- Two-factor authentication
- Email notifications
- Scheduled exports
- Integration with GitHub Gists
- Import from other snippet managers

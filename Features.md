# Features

## Core Capabilities

### User Authentication and Profile Management
**Description:** Allows users to register, log in, manage their profile details (username, email, avatar), and change passwords securely.
![Screenshot](Screenshot/Screenshot 2025-11-25 123254.png)
[Profile Management Video](Videos/Profile Management.mp4)
**Technical Implementation:** Flask-Login for session management, SQLAlchemy for user data persistence, password hashing using Werkzeug.

### Code Snippet Management
**Description:** Users can create, view, edit, and delete code snippets. Snippets can be categorized into collections and tagged for easy retrieval. Supports syntax highlighting for a wide range of programming languages.
**Technical Implementation:** SQLAlchemy models for `Snippet` and `Collection`, WTForms for input validation, Pygments for syntax highlighting in frontend.
[Code Snippet Management 1 Video](Videos/Code Snippet Management 1.mp4)
[Code Snippet Management 2 Video](Videos/Code Snippet Management 2.mp4)

### Collection Organization
**Description:** Provides hierarchical organization for snippets through nested collections. Users can rename, delete, and reorder collections.
**Technical Implementation:** `Collection` model with `parent_id` for nesting, drag-and-drop reordering implemented with JavaScript and a backend API endpoint.
[Collection Organization Video](Videos/Coolection Organization.mp4)

### LeetCode Problem Integration
**Description:** Users can add programming problems (e.g., LeetCode style) with titles, descriptions, difficulty levels, and tags.
**Technical Implementation:** SQLAlchemy model for `LeetcodeProblem`, WTForms for problem creation.

### AI-Powered Code Generation
**Description:** Integrates with an AI service (Google Gemini) to generate new code snippets from natural language prompts, explain existing code, suggest relevant tags, and refine code based on feedback.
**Technical Implementation:** Google Gemini API integration (via `app/ai_services.py`), Celery for asynchronous task processing to avoid blocking the main Flask app during AI calls.
[Code Gen Video](Videos/Code Gen.mp4)

### AI Code Formatting
**Description:** Utilizes AI to automatically format code with proper indentation, spacing, and style to ensure consistency and readability.
**Technical Implementation:** Google Gemini API (via `app/ai_services.py`).

### AI-Powered Solution Generation
**Description:** Integrates with an AI service (Google Gemini) to generate solutions for added programming problems in various languages based on problem descriptions, and to explain and classify these solutions.
**Technical Implementation:** Google Gemini API integration (via `app/ai_services.py`).

### Solution Approval Workflow
**Description:** Generated AI solutions can be reviewed and approved by users, storing the approved solutions for future reference.
**Technical Implementation:** Boolean flag on `Solution` model for approval status, UI elements for approval/rejection.

### Bulk Actions
**Description:** Allows users to perform operations like deleting, copying, or moving multiple snippets simultaneously.
**Technical Implementation:** Frontend JavaScript handles selection and sends bulk requests to a dedicated backend endpoint.
[Bulk Operations Video](Videos/Bulk Operations.mp4)

## Performance Specifications
- **Load Limits:** Designed for individual users or small teams. AI generation tasks are offloaded to a background worker (Celery) to prevent blocking the main application.
- **Browser Compatibility:** Tested on modern web browsers (Chrome, Firefox, Safari, Edge).
- **Database:** SQLite is suitable for small to medium-sized datasets. For larger deployments, the SQLAlchemy ORM allows for easy migration to PostgreSQL or MySQL.


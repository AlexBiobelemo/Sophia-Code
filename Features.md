# Features

## Core Capabilities

### User Authentication and Profile Management
**Description:** Allows users to register, log in, manage their profile details (username, email, avatar), and change passwords securely.
**Technical Implementation:** Flask-Login for session management, SQLAlchemy for user data persistence, password hashing using Werkzeug.

#### Demo: Profile Management (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Profile%20Management.gif" alt="Profile management GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Profile%20Management.mp4" controls loop muted width="600"></video>
</div>

---

### Code Snippet Management
**Description:** Users can create, view, edit, and delete code snippets. Snippets can be categorized into collections and tagged for easy retrieval. Supports syntax highlighting for a wide range of programming languages.
**Technical Implementation:** SQLAlchemy models for `Snippet` and `Collection`, WTForms for input validation, Pygments for syntax highlighting in frontend.

#### Demo: Snippet Management (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Snippet%20Management%201.gif" alt="Code snippet management 1 GIF" width="600">
</div>
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Snippet%20Management%202.gif" alt="Code snippet management 2 GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Snippet%20Management%201.mp4" controls loop muted width="600"></video>
</div>

---

### Collection Organization
**Description:** Provides hierarchical organization for snippets through nested collections. Users can rename, delete, and reorder collections.
**Technical Implementation:** `Collection` model with `parent_id` for nesting, drag-and-drop reordering implemented with JavaScript and a backend API endpoint.

#### Demo: Collection Organization (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Coolection%20Organization.gif" alt="Collection Organization GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Coolection%20Organization.mp4" controls loop muted width="600"></video>
</div>

---

### LeetCode Problem Integration
**Description:** Users can add programming problems (e.g., LeetCode style) with titles, descriptions, difficulty levels, and tags.
**Technical Implementation:** SQLAlchemy model for `LeetcodeProblem`, WTForms for problem creation.

---

### AI-Powered Code Generation
**Description:** Integrates with an AI service (Google Gemini) to generate new code snippets from natural language prompts, explain existing code, suggest relevant tags, and refine code based on feedback.
**Technical Implementation:** Google Gemini API integration (via `app/ai_services.py`), Celery for asynchronous task processing to avoid blocking the main Flask app during AI calls.

#### Demo: Code Generation (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Generation-1.gif" alt="Code generation GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Generation.mp4" controls loop muted width="600"></video>
</div>

---

### AI Code Formatting
**Description:** Utilizes AI to automatically format code with proper indentation, spacing, and style to ensure consistency and readability.
**Technical Implementation:** Google Gemini API (via `app/ai_services.py`).

#### Demo: Code Formatting (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Formatting.gif" alt="Code formatting GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Code%20Formatting.mp4" controls loop muted width="600"></video>
</div>

---

### AI-Powered Solution Generation
**Description:** Integrates with an AI service (Google Gemini) to generate solutions for added programming problems in various languages based on problem descriptions, and to explain and classify these solutions.
**Technical Implementation:** Google Gemini API integration (via `app/ai_services.py`).

---

### Solution Approval Workflow
**Description:** Generated AI solutions can be reviewed and approved by users, storing the approved solutions for future reference.
**Technical Implementation:** Boolean flag on `Solution` model for approval status, UI elements for approval/rejection.

---

### Bulk Actions
**Description:** Allows users to perform operations like deleting, copying, or moving multiple snippets simultaneously.
**Technical Implementation:** Frontend JavaScript handles selection and sends bulk requests to a dedicated backend endpoint.

#### Demo: Bulk Operations (GIF/Video)
<div style="text-align: center;">
<img src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Bulk%20Operations.gif" alt="Bulk operations GIF" width="600">
</div>
<br>
<div style="text-align: center;">
<video src="https://raw.githubusercontent.com/AlexBiobelemo/Sophia---Organize-share-generate-code-snippets./main/Videos/Bulk%20Operations.mp4" controls loop muted width="600"></video>
</div>

---

## Performance Specifications
- **Load Limits:** Designed for individual users or small teams. AI generation tasks are offloaded to a background worker (Celery) to prevent blocking the main application.
- **Browser Compatibility:** Tested on modern web browsers (Chrome, Firefox, Safari, Edge).
- **Database:** SQLite is suitable for small to medium-sized datasets. For larger deployments, the SQLAlchemy ORM allows for easy migration to PostgreSQL or MySQL.

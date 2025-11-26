# Project Sophia

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)

Project Sophia is a knowledge management system designed to help developers organize and share code snippets, solutions, and technical insights. It aims to streamline the process of storing and retrieving valuable programming knowledge.

## About the Project
Project Sophia addresses the common problem developers face in managing an ever-growing collection of code snippets, solutions to problems, and general technical knowledge. It provides a structured environment to:
- Create and categorize code snippets by language and collection.
- Solve and approve LeetCode-style problems.
- Generate code using AI based on prompts.
- Facilitate team collaboration and knowledge sharing.

### Tech Stack
- **Backend:** Flask (Python)
- **Database:** SQLite (SQLAlchemy ORM)
- **Frontend:** HTML, CSS (Bootstrap), JavaScript
- **AI Integration:** Google Gemini API for code generation, explanation, formatting, and tagging


## Getting Started

### Prerequisites
- Python 3.9+
- pip (Python package installer)
- Git

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/AlexBiobelemo/Project-Sophia.git
    cd Project-Sophia
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    \venv\Scripts\activate  # On Windows
    source venv/bin/activate # On macOS/Linux
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the root directory and add the following:
    ```
    SECRET_KEY='your_secret_key_here'
    DATABASE_URL='sqlite:///app.db'
    GEMINI_API_KEY='your_gemini_api_key_here'
    FLASK_APP=run.py
    FLASK_ENV=development
    ```
    Replace `'your_gemini_api_key_here'` with actual values.

5.  **Initialize the database:**
    ```bash
    flask db upgrade
    ```

### Usage

To run the application:
```bash
flask run 
```
The application will typically be available at `http://127.0.0.1:5000/`. Open this URL in your web browser.


## Contact/Acknowledgments
- Developed by Alex Biobelemo
- Inspired by personal needs for better code organization.

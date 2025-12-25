"""Defines the forms used in the Sophia application."""

import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, BooleanField, SubmitField,
                   TextAreaField, SelectField)
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from flask_wtf.file import FileField, FileAllowed

from app import db
from app.models import User, LeetcodeProblem


class RegistrationForm(FlaskForm):
    """Form for new user registration."""
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register', render_kw={'id': 'submit-button'})

    def validate_username(self, username):
        """Checks if the username is already taken."""
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        """Checks if the email is already in use."""
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')


class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In', render_kw={'id': 'submit-button'})


class SnippetForm(FlaskForm):
    """Form for creating and editing a code snippet."""
    title = StringField('Title', validators=[
                        DataRequired(), Length(min=1, max=140)])
    collection = SelectField('Collection (Optional)', coerce=int)
    language = SelectField('Language', choices=[
        # General purpose languages
        ('python', 'Python'),
        ('java', 'Java'),
        ('cpp', 'C++'),
        ('c', 'C'),
        ('csharp', 'C#'),
        ('javascript', 'JavaScript'),
        ('typescript', 'TypeScript'),
        ('go', 'Go'),
        ('kotlin', 'Kotlin'),
        ('swift', 'Swift'),
        ('ruby', 'Ruby'),
        ('rust', 'Rust'),
        ('php', 'PHP'),
        ('scala', 'Scala'),
        ('r', 'R'),
        ('julia', 'Julia'),
        ('matlab', 'MATLAB'),
        ('dart', 'Dart'),
        # Scripting / shell
        ('bash', 'Bash/Shell'),
        ('powershell', 'PowerShell'),
        # Web / markup / data
        ('html', 'HTML'),
        ('css', 'CSS'),
        ('markdown', 'Markdown'),
        ('json', 'JSON'),
        ('yaml', 'YAML'),
        ('xml', 'XML'),
        ('graphql', 'GraphQL'),
        # SQL and dialects
        ('sql', 'SQL (Generic)'),
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('sqlite', 'SQLite'),
        ('plsql', 'Oracle PL/SQL'),
        ('tsql', 'T-SQL (SQL Server)'),
        # Data/ML ecosystems (treated as Python for highlighting)
        ('pandas', 'Pandas (Python)'),
        ('numpy', 'NumPy (Python)'),
        ('scipy', 'SciPy (Python)'),
        ('sklearn', 'scikit-learn (Python)'),
        ('pytorch', 'PyTorch (Python)'),
        ('tensorflow', 'TensorFlow (Python)'),
        # Functional & Modern Niche
        ('haskell', 'Haskell'),
        ('elixir', 'Elixir'),
        ('clojure', 'Clojure'),
        ('fsharp', 'F#'),
        ('ocaml', 'OCaml'),
        ('erlang', 'Erlang'),
        ('zig', 'Zig'),             # Rapidly growing systems language
        ('solidity', 'Solidity'),   # Blockchain/Smart Contracts

        # Scripting, Game Dev & Embedded
        ('perl', 'Perl'),
        ('lua', 'Lua'),             # Standard for game modding/embedded
        ('groovy', 'Groovy'),       # Critical for Jenkins/Gradle
        ('gdscript', 'GDScript'),   # Godot Engine
        ('tcl', 'Tcl'),

        # Enterprise, Legacy & Systems
        ('objectivec', 'Objective-C'), # Apple ecosystem
        ('visualbasic', 'Visual Basic .NET'), # Microsoft legacy
        ('vba', 'VBA'),             # Excel/Office Macros
        ('fortran', 'Fortran'),     # Scientific computing legacy
        ('cobol', 'COBOL'),         # Banking/Mainframe legacy
        ('pascal', 'Pascal/Delphi'), # Educational / Systems
        ('assembly', 'Assembly'),   # General Assembly (x86/ARM)
        ('abap', 'ABAP'),           # SAP Ecosystem
        ('apex', 'Apex'),           # Salesforce Ecosystem
        ('sas', 'SAS'),             # Analytics for business intelligence

        # Infrastructure, Config & Build Tools
        ('dockerfile', 'Dockerfile'), # Containerization syntax
        ('hcl', 'HCL (Terraform)'), # HashiCorp Configuration Language
        ('makefile', 'Makefile'), # Build automation
        ('toml', 'TOML'), # Configuration file format
        ('ini', 'INI'), # Generic configuration file format
        ('protobuf', 'Protocol Buffers'), # Data serialization

        # Web / Document Extensions
        ('scss', 'SCSS/Sass'),      # CSS Preprocessor
        ('latex', 'LaTeX/TeX'),     # Academic/Math Typesetting
    ])
    description = TextAreaField('Description (Optional)')
    code = TextAreaField('Code', validators=[DataRequired()])
    tags = StringField('Tags (comma-separated)',
                       validators=[Length(max=200)])
    submit = SubmitField('Save Snippet')


class AIGenerationForm(FlaskForm):
    """Form for submitting a prompt to the AI for code generation."""
    prompt = TextAreaField(
        'Describe the code you want to generate',
        validators=[DataRequired(), Length(min=10, max=5000)]
    )
    submit = SubmitField('Generate Code', render_kw={'id': 'submit-button'})


class CollectionForm(FlaskForm):
    """Form for creating or renaming a collection."""
    name = StringField('Collection Name', validators=[
                       DataRequired(), Length(min=1, max=100)])
    parent_collection = SelectField('Parent Collection (Optional)', coerce=int, default=0)
    submit = SubmitField('Create Collection', render_kw={'id': 'submit-button'})


class LeetcodeProblemForm(FlaskForm):
    title = StringField('Problem Title', validators=[DataRequired(), Length(min=1, max=255)])
    description = TextAreaField('Problem Description', validators=[DataRequired()])
    difficulty = SelectField('Difficulty', choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], validators=[DataRequired()])
    tags = StringField('Tags (comma-separated)', description='e.g., array, dynamic-programming')
    leetcode_url = StringField('LeetCode URL', validators=[Length(max=500)])
    submit = SubmitField('Add Problem', render_kw={'id': 'submit-button'})

    def validate_title(self, title):
        problem = db.session.scalar(sa.select(LeetcodeProblem).where(LeetcodeProblem.title == title.data))
        if problem is not None:
            raise ValidationError('A problem with this title already exists.')


class GenerateSolutionForm(FlaskForm):
    problem = SelectField('Select Problem', coerce=int, validators=[DataRequired()])
    language = SelectField('Solution Language', choices=[
        ('python', 'Python'),
        ('java', 'Java'),
        ('cpp', 'C++'),
        ('c', 'C'),
        ('csharp', 'C#'),
        ('javascript', 'JavaScript'),
        ('typescript', 'TypeScript'),
        ('go', 'Go'),
        ('kotlin', 'Kotlin'),
        ('swift', 'Swift'),
        ('ruby', 'Ruby'),
        ('rust', 'Rust'),
        ('php', 'PHP'),
        ('scala', 'Scala'),
        # SQL and dialects (for DB problems)
        ('sql', 'SQL (Generic)'),
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('sqlite', 'SQLite'),
        ('plsql', 'Oracle PL/SQL'),
        ('tsql', 'T-SQL (SQL Server)'),

        # Functional & Modern Niche
        ('haskell', 'Haskell'),
        ('elixir', 'Elixir'),
        ('clojure', 'Clojure'),
        ('fsharp', 'F#'),
        ('ocaml', 'OCaml'),
        ('erlang', 'Erlang'),
        ('zig', 'Zig'),             # Rapidly growing systems language
        ('solidity', 'Solidity'),   # Blockchain/Smart Contracts

        # Scripting, Game Dev & Embedded
        ('perl', 'Perl'),
        ('lua', 'Lua'),             # Standard for game modding/embedded
        ('groovy', 'Groovy'),       # Critical for Jenkins/Gradle
        ('gdscript', 'GDScript'),   # Godot Engine
        ('tcl', 'Tcl'),

        # Enterprise, Legacy & Systems
        ('objectivec', 'Objective-C'), # Apple ecosystem
        ('visualbasic', 'Visual Basic .NET'), # Microsoft legacy
        ('vba', 'VBA'),             # Excel/Office Macros
        ('fortran', 'Fortran'),     # Scientific computing legacy
        ('cobol', 'COBOL'),         # Banking/Mainframe legacy
        ('pascal', 'Pascal/Delphi'), # Educational / Systems
        ('assembly', 'Assembly'),   # General Assembly (x86/ARM)
        ('abap', 'ABAP'),           # SAP Ecosystem
        ('apex', 'Apex'),           # Salesforce Ecosystem
        ('sas', 'SAS'),             # Analytics for business intelligence

        # Infrastructure, Config & Build Tools
        ('dockerfile', 'Dockerfile'), # Containerization syntax
        ('hcl', 'HCL (Terraform)'), # HashiCorp Configuration Language
        ('makefile', 'Makefile'), # Build automation
        ('toml', 'TOML'), # Configuration file format
        ('ini', 'INI'), # Generic configuration file format
        ('protobuf', 'Protocol Buffers'), # Data serialization

        # Web / Document Extensions
        ('scss', 'SCSS/Sass'),      # CSS Preprocessor
        ('latex', 'LaTeX/TeX'),     # Academic/Math Typesetting
    ], validators=[DataRequired()])
    submit = SubmitField('Generate Solution', render_kw={'id': 'submit-button'})


class ApproveSolutionForm(FlaskForm):
    approve = BooleanField('Approve Solution')
    submit = SubmitField('Submit Approval', render_kw={'id': 'submit-button'})


class BulkActionForm(FlaskForm):
    """Form for bulk operations (delete, copy, move) on snippets."""
    snippet_ids = StringField('Snippet IDs', validators=[DataRequired()])
    action = SelectField('Action', choices=[
        ('delete', 'Delete'),
        ('copy', 'Copy'),
        ('move', 'Move')
    ], validators=[DataRequired()])
    target_collection = SelectField('Target Collection (for copy/move)', coerce=int, default=0)
    submit = SubmitField('Perform Bulk Action', render_kw={'id': 'submit-button'})

    def validate_snippet_ids(self, field):
        try:
            ids = [int(s_id) for s_id in field.data.split(',') if s_id]
            if not ids:
                raise ValueError("No snippet IDs provided.")
        except ValueError:
            raise ValidationError('Invalid snippet IDs format.')

class MoveSnippetForm(FlaskForm):
    """Form for moving or copying a snippet to a different collection."""
    target_collection = SelectField('Move to Collection', coerce=int, validators=[DataRequired()])
    action = SelectField('Action', choices=[('move', 'Move'), ('copy', 'Copy')], validators=[DataRequired()])
    submit = SubmitField('Perform Action', render_kw={'id': 'submit-button'})


class EditProfileForm(FlaskForm):
    """Form to edit account details (username, email, and password)."""
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    avatar = FileField('Avatar', validators=[FileAllowed(['png','jpg','jpeg','gif','webp'], 'Images only')])
    current_password = PasswordField('Current Password (required to save changes)', validators=[DataRequired()])
    new_password = PasswordField('New Password (optional)')
    new_password2 = PasswordField('Repeat New Password', validators=[EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Save Changes', render_kw={'id': 'submit-button'})

    def validate_new_password(self, field):
        pwd = field.data or ''
        if not pwd:
            return
        errs = []
        if len(pwd) < 8: errs.append('≥8 characters')
        if not any(c.islower() for c in pwd): errs.append('lowercase')
        if not any(c.isupper() for c in pwd): errs.append('uppercase')
        if not any(c.isdigit() for c in pwd): errs.append('digit')
        if not any(c in '!@#$%^&*()-_=+[]{};:\\|,.<>/?' for c in pwd): errs.append('symbol')
        if errs:
            raise ValidationError('Password needs: ' + ', '.join(errs))


class NoteForm(FlaskForm):
    """Form for creating and editing a personal note."""
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=140)])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Save Note')


class SettingsForm(FlaskForm):
    """Form for user settings and preferences."""
    # AI Preferences
    preferred_ai_model = SelectField('Preferred AI Model', choices=[
        ('gemini-2.5-flash', 'Gemini 2.5 Flash (Fast, Good for simple tasks)'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro (Balanced, Good for most tasks)'),
        ('gemini-3-pro', 'Gemini 3 Pro (Advanced, Best for complex tasks)'),
        ('minimax-m2', 'Minimax M2 (Free, Good for code generation)')
    ], validators=[DataRequired()])
    
    code_generation_style = SelectField('Code Generation Style', choices=[
        ('balanced', 'Balanced (Good explanations with moderate detail)'),
        ('detailed', 'Detailed (Comprehensive explanations and comments)'),
        ('concise', 'Concise (Minimal explanations, focus on code)')
    ], validators=[DataRequired()])
    
    auto_explain_code = BooleanField('Automatically explain generated code')
    
    # UI Preferences
    show_line_numbers = BooleanField('Show line numbers in code snippets')
    enable_animations = BooleanField('Enable UI animations and transitions')
    enable_tooltips = BooleanField('Enable tooltips throughout the application')
    tooltip_delay = SelectField('Tooltip delay (seconds)', choices=[
        (1, '1 second'),
        (2, '2 seconds'),
        (3, '3 seconds'),
        (5, '5 seconds'),
        (10, '10 seconds')
    ], validators=[DataRequired()])
    dark_mode = BooleanField('Use dark mode theme')
    
    # Privacy & Sharing
    public_profile = BooleanField('Make profile public')
    show_activity = BooleanField('Show activity on public profile')
    snippet_visibility = SelectField('Default snippet visibility', choices=[
        ('private', 'Private (Only you can see)'),
        ('public', 'Public (Anyone can see)'),
        ('friends', 'Friends only (If social features added)')
    ], validators=[DataRequired()])
    
    # Notifications
    email_notifications = BooleanField('Receive email notifications')
    
    # Auto-save
    auto_save_snippets = BooleanField('Auto-save snippets while editing')
    
    submit = SubmitField('Save Settings', render_kw={'id': 'submit-button'})

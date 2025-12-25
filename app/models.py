"""Database models for the Sophia application."""

from datetime import datetime
import sqlalchemy as sa
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    """
    User loader callback for Flask-Login.
    Reloads the user object from the user ID stored in the session.
    """
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    """Represents a user in the database."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(256))
    avatar_filename = db.Column(db.String(255), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    last_failed_login = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    # AI and User Preferences
    preferred_ai_model = db.Column(db.String(50), default='gemini-2.5-flash')
    code_generation_style = db.Column(db.String(50), default='balanced')  # balanced, detailed, concise
    auto_explain_code = db.Column(db.Boolean, default=True)
    show_line_numbers = db.Column(db.Boolean, default=True)
    enable_animations = db.Column(db.Boolean, default=True)
    enable_tooltips = db.Column(db.Boolean, default=True)
    tooltip_delay = db.Column(db.Integer, default=3)  # Delay in seconds before tooltip appears
    dark_mode = db.Column(db.Boolean, default=True)
    email_notifications = db.Column(db.Boolean, default=True)
    auto_save_snippets = db.Column(db.Boolean, default=True)
    public_profile = db.Column(db.Boolean, default=False)
    show_activity = db.Column(db.Boolean, default=True)
    snippet_visibility = db.Column(db.String(20), default='private')  # private, public, friends

    snippets = db.relationship('Snippet', backref='author', lazy='dynamic')
    collections = db.relationship('Collection', backref='owner', lazy='dynamic')
    leetcode_problems = db.relationship('LeetcodeProblem', backref='author', lazy='dynamic')
    leetcode_solutions = db.relationship('LeetcodeSolution', backref='contributor', lazy='dynamic')
    points = db.relationship('Point', backref='user', lazy='dynamic')
    badges = db.relationship('UserBadge', backref='user', lazy='dynamic')
    notes = db.relationship('Note', backref='author', lazy='dynamic')

    __table_args__ = (
        db.Index('ix_user_username', 'username', unique=True),
        db.Index('ix_user_email', 'email', unique=True),
        db.Index('ix_user_locked_until', 'locked_until'), # Index for quick lookup of locked accounts
    )

    def get_total_points(self):
        return sum(point.points for point in self.points)

    def set_password(self, password):
        """Hashes and sets the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the user's hashed password."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        """String representation of the User object."""
        return f'<User {self.username}>'


    def award_badge(self, badge_name):
        """Awards a badge to the user if not already earned."""
        badge = db.session.scalar(sa.select(Badge).where(Badge.name == badge_name))
        if badge and not db.session.scalar(sa.select(UserBadge).where(UserBadge.user_id == self.id, UserBadge.badge_id == badge.id)):
            user_badge = UserBadge(user_id=self.id, badge_id=badge.id)
            db.session.add(user_badge)
            db.session.commit()
            return True
        return False


class Collection(db.Model):
    """Represents a user-defined collection for organizing snippets."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, default=0) # For custom ordering of collections
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parent_id = db.Column(db.Integer, db.ForeignKey('collection.id'), nullable=True) # For sub-collections
    snippets = db.relationship('Snippet', backref='collection', lazy='dynamic')
    children = db.relationship('Collection', backref=db.backref('parent', remote_side=[id]), lazy='dynamic') # For hierarchical collections

    __table_args__ = (
        db.Index('ix_collection_timestamp', 'timestamp'),
        db.Index('ix_collection_user_id', 'user_id'),
        db.Index('ix_collection_parent_id', 'parent_id'),
    )

    def __repr__(self):
        """String representation of the Collection object."""
        return f'<Collection {self.name}>'


class Snippet(db.Model):
    """Represents a code snippet in the database."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140))
    code = db.Column(db.Text)
    description = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    tags = db.Column(db.String(200), nullable=True)
    embedding = db.Column(db.JSON, nullable=True)
    collection_id = db.Column(db.Integer, db.ForeignKey('collection.id'), nullable=True)
    language = db.Column(db.String(50), nullable=False, default='python')
    thought_steps = db.Column(db.JSON, nullable=True)  # Stores multi-step thinking process

    versions = db.relationship('SnippetVersion', backref='snippet', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_snippet_timestamp', 'timestamp'),
        db.Index('ix_snippet_user_id', 'user_id'),
        db.Index('ix_snippet_title', 'title'),
        db.Index('ix_snippet_language', 'language'),
    )

    def generate_and_set_embedding(self):
        """Generates and saves a vector embedding for the snippet's content."""
        # Import locally to avoid circular dependencies at startup
        from app import ai_services

        # Combine the most important text fields for a rich embedding
        text_to_embed = f"Title: {self.title}\nDescription: {self.description}\nCode: {self.code}"
        self.embedding = ai_services.generate_embedding(
            text_to_embed, task_type="RETRIEVAL_DOCUMENT")

    def __repr__(self):
        """String representation of the Snippet object."""
        return f'<Snippet {self.title}>'


class SnippetVersion(db.Model):
    """Immutable snapshot of a snippet at a point in time for history and rollback."""
    id = db.Column(db.Integer, primary_key=True)
    snippet_id = db.Column(db.Integer, db.ForeignKey('snippet.id'), nullable=False)
    title = db.Column(db.String(140))
    description = db.Column(db.Text, nullable=True)
    code = db.Column(db.Text)
    language = db.Column(db.String(50), nullable=False, default='python')
    tags = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_snippet_version_snippet_id', 'snippet_id'),
        db.Index('ix_snippet_version_created_at', 'created_at'),
    )

    def __repr__(self):
        return f'<SnippetVersion {self.id} of snippet {self.snippet_id}>'


class Point(db.Model):
    """Represents points awarded to a user for gamification."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    activity = db.Column(db.String(255), nullable=False) # e.g., "Snippet Created", "Solution Approved"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_point_user_id', 'user_id'),
        db.Index('ix_point_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f'<Point {self.points} for {self.user.username} ({self.activity})>'


class Badge(db.Model):
    """Represents a badge that can be awarded to users."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), nullable=True) # URL to badge icon
    # Criteria for earning the badge (e.g., 'snippets_created:10', 'solutions_approved:5')
    criteria = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_badge_name', 'name', unique=True),
    )

    def __repr__(self):
        return f'<Badge {self.name}>'


class UserBadge(db.Model):
    """Associates users with earned badges."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    badge = db.relationship('Badge', backref='user_badges')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'badge_id', name='uq_user_badge'),
        db.Index('ix_user_badge_user_id', 'user_id'),
        db.Index('ix_user_badge_badge_id', 'badge_id'),
    )

    def __repr__(self):
        return f'<User {self.user.username} earned {self.badge.name}>'



class LeetcodeProblem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(20), nullable=False) # Easy, Medium, Hard
    tags = db.Column(db.String(255), nullable=True) # e.g., "array, dynamic-programming"
    leetcode_url = db.Column(db.String(500), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # User who added the problem

    solutions = db.relationship('LeetcodeSolution', backref='problem', lazy='dynamic')

    __table_args__ = (
        db.Index('ix_leetcode_problem_title', 'title', unique=True),
        db.Index('ix_leetcode_problem_difficulty', 'difficulty'),
        db.Index('ix_leetcode_problem_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f'<LeetcodeProblem {self.title}>'


class LeetcodeSolution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey('leetcode_problem.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id')) # User who contributed the solution
    solution_code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False, default='python')
    explanation = db.Column(db.Text, nullable=True)
    classification = db.Column(db.String(255), nullable=True) # e.g., "Dynamic Programming, BFS"
    approved = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    embedding = db.Column(db.JSON, nullable=True) # For semantic search of solutions

    __table_args__ = (
        db.Index('ix_leetcode_solution_problem_id', 'problem_id'),
        db.Index('ix_leetcode_solution_user_id', 'user_id'),
        db.Index('ix_leetcode_solution_approved', 'approved'),
        db.Index('ix_leetcode_solution_timestamp', 'timestamp'),
    )

    def generate_and_set_embedding(self):
        from app import ai_services
        text_to_embed = f"Problem: {self.problem.title}\nSolution: {self.solution_code}\nExplanation: {self.explanation}"
        self.embedding = ai_services.generate_embedding(
            text_to_embed, task_type="RETRIEVAL_DOCUMENT")

    def __repr__(self):
        return f'<LeetcodeSolution for {self.problem.title} by {self.contributor.username}>'


class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, default='New Chat')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('ChatMessage', backref='session', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_chat_session_user_id', 'user_id'),
        db.Index('ix_chat_session_updated_at', 'updated_at'),
    )

    def __repr__(self):
        return f'<ChatSession {self.id} {self.title}>'


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_chat_message_session_id', 'session_id'),
        db.Index('ix_chat_message_created_at', 'created_at'),
    )

    def __repr__(self):
        return f'<ChatMessage {self.role} {self.created_at}>'


class Note(db.Model):
    """Represents a user's personal note in the database."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    __table_args__ = (
        db.Index('ix_note_timestamp', 'timestamp'),
        db.Index('ix_note_user_id', 'user_id'),
    )

    def __repr__(self):
        return f'<Note {self.title}>'


class MultiStepResult(db.Model):
    """Represents multi-step AI thinking results for code generation."""
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.String(36), nullable=False, unique=True)  # UUID string
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    test_cases = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='processing')  # processing, completed, error
    error_message = db.Column(db.Text, nullable=True)
    
    # Multi-step thinking layers
    layer1_architecture = db.Column(db.Text, nullable=True)
    layer2_coder = db.Column(db.Text, nullable=True)
    layer3_tester = db.Column(db.Text, nullable=True)
    layer4_refiner = db.Column(db.Text, nullable=True)
    
    # Final results
    final_code = db.Column(db.Text, nullable=True)
    processing_time = db.Column(db.Float, nullable=True)  # in seconds
    
    # Timestamps
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', backref='multi_step_results')
    
    __table_args__ = (
        db.Index('ix_multi_step_result_result_id', 'result_id'),
        db.Index('ix_multi_step_result_user_id', 'user_id'),
        db.Index('ix_multi_step_result_timestamp', 'timestamp'),
        db.Index('ix_multi_step_result_status', 'status'),
    )

    def __repr__(self):
        return f'<MultiStepResult {self.result_id} ({self.status})>'

    def to_dict(self):
        """Convert the model instance to a dictionary for JSON serialization."""
        return {
            'id': self.id,
            'result_id': self.result_id,
            'user_id': self.user_id,
            'prompt': self.prompt,
            'test_cases': self.test_cases,
            'status': self.status,
            'error_message': self.error_message,
            'layer1_architecture': self.layer1_architecture,
            'layer2_coder': self.layer2_coder,
            'layer3_tester': self.layer3_tester,
            'layer4_refiner': self.layer4_refiner,
            'final_code': self.final_code,
            'processing_time': self.processing_time,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

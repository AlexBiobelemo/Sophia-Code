"""Badge system initialization and management for Project Sophia."""

import sqlalchemy as sa
from app import db
from app.models import Badge


def initialize_default_badges():
    """Initialize default badges if they don't exist."""
    default_badges = [
        # Snippet-related badges
        {
            "name": "First Snippet",
            "description": "Created your first code snippet",
            "criteria": "snippets:1",
            "image_url": "bi-code-slash"
        },
        {
            "name": "Code Apprentice",
            "description": "Created 5 code snippets",
            "criteria": "snippets:5",
            "image_url": "bi-code-square"
        },
        {
            "name": "Code Journeyman",
            "description": "Created 10 code snippets",
            "criteria": "snippets:10",
            "image_url": "bi-code"
        },
        {
            "name": "Code Expert",
            "description": "Created 25 code snippets",
            "criteria": "snippets:25",
            "image_url": "bi-braces"
        },
        {
            "name": "Code Master",
            "description": "Created 50 code snippets",
            "criteria": "snippets:50",
            "image_url": "bi-diagram-3"
        },
        {
            "name": "Code Guru",
            "description": "Created 100 code snippets",
            "criteria": "snippets:100",
            "image_url": "bi-lightning"
        },
        {
            "name": "Legendary Coder",
            "description": "Created 250 code snippets",
            "criteria": "snippets:250",
            "image_url": "bi-trophy"
        },
        
        # Collection-related badges
        {
            "name": "Organizer",
            "description": "Created your first collection",
            "criteria": "collections:1",
            "image_url": "bi-folder-plus"
        },
        {
            "name": "Archivist",
            "description": "Created 5 collections",
            "criteria": "collections:5",
            "image_url": "bi-folder2-open"
        },
        {
            "name": "Librarian",
            "description": "Created 10 collections",
            "criteria": "collections:10",
            "image_url": "bi-folder"
        },
        
        # Points-related badges
        {
            "name": "Rookie",
            "description": "Earned your first 10 points",
            "criteria": "points:10",
            "image_url": "bi-star"
        },
        {
            "name": "Contributor",
            "description": "Earned 50 points",
            "criteria": "points:50",
            "image_url": "bi-star-fill"
        },
        {
            "name": "Champion",
            "description": "Earned 100 points",
            "criteria": "points:100",
            "image_url": "bi-gem"
        },
        {
            "name": "Legend",
            "description": "Earned 250 points",
            "criteria": "points:250",
            "image_url": "bi-crown"
        },
        
        # Activity streaks
        {
            "name": "Getting Started",
            "description": "Maintained a 3-day coding streak",
            "criteria": "streak:3",
            "image_url": "bi-fire"
        },
        {
            "name": "Dedicated",
            "description": "Maintained a 7-day coding streak",
            "criteria": "streak:7",
            "image_url": "bi-flame"
        },
        {
            "name": "Committed",
            "description": "Maintained a 14-day coding streak",
            "criteria": "streak:14",
            "image_url": "bi-burn"
        },
        {
            "name": "Persistent",
            "description": "Maintained a 30-day coding streak",
            "criteria": "streak:30",
            "image_url": "bi-incandescent"
        },
        
        # Language diversity
        {
            "name": "Polyglot",
            "description": "Used 3 different programming languages",
            "criteria": "languages:3",
            "image_url": "bi-translate"
        },
        {
            "name": "Universal Coder",
            "description": "Used 5 different programming languages",
            "criteria": "languages:5",
            "image_url": "bi-globe"
        },
        
        # LeetCode contributions
        {
            "name": "Problem Solver",
            "description": "Added your first LeetCode problem",
            "criteria": "problems:1",
            "image_url": "bi-puzzle"
        },
        {
            "name": "Solution Provider",
            "description": "Contributed your first solution",
            "criteria": "solutions:1",
            "image_url": "bi-lightbulb"
        },
        {
            "name": "Algorithm Expert",
            "description": "Contributed 5 solutions",
            "criteria": "solutions:5",
            "image_url": "bi-cpu"
        },
        
        # Notes and documentation
        {
            "name": "Note Taker",
            "description": "Created your first note",
            "criteria": "notes:1",
            "image_url": "bi-journal-text"
        },
        {
            "name": "Knowledge Keeper",
            "description": "Created 10 notes",
            "criteria": "notes:10",
            "image_url": "bi-journal-bookmark"
        },
        
        # Special achievements
        {
            "name": "Early Adopter",
            "description": "One of the first users to join",
            "criteria": "early_user:true",
            "image_url": "bi-rocket"
        },
        {
            "name": "Active Contributor",
            "description": "Active for 30 days",
            "criteria": "days_active:30",
            "image_url": "bi-calendar-check"
        }
    ]
    
    for badge_data in default_badges:
        # Check if badge already exists
        existing_badge = db.session.scalar(
            sa.select(Badge).where(Badge.name == badge_data["name"])
        )
        
        if not existing_badge:
            badge = Badge(
                name=badge_data["name"],
                description=badge_data["description"],
                criteria=badge_data["criteria"],
                image_url=badge_data["image_url"]
            )
            db.session.add(badge)
    
    db.session.commit()


def check_and_award_badges(user):
    """Enhanced badge checking and awarding system."""
    from app.models import Snippet, Collection, LeetcodeProblem, LeetcodeSolution, Note
    
    # Get user statistics
    snippet_count = user.snippets.count()
    collection_count = user.collections.count()
    problem_count = user.leetcode_problems.count()
    solution_count = user.leetcode_solutions.count()
    note_count = user.notes.count()
    total_points = user.get_total_points()
    
    # Calculate language diversity
    language_count = db.session.scalar(
        sa.select(sa.func.count(sa.distinct(Snippet.language)))
        .where(Snippet.user_id == user.id)
    ) or 0
    
    # Calculate current streak
    current_streak = calculate_current_streak(user)
    
    # Calculate days active
    days_active = calculate_days_active(user)
    
    # Badge criteria checking
    badge_criteria = [
        # Snippet badges
        ("First Snippet", snippet_count >= 1),
        ("Code Apprentice", snippet_count >= 5),
        ("Code Journeyman", snippet_count >= 10),
        ("Code Expert", snippet_count >= 25),
        ("Code Master", snippet_count >= 50),
        ("Code Guru", snippet_count >= 100),
        ("Legendary Coder", snippet_count >= 250),
        
        # Collection badges
        ("Organizer", collection_count >= 1),
        ("Archivist", collection_count >= 5),
        ("Librarian", collection_count >= 10),
        
        # Points badges
        ("Rookie", total_points >= 10),
        ("Contributor", total_points >= 50),
        ("Champion", total_points >= 100),
        ("Legend", total_points >= 250),
        
        # Streak badges
        ("Getting Started", current_streak >= 3),
        ("Dedicated", current_streak >= 7),
        ("Committed", current_streak >= 14),
        ("Persistent", current_streak >= 30),
        
        # Language badges
        ("Polyglot", language_count >= 3),
        ("Universal Coder", language_count >= 5),
        
        # LeetCode badges
        ("Problem Solver", problem_count >= 1),
        ("Solution Provider", solution_count >= 1),
        ("Algorithm Expert", solution_count >= 5),
        
        # Notes badges
        ("Note Taker", note_count >= 1),
        ("Knowledge Keeper", note_count >= 10),
        
        # Special badges
        ("Active Contributor", days_active >= 30)
    ]
    
    # Award badges based on criteria
    awarded_count = 0
    for badge_name, criteria_met in badge_criteria:
        if criteria_met:
            if user.award_badge(badge_name):
                awarded_count += 1
    
    if awarded_count > 0:
        db.session.commit()
    
    return awarded_count


def calculate_current_streak(user):
    """Calculate the current consecutive day streak."""
    from datetime import date, timedelta
    from app.models import Snippet, Note
    
    today = date.today()
    streak = 0
    current_date = today
    
    # Check snippets and notes for consecutive days
    for i in range(365):  # Check up to 1 year back
        # Check if user was active on this date
        snippet_count = db.session.scalar(
            sa.select(sa.func.count(Snippet.id))
            .where(
                Snippet.user_id == user.id,
                sa.func.date(Snippet.timestamp) == current_date
            )
        ) or 0
        
        note_count = db.session.scalar(
            sa.select(sa.func.count(Note.id))
            .where(
                Note.user_id == user.id,
                sa.func.date(Note.timestamp) == current_date
            )
        ) or 0
        
        if snippet_count > 0 or note_count > 0:
            if i == 0:  # Today
                streak = 1
            elif streak > 0:  # Continuing streak
                streak += 1
            else:  # First day of streak
                streak = 1
        else:
            if i == 0:  # No activity today, streak is 0
                break
            else:  # Streak broken
                break
        
        current_date = current_date - timedelta(days=1)
    
    return streak


def calculate_days_active(user):
    """Calculate total number of days the user has been active."""
    from app.models import Snippet, Note
    
    # Get unique active dates from snippets
    snippet_dates = db.session.execute(
        sa.select(sa.func.date(Snippet.timestamp))
        .where(Snippet.user_id == user.id)
        .distinct()
    ).scalars().all()
    
    # Get unique active dates from notes
    note_dates = db.session.execute(
        sa.select(sa.func.date(Note.timestamp))
        .where(Note.user_id == user.id)
        .distinct()
    ).scalars().all()
    
    # Combine and count unique dates
    all_dates = set(snippet_dates + note_dates)
    return len(all_dates)
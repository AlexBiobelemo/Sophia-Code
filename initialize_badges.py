"""Simple script to initialize badges and test the system."""

from app import create_app, db
from app.models import User, Badge, UserBadge
from app.badge_system import initialize_default_badges, check_and_award_badges

app = create_app()

with app.app_context():
    # Initialize default badges
    print("Initializing default badges...")
    initialize_default_badges()
    print("Badges initialized successfully!")
    
    # Get all users and update badges
    users = User.query.all()
    print(f"Processing badges for {len(users)} users...")
    
    total_badges_awarded = 0
    
    for user in users:
        # Check and award badges
        awarded_count = check_and_award_badges(user)
        total_badges_awarded += awarded_count
        if awarded_count > 0:
            print(f"Awarded {awarded_count} new badges to user: {user.username}")
    
    print(f"\nInitialization complete!")
    print(f"Total badges awarded: {total_badges_awarded}")
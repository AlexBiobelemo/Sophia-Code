#!/usr/bin/env python3
"""
Comprehensive User Management Script for Project-Sophia

This script allows you to:
1. List all users in the database
2. Verify passwords against stored hashes
3. Create new users
4. Reset user passwords

Usage:
    python user_manager.py [command] [options]

Commands:
    list        - List all users
    verify      - Verify a password against all users
    create      - Create a new user
    reset       - Reset a user's password

Examples:
    python user_manager.py list
    python user_manager.py verify --password "mypassword"
    python user_manager.py create --username "john" --email "john@example.com" --password "newpass123"
    python user_manager.py reset --username "john" --password "newpass123"
"""

import os
import sys
import argparse
from werkzeug.security import generate_password_hash, check_password_hash

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_flask_app():
    """Set up Flask app and database connection."""
    from flask import Flask
    from config import Config
    from app import db
    from app.models import User
    
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    
    return app, User

def list_users():
    """List all users in the database."""
    app, User = setup_flask_app()
    
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("No users found in the database.")
            return
        
        print(f"\n{'='*80}")
        print(f"{'User Credentials Report':^80}")
        print(f"{'='*80}")
        print(f"{'Username':<20} {'Email':<30} {'Password Hash (preview)':<30}")
        print(f"{'-'*80}")
        
        for user in users:
            print(f"{user.username:<20} {user.email:<30} {user.password_hash[:25]}...")
        
        print(f"{'='*80}")
        print(f"Total users found: {len(users)}")
        print(f"{'='*80}\n")

def verify_password(password_to_check):
    """Verify a password against all user hashes."""
    if not password_to_check:
        print("Please provide a password to verify using --password option.")
        return
    
    app, User = setup_flask_app()
    
    with app.app_context():
        users = User.query.all()
        
        if not users:
            print("No users found in the database.")
            return
        
        print(f"\n{'='*80}")
        print(f"{'Password Verification Report':^80}")
        print(f"{'='*80}")
        print(f"Verifying password: {password_to_check}")
        print(f"{'-'*80}")
        
        found_match = False
        for user in users:
            if check_password_hash(user.password_hash, password_to_check):
                print(f"✓ MATCH FOUND: Username '{user.username}' uses this password!")
                found_match = True
            else:
                print(f"✗ No match for user: {user.username}")
        
        if not found_match:
            print("No users found with the provided password.")
        
        print(f"{'='*80}\n")

def create_user(username, email, password):
    """Create a new user in the database."""
    app, User = setup_flask_app()
    
    with app.app_context():
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Error: Username '{username}' already exists.")
            return False
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"Error: Email '{email}' already exists.")
            return False
        
        # Create new user
        new_user = User(
            username=username,
            email=email
        )
        new_user.set_password(password)
        
        try:
            db = app.extensions['sqlalchemy'].db
            db.session.add(new_user)
            db.session.commit()
            print(f"✓ User '{username}' created successfully!")
            print(f"  Email: {email}")
            print(f"  Password: {password}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}")
            return False

def reset_password(username, new_password):
    """Reset a user's password."""
    app, User = setup_flask_app()
    
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        
        if not user:
            print(f"Error: User '{username}' not found.")
            return False
        
        user.set_password(new_password)
        
        try:
            db = app.extensions['sqlalchemy'].db
            db.session.commit()
            print(f"✓ Password for user '{username}' reset successfully!")
            print(f"  New password: {new_password}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting password: {e}")
            return False

def main():
    """Main function to parse arguments and execute commands."""
    parser = argparse.ArgumentParser(
        description="User Management for Project-Sophia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
    list        - List all users in the database
    verify      - Verify a password against all users
    create      - Create a new user
    reset       - Reset a user's password

Examples:
    python user_manager.py list
    python user_manager.py verify --password "mypassword"
    python user_manager.py create --username "john" --email "john@example.com" --password "newpass123"
    python user_manager.py reset --username "john" --password "newpass123"
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all users')
    
    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify a password against all users')
    verify_parser.add_argument('--password', type=str, required=True, help='Password to verify')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new user')
    create_parser.add_argument('--username', type=str, required=True, help='Username for new user')
    create_parser.add_argument('--email', type=str, required=True, help='Email for new user')
    create_parser.add_argument('--password', type=str, required=True, help='Password for new user')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset a user\'s password')
    reset_parser.add_argument('--username', type=str, required=True, help='Username to reset password for')
    reset_parser.add_argument('--password', type=str, required=True, help='New password')
    
    args = parser.parse_args()
    
    # Check if database file exists
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print("Make sure you're running this script from the Project-Sophia root directory.")
        sys.exit(1)
    
    # Execute command
    if args.command == 'list':
        list_users()
    elif args.command == 'verify':
        verify_password(args.password)
    elif args.command == 'create':
        create_user(args.username, args.email, args.password)
    elif args.command == 'reset':
        reset_password(args.username, args.password)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
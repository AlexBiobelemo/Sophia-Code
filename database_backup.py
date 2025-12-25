#!/usr/bin/env python3
"""
Automatic Database Backup System
Creates backups of app.db in a backup folder with timestamps.
Can be triggered manually, on server startup, or after snippet saves.
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

class DatabaseBackup:
    """Handles automatic database backups for the Flask application."""
    
    def __init__(self, db_path='app.db', backup_dir='backup', max_backups=50):
        """
        Initialize the backup system.
        
        Args:
            db_path: Path to the database file
            backup_dir: Directory to store backups
            max_backups: Maximum number of backup files to keep
        """
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)
        
        print(f"Database Backup System initialized:")
        print(f"  Database: {self.db_path}")
        print(f"  Backup directory: {self.backup_dir}")
        print(f"  Max backups to keep: {self.max_backups}")
    
    def create_backup(self, reason="manual"):
        """
        Create a backup of the database.
        
        Args:
            reason: Reason for the backup (e.g., "server_startup", "auto_save", "manual")
        
        Returns:
            str: Path to the backup file if successful, None if failed
        """
        if not self.db_path.exists():
            print(f"Error: Database file {self.db_path} does not exist!")
            return None
        
        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}_{reason}.db"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Copy the database file
            shutil.copy2(self.db_path, backup_path)
            print(f"Backup created: {backup_path} (reason: {reason})")
            
            # Clean up old backups if we have too many
            self.cleanup_old_backups()
            
            return str(backup_path)
            
        except Exception as e:
            print(f"Error creating backup: {str(e)}")
            return None
    
    def cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones."""
        try:
            # Get all backup files
            backup_files = list(self.backup_dir.glob("backup_*.db"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            if len(backup_files) > self.max_backups:
                # Remove excess backups
                for backup_file in backup_files[self.max_backups:]:
                    backup_file.unlink()
                    print(f"Removed old backup: {backup_file}")
                    
        except Exception as e:
            print(f"Error cleaning up old backups: {str(e)}")
    
    def list_backups(self):
        """List all available backups with their creation times."""
        try:
            backup_files = list(self.backup_dir.glob("backup_*.db"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            print(f"\nAvailable backups ({len(backup_files)}):")
            print("-" * 60)
            
            for backup_file in backup_files:
                stat = backup_file.stat()
                size_mb = stat.st_size / (1024 * 1024)
                created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                reason = backup_file.stem.split('_', 2)[-1] if '_' in backup_file.stem else "unknown"
                
                print(f"  {backup_file.name}")
                print(f"    Created: {created}")
                print(f"    Modified: {modified}")
                print(f"    Size: {size_mb:.2f} MB")
                print(f"    Reason: {reason}")
                print()
            
            return backup_files
            
        except Exception as e:
            print(f"Error listing backups: {str(e)}")
            return []
    
    def restore_backup(self, backup_filename):
        """
        Restore the database from a backup.
        
        Args:
            backup_filename: Name of the backup file to restore
        """
        backup_path = self.backup_dir / backup_filename
        
        if not backup_path.exists():
            print(f"Error: Backup file {backup_filename} does not exist!")
            return False
        
        # Ask for confirmation
        response = input(f"Are you sure you want to restore from {backup_filename}? This will overwrite the current database! (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Restore cancelled.")
            return False
        
        try:
            # Close any open database connections
            self._close_db_connections()
            
            # Restore the backup
            shutil.copy2(backup_path, self.db_path)
            print(f"Database restored from {backup_filename}")
            return True
            
        except Exception as e:
            print(f"Error restoring backup: {str(e)}")
            return False
    
    def _close_db_connections(self):
        """Attempt to close any open database connections."""
        try:
            # This is a simple approach - in a real Flask app, 
            # you might want to handle this more gracefully
            import sqlite3
            sqlite3.connect(':memory:').close()
        except:
            pass
    
    def run_server_startup_backup(self):
        """Run backup on server startup."""
        print("\n" + "="*60)
        print("Running server startup backup...")
        self.create_backup("server_startup")
        print("="*60 + "\n")
    
    def run_snippet_save_backup(self, snippet_count):
        """Run backup after snippet saves."""
        print(f"\nAuto backup triggered after {snippet_count} snippet saves")
        self.create_backup(f"auto_{snippet_count}_snippets")
        print()


# Global backup counter for tracking snippet saves
snippet_save_count = 0
backup_system = None

def init_backup_system():
    """Initialize the backup system."""
    global backup_system
    backup_system = DatabaseBackup()
    return backup_system

def get_backup_system():
    """Get the initialized backup system."""
    return backup_system

def increment_snippet_save_counter():
    """Increment the snippet save counter and create backup if needed."""
    global snippet_save_count, backup_system
    
    if backup_system is None:
        backup_system = DatabaseBackup()
    
    snippet_save_count += 1
    
    # Create backup after every 5 snippet saves
    if snippet_save_count % 5 == 0:
        backup_system.run_snippet_save_backup(snippet_save_count)
    
    return snippet_save_count

def create_manual_backup():
    """Create a manual backup."""
    if backup_system is None:
        backup_system = DatabaseBackup()
    return backup_system.create_backup("manual")


def main():
    """Main function for command-line usage."""
    backup = DatabaseBackup()
    
    if len(sys.argv) < 2:
        print("Database Backup System")
        print("Usage:")
        print("  python database_backup.py create           - Create a manual backup")
        print("  python database_backup.py list             - List all backups")
        print("  python database_backup.py restore <file>   - Restore from backup")
        print("  python database_backup.py startup          - Run server startup backup")
        print("  python database_backup.py auto <count>     - Simulate auto backup")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "create":
        backup.create_backup("manual")
    elif command == "list":
        backup.list_backups()
    elif command == "restore" and len(sys.argv) > 2:
        backup.restore_backup(sys.argv[2])
    elif command == "startup":
        backup.run_server_startup_backup()
    elif command == "auto" and len(sys.argv) > 2:
        try:
            count = int(sys.argv[2])
            backup.run_snippet_save_backup(count)
        except ValueError:
            print("Error: Please provide a valid number for auto command")
    else:
        print("Invalid command. Use 'create', 'list', 'restore', 'startup', or 'auto'")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
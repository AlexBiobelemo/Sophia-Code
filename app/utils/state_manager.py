"""State management utilities for preserving user state across page navigations."""

import json
import time
from typing import Any, Dict, Optional, Union
from flask import session, request, current_app, has_request_context
from datetime import datetime, timedelta

class StateManager:
    """Manages user state preservation across page navigations."""
    
    # State categories
    FORM_DATA = 'form_data'
    SEARCH_FILTERS = 'search_filters'
    PAGINATION_STATE = 'pagination'
    DRAFT_CONTENT = 'drafts'
    NAVIGATION_STATE = 'navigation'
    
    # State retention period (24 hours)
    RETENTION_PERIOD = timedelta(hours=24)
    
    @classmethod
    def _get_state_key(cls, category: str, identifier: str = None) -> str:
        """Generate a unique key for storing state data."""
        if identifier:
            return f'state_{category}_{identifier}'
        return f'state_{category}'
    
    @classmethod
    def save_state(cls, category: str, data: Dict[str, Any], identifier: str = None) -> None:
        """Save state data to session with timestamp."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_state_key(category, identifier)
            state_data = {
                'data': data,
                'timestamp': datetime.utcnow().isoformat(),
                'url': request.url if request else None,
                'user_agent': request.headers.get('User-Agent') if request else None
            }
            session[key] = state_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save state for {category}: {e}")
    
    @classmethod
    def get_state(cls, category: str, identifier: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve state data from session if not expired."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return None  # Return None if not in request context
                
            key = cls._get_state_key(category, identifier)
            state_data = session.get(key)
            
            if not state_data:
                return None
            
            # Check if state is expired
            timestamp = datetime.fromisoformat(state_data['timestamp'])
            if datetime.utcnow() - timestamp > cls.RETENTION_PERIOD:
                session.pop(key, None)
                return None
            
            return state_data['data']
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to retrieve state for {category}: {e}")
            return None
    
    @classmethod
    def clear_state(cls, category: str, identifier: str = None) -> None:
        """Clear specific state data."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip clearing if not in request context
                
            key = cls._get_state_key(category, identifier)
            session.pop(key, None)
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to clear state for {category}: {e}")
    
    @classmethod
    def clear_expired_states(cls) -> None:
        """Clear all expired state data."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip clearing if not in request context
                
            keys_to_remove = []
            for key, value in session.items():
                if key.startswith('state_') and isinstance(value, dict):
                    timestamp = datetime.fromisoformat(value['timestamp'])
                    if datetime.utcnow() - timestamp > cls.RETENTION_PERIOD:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                session.pop(key, None)
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to clear expired states: {e}")
    
    @classmethod
    def save_form_data(cls, form_name: str, form_data: Dict[str, Any]) -> None:
        """Save form data for later restoration."""
        cls.save_state(cls.FORM_DATA, form_data, form_name)
    
    @classmethod
    def get_form_data(cls, form_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve saved form data."""
        return cls.get_state(cls.FORM_DATA, form_name)
    
    @classmethod
    def save_search_filters(cls, filters: Dict[str, Any]) -> None:
        """Save search filter state."""
        cls.save_state(cls.SEARCH_FILTERS, filters)
    
    @classmethod
    def get_search_filters(cls) -> Optional[Dict[str, Any]]:
        """Retrieve search filter state."""
        return cls.get_state(cls.SEARCH_FILTERS)
    
    @classmethod
    def save_pagination_state(cls, page: int, per_page: int) -> None:
        """Save pagination state."""
        cls.save_state(cls.PAGINATION_STATE, {
            'page': page,
            'per_page': per_page
        })
    
    @classmethod
    def get_pagination_state(cls) -> Optional[Dict[str, int]]:
        """Retrieve pagination state."""
        return cls.get_state(cls.PAGINATION_STATE)
    
    @classmethod
    def save_draft_content(cls, content_type: str, content_id: str, content: str) -> None:
        """Save draft content with automatic cleanup."""
        draft_key = f"{content_type}_{content_id}"
        cls.save_state(cls.DRAFT_CONTENT, {
            'content': content,
            'content_type': content_type,
            'content_id': content_id
        }, draft_key)
    
    @classmethod
    def get_draft_content(cls, content_type: str, content_id: str) -> Optional[str]:
        """Retrieve draft content."""
        draft_key = f"{content_type}_{content_id}"
        state = cls.get_state(cls.DRAFT_CONTENT, draft_key)
        return state['content'] if state else None
    
    @classmethod
    def clear_draft_content(cls, content_type: str, content_id: str) -> None:
        """Clear specific draft content."""
        draft_key = f"{content_type}_{content_id}"
        cls.clear_state(cls.DRAFT_CONTENT, draft_key)


class AutoSaveManager:
    """Manages automatic saving of draft content."""
    
    @staticmethod
    def should_auto_save(content: str, last_saved: Optional[datetime] = None) -> bool:
        """Determine if content should be auto-saved."""
        if not content or len(content.strip()) < 10:  # Minimum content length
            return False
        
        if not last_saved:
            return True
        
        # Auto-save if more than 30 seconds have passed
        return (datetime.utcnow() - last_saved).total_seconds() > 30
    
    @staticmethod
    def format_auto_save_timestamp(timestamp: datetime) -> str:
        """Format timestamp for display in auto-save notifications."""
        now = datetime.utcnow()
        diff = now - timestamp
        
        if diff.total_seconds() < 60:
            return "just now"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            hours = int(diff.total_seconds() // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"


class StatePreservationMiddleware:
    """Middleware for automatic state preservation."""
    
    @staticmethod
    def before_request():
        """Process state before each request."""
        # Clean up expired states on every request (with low probability to avoid overhead)
        import random
        if random.random() < 0.1:  # 10% chance
            StateManager.clear_expired_states()
    
    @staticmethod
    def after_request(response):
        """Process state after each request."""
        # Add headers to indicate state preservation is enabled
        response.headers['X-State-Preservation'] = 'enabled'
        return response


def preserve_form_state(form_data: Dict[str, Any], form_name: str) -> None:
    """Convenience function to preserve form state."""
    StateManager.save_form_data(form_name, form_data)


def restore_form_state(form_name: str) -> Optional[Dict[str, Any]]:
    """Convenience function to restore form state."""
    return StateManager.get_form_data(form_name)


def preserve_search_state(filters: Dict[str, Any]) -> None:
    """Convenience function to preserve search state."""
    StateManager.save_search_filters(filters)


def restore_search_state() -> Optional[Dict[str, Any]]:
    """Convenience function to restore search state."""
    return StateManager.get_search_filters()


class StreamingStateManager:
    """Manages state for streaming AI pipeline operations."""
    
    # Streaming session retention period (2 hours)
    STREAMING_RETENTION = timedelta(hours=2)
    
    @classmethod
    def _get_streaming_key(cls, session_id: str, data_type: str) -> str:
        """Generate a unique key for streaming data."""
        return f'streaming_{session_id}_{data_type}'
    
    @classmethod
    def save_session_start(cls, session_id: str, pipeline_type: str, prompt: str) -> None:
        """Save the start of a streaming session."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'session')
            session_data = {
                'pipeline_type': pipeline_type,
                'prompt': prompt,
                'start_time': datetime.utcnow().isoformat(),
                'status': 'started',
                'steps_completed': 0
            }
            session[key] = session_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save streaming session start: {e}")
    
    @classmethod
    def save_intermediate_code(cls, session_id: str, code_content: str) -> None:
        """Save intermediate code content during streaming."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'intermediate_code')
            code_data = {
                'content': code_content,
                'timestamp': datetime.utcnow().isoformat(),
                'chunk_count': code_content.count('\n') + 1 if code_content else 0
            }
            session[key] = code_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save intermediate code: {e}")
    
    @classmethod
    def save_final_code(cls, session_id: str, code_content: str) -> None:
        """Save final code content."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'final_code')
            code_data = {
                'content': code_content,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
            session[key] = code_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save final code: {e}")
    
    @classmethod
    def save_intermediate_explanation(cls, session_id: str, explanation_content: str) -> None:
        """Save intermediate explanation content during streaming."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'intermediate_explanation')
            explanation_data = {
                'content': explanation_content,
                'timestamp': datetime.utcnow().isoformat(),
                'chunk_count': explanation_content.count('\n') + 1 if explanation_content else 0
            }
            session[key] = explanation_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save intermediate explanation: {e}")
    
    @classmethod
    def save_final_explanation(cls, session_id: str, explanation_content: str) -> None:
        """Save final explanation content."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'final_explanation')
            explanation_data = {
                'content': explanation_content,
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'completed'
            }
            session[key] = explanation_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to save final explanation: {e}")
    
    @classmethod
    def update_session_progress(cls, session_id: str, steps_completed: int) -> None:
        """Update session progress."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip saving if not in request context
                
            key = cls._get_streaming_key(session_id, 'session')
            session_data = session.get(key)
            if session_data:
                session_data['steps_completed'] = steps_completed
                session_data['last_update'] = datetime.utcnow().isoformat()
                session[key] = session_data
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to update session progress: {e}")
    
    @classmethod
    def get_session_data(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve all session data."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return None  # Return None if not in request context
                
            session_key = cls._get_streaming_key(session_id, 'session')
            session_data = session.get(session_key)
            
            if not session_data:
                return None
            
            # Check if session is expired
            timestamp = datetime.fromisoformat(session_data['start_time'])
            if datetime.utcnow() - timestamp > cls.STREAMING_RETENTION:
                cls.clear_session(session_id)
                return None
            
            # Collect all session data
            result = session_data.copy()
            
            # Get intermediate/final code
            intermediate_code_key = cls._get_streaming_key(session_id, 'intermediate_code')
            final_code_key = cls._get_streaming_key(session_id, 'final_code')
            
            result['intermediate_code'] = session.get(intermediate_code_key)
            result['final_code'] = session.get(final_code_key)
            
            # Get intermediate/final explanation
            intermediate_explanation_key = cls._get_streaming_key(session_id, 'intermediate_explanation')
            final_explanation_key = cls._get_streaming_key(session_id, 'final_explanation')
            
            result['intermediate_explanation'] = session.get(intermediate_explanation_key)
            result['final_explanation'] = session.get(final_explanation_key)
            
            return result
            
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to retrieve session data: {e}")
            return None
    
    @classmethod
    def get_code_content(cls, session_id: str) -> Optional[str]:
        """Get the latest code content for the session."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return None  # Return None if not in request context
                
            # Try final code first
            final_code_key = cls._get_streaming_key(session_id, 'final_code')
            final_data = session.get(final_code_key)
            if final_data and final_data.get('status') == 'completed':
                return final_data['content']
            
            # Fall back to intermediate code
            intermediate_code_key = cls._get_streaming_key(session_id, 'intermediate_code')
            intermediate_data = session.get(intermediate_code_key)
            if intermediate_data:
                return intermediate_data['content']
            
            return None
            
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to get code content: {e}")
            return None
    
    @classmethod
    def clear_session(cls, session_id: str) -> None:
        """Clear all data for a specific streaming session."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip clearing if not in request context
                
            keys_to_remove = []
            for key in session.keys():
                if key.startswith(f'streaming_{session_id}_'):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                session.pop(key, None)
                
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to clear streaming session: {e}")
    
    @classmethod
    def clear_expired_streaming_sessions(cls) -> None:
        """Clear all expired streaming sessions."""
        try:
            # Check if we're in a request context
            if not has_request_context():
                return  # Skip clearing if not in request context
                
            current_time = datetime.utcnow()
            keys_to_remove = []
            
            for key, value in session.items():
                if key.startswith('streaming_') and isinstance(value, dict):
                    if 'start_time' in value:
                        timestamp = datetime.fromisoformat(value['start_time'])
                        if current_time - timestamp > cls.STREAMING_RETENTION:
                            keys_to_remove.append(key)
            
            for key in keys_to_remove:
                session.pop(key, None)
                
        except Exception as e:
            if has_request_context():
                current_app.logger.warning(f"Failed to clear expired streaming sessions: {e}")


# Add streaming middleware to the existing middleware
class StreamingStatePreservationMiddleware:
    """Enhanced middleware for streaming state preservation."""
    
    @staticmethod
    def before_request():
        """Process streaming state before each request."""
        # Clean up expired streaming sessions (with low probability to avoid overhead)
        import random
        if random.random() < 0.05:  # 5% chance
            StreamingStateManager.clear_expired_streaming_sessions()
        
        # Clean up regular expired states
        StatePreservationMiddleware.before_request()
    
    @staticmethod
    def after_request(response):
        """Process state after each request."""
        # Add headers to indicate streaming state preservation is enabled
        response.headers['X-Streaming-State-Preservation'] = 'enabled'
        return StatePreservationMiddleware.after_request(response)


# Convenience functions for streaming state
def save_streaming_session(session_id: str, pipeline_type: str, prompt: str) -> None:
    """Convenience function to save streaming session start."""
    StreamingStateManager.save_session_start(session_id, pipeline_type, prompt)


def get_streaming_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to retrieve streaming session data."""
    return StreamingStateManager.get_session_data(session_id)


def clear_streaming_session(session_id: str) -> None:
    """Convenience function to clear streaming session data."""
    StreamingStateManager.clear_session(session_id)


def get_streaming_code_content(session_id: str) -> Optional[str]:
    """Convenience function to get streaming code content."""
    return StreamingStateManager.get_code_content(session_id)


# Enhanced convenience functions with context safety
def safe_save_state(category: str, data: Dict[str, Any], identifier: str = None) -> None:
    """Safely save state data, handling cases where session is not available."""
    try:
        if has_request_context():
            StateManager.save_state(category, data, identifier)
    except Exception:
        pass  # Silently fail if we can't save state


def safe_get_state(category: str, identifier: str = None) -> Optional[Dict[str, Any]]:
    """Safely get state data, handling cases where session is not available."""
    try:
        if has_request_context():
            return StateManager.get_state(category, identifier)
    except Exception:
        pass  # Silently fail if we can't get state
    return None


def safe_save_streaming_code(session_id: str, code_content: str) -> None:
    """Safely save streaming code, handling cases where session is not available."""
    try:
        if has_request_context():
            StreamingStateManager.save_intermediate_code(session_id, code_content)
    except Exception:
        pass  # Silently fail if we can't save streaming code


def safe_update_streaming_progress(session_id: str, steps_completed: int) -> None:
    """Safely update streaming progress, handling cases where session is not available."""
    try:
        if has_request_context():
            StreamingStateManager.update_session_progress(session_id, steps_completed)
    except Exception:
        pass  # Silently fail if we can't update progress
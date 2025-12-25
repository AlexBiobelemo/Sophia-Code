"""
Enhanced MiniMax AI Service with improved error handling and rate limiting.
"""

import requests
import json
import time
import random
from typing import Callable, Optional
from flask import current_app

# Rate limiting
class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        # Remove old requests outside the time window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            # Wait until the oldest request expires
            oldest_request = min(self.requests)
            wait_time = self.time_window - (now - oldest_request) + 1
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
        
        self.requests.append(now)

# Global rate limiter
rate_limiter = RateLimiter(max_requests=8, time_window=60)  # Conservative limits

def _safe_log_error(message):
    """Safely log error messages."""
    try:
        current_app.logger.error(message)
    except RuntimeError:
        print(f"ERROR: {message}")

def _get_api_key():
    """Get Minimax API key from configuration."""
    try:
        api_key = current_app.config.get('MINIMAX_API_KEY')
    except RuntimeError:
        import os
        api_key = os.environ.get('MINIMAX_API_KEY')
    
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured.")
    return api_key

def _make_minimax_request_enhanced(prompt, system_prompt=None, temperature=0.4, max_tokens=2048, operation_name="general"):
    """Enhanced MiniMax API request with better error handling."""
    api_key = _get_api_key()
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "minimax/minimax-m2:free",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    
    # Apply rate limiting
    rate_limiter.wait_if_needed()
    
    max_retries = 3
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.minimax.chat/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.ok:
                result = response.json()
                if 'choices' not in result or not result['choices']:
                    raise RuntimeError("No choices in MiniMax API response")
                
                return result['choices'][0]['message']['content'].strip()
            
            # Handle specific error cases
            if response.status_code == 401:
                error_data = response.text
                try:
                    error_json = json.loads(error_data)
                    if "invalid api key" in error_json.get('error', {}).get('message', '').lower():
                        _safe_log_error(f"MiniMax API key is invalid for {operation_name}")
                        raise RuntimeError(f"Invalid API key for {operation_name}. Please check your MINIMAX_API_KEY.")
                except:
                    pass
                raise RuntimeError(f"Authentication failed: {response.status_code} - {response.text}")
            
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    _safe_log_warning(f"Rate limited for {operation_name}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"Rate limit exceeded for {operation_name}")
            
            elif response.status_code >= 500:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    _safe_log_warning(f"Server error for {operation_name}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise RuntimeError(f"Server error: {response.status_code} - {response.text}")
            
            else:
                raise RuntimeError(f"API error: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                _safe_log_warning(f"Request failed for {operation_name}. Retrying in {delay:.1f}s...")
                time.sleep(delay)
                continue
            else:
                raise RuntimeError(f"Request failed: {str(e)}")
    
    raise RuntimeError(f"Max retries exceeded for {operation_name}")

def suggest_tags_for_code_enhanced(code_to_analyze):
    """Enhanced tag suggestion with better error handling."""
    try:
        # Simplified prompt to reduce complexity
        system_prompt = "Generate 3-5 comma-separated tags for this code. Only return the tags, no explanation."
        
        prompt = f"Analyze this code and provide tags: {code_to_analyze[:500]}"  # Limit code length
        
        result = _make_minimax_request_enhanced(
            prompt, 
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=100,
            operation_name="tag suggestion"
        )
        
        # Clean and return tags
        parts = [t.strip().lower() for t in result.replace("\n", ",").split(",") if t.strip()]
        return ",".join(parts[:5])
        
    except Exception as e:
        _safe_log_error(f"MiniMax API error (tagging): {e}")
        return f"Error: Could not suggest tags. {str(e)}"

def explain_code_enhanced(code_to_explain):
    """Enhanced code explanation with better error handling."""
    try:
        # Simplified system prompt
        system_prompt = "Explain this code clearly and concisely."
        
        # Limit code length to avoid token limits
        limited_code = code_to_explain[:1000] if len(code_to_explain) > 1000 else code_to_explain
        
        prompt = f"Explain this code:\n```\n{limited_code}\n```"
        
        result = _make_minimax_request_enhanced(
            prompt, 
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=500,
            operation_name="code explanation"
        )
        
        return result
        
    except Exception as e:
        _safe_log_error(f"MiniMax API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"

# Example usage replacement functions
def replace_in_ai_services():
    """Instructions for replacing the existing functions."""
    return """
    To apply the enhanced MiniMax service:

    1. Backup your current ai_services_minimax.py
    2. Replace the following functions with the enhanced versions:
       - suggest_tags_for_code() -> suggest_tags_for_code_enhanced()
       - explain_code() -> explain_code_enhanced()
    
    3. Add the rate limiter and enhanced request function at the top of the file
    
    4. Update your route handlers to use the enhanced functions
    
    The enhanced version includes:
    - Better rate limiting
    - Improved error handling for 401 errors
    - Simplified prompts to reduce API complexity
    - Exponential backoff for retries
    - Specific error messages for different failure types
    """

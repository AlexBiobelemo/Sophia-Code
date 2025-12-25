"""Comprehensive fix for MiniMax API error 401 - invalid API key (2049).

This module provides enhanced error handling, debugging, and fixes for MiniMax API authentication issues.
"""

import requests
import json
import time
import random
import os
from typing import Callable, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from flask import current_app, g


def _safe_log_error(message):
    """Safely log error messages, handling cases where current_app is not available."""
    try:
        current_app.logger.error(message)
    except RuntimeError:
        # Working outside of application context, use print instead
        print(f"ERROR: {message}")


def _safe_log_warning(message):
    """Safely log warning messages, handling cases where current_app is not available."""
    try:
        current_app.logger.warning(message)
    except RuntimeError:
        # Working outside of application context, use print instead
        print(f"WARNING: {message}")


def _safe_log_info(message):
    """Safely log info messages, handling cases where current_app is not available."""
    try:
        current_app.logger.info(message)
    except RuntimeError:
        # Working outside of application context, use print instead
        print(f"INFO: {message}")


def debug_minimax_configuration():
    """Debug function to check MiniMax API configuration and environment."""
    _safe_log_info("=== MiniMax Configuration Debug ===")
    
    # Check if MINIMAX_AVAILABLE is True
    try:
        from app.ai_services_minimax import MINIMAX_AVAILABLE
        _safe_log_info(f"MINIMAX_AVAILABLE: {MINIMAX_AVAILABLE}")
    except ImportError:
        _safe_log_error("Failed to import MINIMAX_AVAILABLE")
    
    # Check API key from different sources
    api_key_sources = {
        'config': None,
        'env': None,
        'g_object': None
    }
    
    # Check from Flask config
    try:
        api_key_sources['config'] = current_app.config.get('MINIMAX_API_KEY')
        _safe_log_info(f"API Key from config: {'✓ Set' if api_key_sources['config'] else '✗ Missing'}")
    except RuntimeError:
        _safe_log_warning("Cannot access Flask config (outside app context)")
    
    # Check from environment variables
    api_key_sources['env'] = os.environ.get('MINIMAX_API_KEY')
    _safe_log_info(f"API Key from environment: {'✓ Set' if api_key_sources['env'] else '✗ Missing'}")
    
    # Check from g object
    try:
        if hasattr(g, 'minimax_api_key'):
            api_key_sources['g_object'] = g.minimax_api_key
            _safe_log_info(f"API Key from g object: {'✓ Set' if api_key_sources['g_object'] else '✗ Missing'}")
    except RuntimeError:
        _safe_log_warning("Cannot access g object (outside request context)")
    
    # Check for conflicting environment variables
    conflicting_vars = []
    for var in ['ANTHROPIC_AUTH_TOKEN', 'OPENAI_API_KEY', 'GEMINI_API_KEY']:
        if os.environ.get(var):
            conflicting_vars.append(var)
    
    if conflicting_vars:
        _safe_log_warning(f"Conflicting environment variables detected: {', '.join(conflicting_vars)}")
        _safe_log_warning("These may interfere with MiniMax API calls")
    
    # Test API key format
    api_key = api_key_sources['config'] or api_key_sources['env'] or api_key_sources['g_object']
    if api_key:
        _safe_log_info(f"API Key length: {len(api_key)} characters")
        _safe_log_info(f"API Key starts with: {api_key[:10]}...")
        if api_key.startswith('Bearer '):
            _safe_log_warning("API key appears to already contain 'Bearer ' prefix")
        if '"' in api_key or "'" in api_key:
            _safe_log_warning("API key contains quotes - this may cause issues")
    
    _safe_log_info("=== End MiniMax Configuration Debug ===")
    return api_key_sources


def validate_minimax_api_key(api_key):
    """Validate MiniMax API key format and provide helpful error messages."""
    if not api_key:
        return False, "API key is missing or empty"
    
    # Check for common issues
    if api_key.startswith('Bearer '):
        return False, "API key should not include 'Bearer ' prefix - remove it"
    
    if '"' in api_key or "'" in api_key:
        return False, "API key contains quotes - remove them"
    
    if len(api_key.strip()) < 20:
        return False, "API key appears too short - verify it's complete"
    
    # Check for placeholder text
    placeholder_indicators = ['your-api-key', 'api-key-here', 'replace-me', 'example']
    if any(indicator in api_key.lower() for indicator in placeholder_indicators):
        return False, "API key appears to be a placeholder - replace with actual key"
    
    return True, "API key format looks valid"


def test_minimax_api_connection(api_key=None, timeout=30):
    """Test MiniMax API connection with the provided key."""
    if not api_key:
        try:
            api_key = current_app.config.get('MINIMAX_API_KEY')
        except RuntimeError:
            api_key = os.environ.get('MINIMAX_API_KEY')
    
    if not api_key:
        return False, "No API key provided"
    
    # Validate key format first
    is_valid, validation_msg = validate_minimax_api_key(api_key)
    if not is_valid:
        return False, f"API key validation failed: {validation_msg}"
    
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Make a simple test request to check authentication
        test_payload = {
            "model": "minimax/minimax-m2:free",
            "messages": [{"role": "user", "content": "test"}],
            "temperature": 0.1,
            "max_tokens": 1
        }
        
        response = requests.post(
            "https://api.minimax.chat/v1/chat/completions",
            headers=headers,
            json=test_payload,
            timeout=timeout
        )
        
        if response.status_code == 200:
            return True, "API connection successful"
        elif response.status_code == 401:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown authentication error')
            return False, f"Authentication failed: {error_msg}"
        elif response.status_code == 429:
            return False, "Rate limit exceeded - try again later"
        else:
            return False, f"API error {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except requests.exceptions.ConnectionError:
        return False, "Connection error - check network connectivity"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def get_minimax_api_key_with_fallback():
    """Get MiniMax API key with comprehensive fallback logic."""
    # Try multiple sources in order of preference
    sources = [
        ('Flask config', lambda: current_app.config.get('MINIMAX_API_KEY')),
        ('Environment variable', lambda: os.environ.get('MINIMAX_API_KEY')),
        ('g object', lambda: getattr(g, 'minimax_api_key', None) if hasattr(g, 'minimax_api_key') else None)
    ]
    
    for source_name, getter in sources:
        try:
            api_key = getter()
            if api_key:
                is_valid, msg = validate_minimax_api_key(api_key)
                if is_valid:
                    _safe_log_info(f"Using API key from {source_name}")
                    return api_key
                else:
                    _safe_log_warning(f"API key from {source_name} is invalid: {msg}")
        except RuntimeError:
            # Skip sources that require app context when not available
            continue
    
    # If no valid key found, try to test connection anyway (for debugging)
    _safe_log_error("No valid MiniMax API key found in any source")
    
    # Try to get any key for testing purposes
    for source_name, getter in sources:
        try:
            api_key = getter()
            if api_key:
                _safe_log_info(f"Testing potentially invalid key from {source_name}")
                success, msg = test_minimax_api_connection(api_key)
                if not success:
                    _safe_log_error(f"Key test failed: {msg}")
                return None
        except RuntimeError:
            continue
    
    return None


def enhanced_make_minimax_request(prompt, system_prompt=None, temperature=0.4, max_tokens=2048):
    """Enhanced MiniMax API request with comprehensive error handling and debugging."""
    # Get API key with fallback logic
    api_key = get_minimax_api_key_with_fallback()
    
    if not api_key:
        raise RuntimeError("No valid MiniMax API key available. Please check your configuration.")
    
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
        
        # Enhanced error handling for specific status codes
        if response.status_code == 401:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown authentication error')
            error_code = error_data.get('error', {}).get('http_code', '401')
            
            _safe_log_error(f"MiniMax API authentication error: {error_msg} (code: {error_code})")
            
            # Provide specific guidance based on error code
            if "invalid api key" in error_msg.lower() or error_code == "2049":
                _safe_log_error("ERROR 2049: Invalid API key. Please check:")
                _safe_log_error("1. API key is correct and not expired")
                _safe_log_error("2. API key format is correct (no Bearer prefix, no quotes)")
                _safe_log_error("3. No conflicting environment variables (ANTHROPIC_AUTH_TOKEN, etc.)")
                _safe_log_error("4. API key matches the correct region/group ID if applicable")
            
            raise RuntimeError(f"Authentication failed: {error_msg}")
        
        elif response.status_code == 429:
            raise RuntimeError("Rate limit exceeded. Please wait and try again.")
        
        elif response.status_code >= 500:
            raise RuntimeError(f"Server error: {response.status_code} - {response.text}")
        
        else:
            raise RuntimeError(f"API error: {response.status_code} - {response.text}")
            
    except requests.exceptions.RequestException as e:
        _safe_log_error(f"Network error during MiniMax API request: {e}")
        raise RuntimeError(f"Network error: {str(e)}")


def setup_minimax_environment():
    """Setup function to configure MiniMax environment properly."""
    # Debug current configuration
    debug_minimax_configuration()
    
    # Test API connection if key is available
    api_key = get_minimax_api_key_with_fallback()
    if api_key:
        _safe_log_info("Testing MiniMax API connection...")
        success, msg = test_minimax_api_connection(api_key)
        if success:
            _safe_log_info(f"✓ MiniMax API connection successful: {msg}")
        else:
            _safe_log_error(f"✗ MiniMax API connection failed: {msg}")
            _safe_log_error("Please fix the above issues before using MiniMax services")
    else:
        _safe_log_warning("No MiniMax API key found - MiniMax services will not be available")


# Enhanced version of the original functions with better error handling
def generate_code_from_prompt_enhanced(prompt_text):
    """Enhanced code generation with comprehensive error handling."""
    try:
        system_prompt = (
            "You are a code generation expert. "
            "Based on the following prompt, generate only the code block requested. "
            "Do not include any explanation, preamble, or markdown formatting. "
            "Just return the raw code and one line comments where necessary."
        )
        
        full_prompt = f'PROMPT: "{prompt_text}"'
        
        result = enhanced_make_minimax_request(
            full_prompt, 
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=819200
        )
        return result
        
    except Exception as e:
        _safe_log_error(f"Enhanced MiniMax API error (generation): {e}")
        return f"Error: Could not generate code. {str(e)}"


def explain_code_enhanced(code_to_explain):
    """Enhanced code explanation with comprehensive error handling."""
    try:
        system_prompt = "You are a code analysis expert. Provide clear, structured explanations using simple language."
        prompt = f"Explain this code:\n```\n{code_to_explain[:4000]}\n```"
        
        result = enhanced_make_minimax_request(
            prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )
        return result
        
    except Exception as e:
        _safe_log_error(f"Enhanced MiniMax API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"


def suggest_tags_for_code_enhanced(code_to_analyze):
    """Enhanced tag suggestion with comprehensive error handling."""
    try:
        system_prompt = "You are a code tagging expert. Generate 3-5 relevant, lowercase tags separated by commas."
        prompt = f"Generate tags for this code:\n```\n{code_to_analyze[:3000]}\n```"
        
        result = enhanced_make_minimax_request(
            prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=100
        )
        
        # Clean and return tags
        parts = [t.strip().lower() for t in result.replace("\n", ",").split(",") if t.strip()]
        return ",".join(parts[:5])
        
    except Exception as e:
        _safe_log_error(f"Enhanced MiniMax API error (tagging): {e}")
        return f"Error: Could not suggest tags. {str(e)}"


if __name__ == "__main__":
    # Run setup and debugging when script is executed directly
    print("Setting up MiniMax environment...")
    setup_minimax_environment()
    
    # Test basic functionality if API key is available
    api_key = get_minimax_api_key_with_fallback()
    if api_key:
        print("\nTesting basic API functionality...")
        success, msg = test_minimax_api_connection(api_key)
        print(f"Connection test: {'✓ SUCCESS' if success else '✗ FAILED'}")
        print(f"Message: {msg}")
    else:
        print("\nNo API key available for testing")
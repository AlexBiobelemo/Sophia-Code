"""Minimax AI Service using puter.js for code generation and explanations."""

import time
import random
from typing import Callable, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from flask import current_app

# Import enhanced MiniMax fix
from minimax_api_fix import (
    debug_minimax_configuration,
    validate_minimax_api_key,
    get_minimax_api_key_with_fallback,
    test_minimax_api_connection
)


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

# Availability flag for the minimax service
MINIMAX_AVAILABLE = True

# Model configuration for minimax-m2
MINIMAX_MODEL_NAME = "minimax/minimax-m2:free"
DEFAULT_MAX_INPUT_TOKENS = 12000
DEFAULT_MAX_OUTPUT_TOKENS = 2048
REQUEST_TIMEOUT_SECONDS = 300
MAX_RETRIES = 3
BACKOFF_BASE = 1.5
BACKOFF_MAX = 8

# Per-request metadata for UI banners
LAST_META = {
    'retries': False,
    'retry_attempts': 0,
    'chunked': False,
    'provider': 'minimax'
}


def _count_tokens_estimate(text):
    """Provides a rough estimate of token count for input validation."""
    return len(text) // 4


def _validate_input_size(text, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS):
    """Validates that input text doesn't exceed reasonable token limits."""
    estimated_tokens = _count_tokens_estimate(text)
    if estimated_tokens > max_input_tokens:
        return False, f"Input too large ({estimated_tokens} estimated tokens, max {max_input_tokens}). Please reduce input size."
    return True, None


def _get_api_key():
    """Get Minimax API key from configuration with enhanced fallback logic."""
    # Use the enhanced key retrieval from the fix
    api_key = get_minimax_api_key_with_fallback()
    
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured. Please set the MINIMAX_API_KEY environment variable.")
    return api_key


def _is_retryable_exception(e: Exception) -> bool:
    """Check if exception is retryable."""
    msg = str(e).lower()
    return any(code in msg for code in ["500", "502", "503", "504"]) or "timeout" in msg or "timed out" in msg or "rate" in msg or "temporarily" in msg


def _call_with_timeout(fn: Callable[[], any], timeout_seconds: int):
    """Call function with timeout."""
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn)
    try:
        return fut.result(timeout=timeout_seconds)
    except FuturesTimeout as te:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        raise TimeoutError(f"Operation timed out after {timeout_seconds}s") from te
    except Exception:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        raise
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


def _call_with_retries(fn: Callable[[], any], operation_name: str):
    """Call function with retries."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            try:
                timeout_secs = int(current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS', REQUEST_TIMEOUT_SECONDS))
            except RuntimeError:
                # Working outside of application context
                timeout_secs = REQUEST_TIMEOUT_SECONDS
                
            result = _call_with_timeout(fn, timeout_secs)
            if attempt > 1:
                LAST_META['retries'] = True
                LAST_META['retry_attempts'] = attempt - 1
            return result
        except Exception as e:
            last_err = e
            if not _is_retryable_exception(e) or attempt == MAX_RETRIES:
                _safe_log_error(f"Minimax API error ({operation_name}): {e}")
                raise
            delay = min(BACKOFF_MAX, (BACKOFF_BASE ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            sleep_for = delay + jitter
            _safe_log_warning(f"Transient error during {operation_name} (attempt {attempt}/{MAX_RETRIES}). Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
    raise last_err if last_err else RuntimeError(f"Unknown error during {operation_name}")


def _make_minimax_request(prompt, system_prompt=None, temperature=0.4, max_tokens=2048):
    """Make request to Minimax API using enhanced error handling."""
    # Import the enhanced function
    from minimax_api_fix import enhanced_make_minimax_request
    
    try:
        return enhanced_make_minimax_request(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    except Exception as e:
        # Fallback to original error handling
        _safe_log_error(f"Enhanced MiniMax request failed: {e}")
        raise RuntimeError(f"MiniMax API error: {e}")


def generate_code_from_prompt(prompt_text):
    """Generate code from prompt using Minimax-m2."""
    # Debug configuration at the start
    debug_minimax_configuration()
    
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'minimax'
    
    try:
        is_valid, error_msg = _validate_input_size(prompt_text, max_input_tokens=200000)
        if not is_valid:
            _safe_log_error(f"Input validation failed: {error_msg}")
            return error_msg
        
        system_prompt = (
            "You are a code generation expert. "
            "Based on the following prompt, generate only the code block requested. "
            "Do not include any explanation, preamble, or markdown formatting. "
            "Just return the raw code and one line comments where necessary."
        )
        
        full_prompt = f'PROMPT: "{prompt_text}"'
        
        def _do_call():
            return _make_minimax_request(
                full_prompt, 
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=819200
            )
        
        result = _call_with_retries(_do_call, "code generation")
        return result
        
    except Exception as e:
        _safe_log_error(f"Minimax API error (generation): {e}")
        
        # Show tooltip for API errors
        if "401" in str(e) or "invalid api key" in str(e).lower():
            # This would trigger JavaScript tooltip in web interface
            tooltip_content = f"""API Error 401: Invalid API Key

Error: {str(e)}

Hover for troubleshooting steps:
1. Check MINIMAX_API_KEY environment variable
2. Ensure API key format is correct (no Bearer prefix, no quotes)
3. Remove conflicting environment variables (GEMINI_API_KEY, etc.)
4. Verify API key is not expired or revoked
5. Test connection with: python test_minimax_fix.py"""
        else:
            tooltip_content = f"""MiniMax API Error

Error: {str(e)}

Check the application logs for detailed troubleshooting steps."""
        
        return f"""Error: Could not generate code. {str(e)}

Troubleshooting:
1. Check your MINIMAX_API_KEY environment variable
2. Ensure the API key format is correct (no Bearer prefix, no quotes)
3. Remove conflicting environment variables (ANTHROPIC_AUTH_TOKEN, etc.)
4. Test your API key with: python test_minimax_fix.py"""


def explain_code(code_to_explain):
    """Generate explanation for code using Minimax-m2 with enhanced error handling and fallback."""
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'minimax'
    
    try:
        # Reduce maximum input tokens for this function
        is_valid, error_msg = _validate_input_size(code_to_explain, max_input_tokens=8000)
        if not is_valid:
            _safe_log_error(f"Input validation failed: {error_msg}")
            return error_msg
        
        # Simplified system prompt to reduce complexity
        system_prompt = "You are a code analysis expert. Provide clear, structured explanations using simple language."
        
        # Simplified prompt
        prompt = f"Explain this code:\n```\n{code_to_explain[:4000]}\n```"
        
        # Use centralized request function
        result = _make_minimax_request(
            prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )
        
        return result
        
    except Exception as e:
        _safe_log_error(f"Minimax API error (explanation): {e}")
        
        # FALLBACK: Provide a basic explanation when MiniMax fails
        _safe_log_warning("Falling back to basic explanation due to MiniMax API error")
        return _generate_fallback_explanation(code_to_explain)


def _generate_fallback_explanation(code):
    """Generate fallback explanation using simple heuristics when AI fails."""
    import re
    
    # Detect programming language
    language = "Unknown"
    if 'def ' in code and ('import ' in code or 'from ' in code):
        language = "Python"
    elif 'function ' in code and ('var ' in code or 'let ' in code):
        language = "JavaScript"
    elif 'class ' in code and '{' in code:
        language = "Java"
    elif '#include' in code:
        language = "C++"
    
    # Count lines of code
    lines = code.strip().split('\n')
    code_lines = [line for line in lines if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('//')]
    
    explanation = f"## Code Explanation\n\n"
    explanation += f"**Language:** {language}\n\n"
    explanation += f"**Lines of Code:** {len(code_lines)}\n\n"
    
    # Basic functionality detection
    functions = re.findall(r'def\s+(\w+)\s*\(', code)
    classes = re.findall(r'class\s+(\w+)\s*', code)
    imports = re.findall(r'import\s+(\w+)', code)
    
    explanation += "## Overview\n\n"
    explanation += "This code appears to be a "
    
    if classes:
        explanation += f"class-based implementation with {len(classes)} class(es) ({', '.join(classes)}). "
    if functions:
        explanation += f"It contains {len(functions)} function(s) ({', '.join(functions)}). "
    if imports:
        explanation += f"The code imports {len(imports)} module(s) ({', '.join(imports[:3])}{'...' if len(imports) > 3 else ''}). "
    
    explanation += "\n\n## Key Components\n\n"
    
    # Analyze imports for dependencies
    if imports:
        explanation += "### Dependencies\n"
        for imp in imports[:5]:  # Show first 5 imports
            explanation += f"- {imp}\n"
        explanation += "\n"
    
    # Analyze functions/methods
    if functions:
        explanation += "### Functions\n"
        for func in functions[:5]:  # Show first 5 functions
            explanation += f"- `{func}()`: Custom function\n"
        explanation += "\n"
    
    # Basic complexity analysis
    explanation += "## Complexity Analysis\n\n"
    explanation += "**Time Complexity:** O(n) - Linear time complexity based on the structure.\n\n"
    explanation += "**Space Complexity:** O(1) - Constant space usage (assumes no large data structures).\n\n"
    
    # Edge cases
    explanation += "## Edge Cases\n\n"
    explanation += "- Input validation should be handled for user-provided data\n"
    explanation += "- Error handling should be implemented for API calls or file operations\n"
    explanation += "- Consider bounds checking for array/list operations\n\n"
    
    # Recommendations
    explanation += "## Recommendations\n\n"
    explanation += "1. **Add error handling** for robustness\n"
    explanation += "2. **Include input validation** to prevent unexpected behavior\n"
    explanation += "3. **Add comments** to explain complex logic\n"
    explanation += "4. **Consider performance** optimizations if dealing with large datasets\n"
    explanation += "5. **Write unit tests** to verify functionality\n\n"
    
    explanation += "*Note: This is a basic analysis. For detailed explanations, please ensure the AI service is working properly.*"
    
    return explanation


def format_code_with_ai(code_to_format: str, language_hint: str = None) -> str:
    """Format code using Minimax-m2."""
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'minimax'
    
    try:
        is_valid, error_msg = _validate_input_size(code_to_format, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
        if not is_valid:
            _safe_log_error(f"Input validation failed: {error_msg}")
            return error_msg
        
        system_prompt = (
            "You are a code formatting expert. Format the following code with proper indentation, spacing, and style. "
            "Add one-line comments where necessary to clarify complex logic. "
            "Preserve the original functionality and logic. "
            "Return ONLY the formatted code, no explanations, no markdown formatting, no code blocks."
        )
        
        lang_line = f"Language: {language_hint}\n" if language_hint else ""
        prompt = f"{lang_line}CODE TO FORMAT:\n```\n{code_to_format}\n```\n\nFORMATTED CODE:"
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=819200
            )
        
        result = _call_with_retries(_do_call, "code formatting")
        return result
        
    except Exception as e:
        _safe_log_error(f"Minimax API error (formatting): {e}")
        return f"Error: Could not format code. {str(e)}"


def suggest_tags_for_code(code_to_analyze):
    """Suggest tags for code using Minimax-m2 with enhanced error handling and fallback."""
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'minimax'
    
    try:
        # Reduce maximum input tokens for this function
        is_valid, error_msg = _validate_input_size(code_to_analyze, max_input_tokens=6000)
        if not is_valid:
            _safe_log_error(f"Input validation failed: {error_msg}")
            return error_msg
        
        # Simplified system prompt to reduce complexity
        system_prompt = "You are a code tagging expert. Generate 3-5 relevant, lowercase tags separated by commas."
        
        # Simplified prompt with truncated code
        prompt = f"Generate tags for this code:\n```\n{code_to_analyze[:3000]}\n```"
        
        # Use centralized request function
        result = _make_minimax_request(
            prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=100
        )
        
        # Clean and return tags
        parts = [t.strip().lower() for t in result.replace("\n", ",").split(",") if t.strip()]
        return ",".join(parts[:5])
        
    except Exception as e:
        _safe_log_error(f"Minimax API error (tagging): {e}")
        
        # FALLBACK: Use simple heuristic tag generation when MiniMax fails
        _safe_log_warning("Falling back to heuristic tag generation due to MiniMax API error")
        return _generate_fallback_tags(code_to_analyze)


def _generate_fallback_tags(code):
    """Generate fallback tags using simple heuristics when AI fails."""
    import re
    
    # Convert to lowercase for analysis
    code_lower = code.lower()
    
    # Programming language detection
    language_tags = []
    if 'def ' in code or 'import ' in code or 'from ' in code:
        language_tags.append('python')
    elif 'function ' in code or 'var ' in code or 'let ' in code or 'const ' in code:
        language_tags.append('javascript')
    elif 'class ' in code and '{' in code:
        language_tags.append('java')
    elif '#include' in code or 'int main' in code:
        language_tags.append('cpp')
    elif 'function' in code and 'end' in code:
        language_tags.append('ruby')
    
    # Framework/library detection
    framework_tags = []
    if 'flask' in code_lower or 'from flask' in code_lower:
        framework_tags.append('flask')
    elif 'react' in code_lower or 'jsx' in code_lower:
        framework_tags.append('react')
    elif 'django' in code_lower:
        framework_tags.append('django')
    elif 'express' in code_lower:
        framework_tags.append('express')
    elif 'pandas' in code_lower or 'pd.' in code_lower:
        framework_tags.append('pandas')
    elif 'numpy' in code_lower or 'np.' in code_lower:
        framework_tags.append('numpy')
    
    # Algorithm/pattern detection
    algorithm_tags = []
    if 'def binary_search' in code_lower or 'binary search' in code_lower:
        algorithm_tags.append('binary-search')
    elif 'def quicksort' in code_lower or 'quick sort' in code_lower:
        algorithm_tags.append('sorting')
    elif 'def fibonacci' in code_lower or 'fibonacci' in code_lower:
        algorithm_tags.append('dynamic-programming')
    elif 'bfs' in code_lower or 'queue' in code_lower:
        algorithm_tags.append('bfs')
    elif 'dfs' in code_lower or 'stack' in code_lower:
        algorithm_tags.append('dfs')
    elif 'hash' in code_lower or 'dict' in code_lower:
        algorithm_tags.append('hash-table')
    elif 'tree' in code_lower or 'node' in code_lower:
        algorithm_tags.append('tree')
    
    # Data structure detection
    structure_tags = []
    if 'list' in code_lower or 'array' in code_lower:
        structure_tags.append('array')
    if 'dict' in code_lower or '{}' in code:
        structure_tags.append('hashmap')
    if 'set(' in code_lower:
        structure_tags.append('set')
    if 'queue' in code_lower:
        structure_tags.append('queue')
    if 'stack' in code_lower:
        structure_tags.append('stack')
    
    # Combine all tags
    all_tags = language_tags + framework_tags + algorithm_tags + structure_tags
    
    # Remove duplicates and limit to 5
    unique_tags = list(dict.fromkeys(all_tags))  # Preserves order while removing duplicates
    return ",".join(unique_tags[:5]) if unique_tags else "code,programming"


def chat_answer(system_preamble: str, history_pairs: list, user_message: str) -> str:
    """Return a chatbot answer using Minimax-m2."""
    try:
        # Convert history to prompt format for centralized request
        prompt_parts = []
        
        if system_preamble:
            prompt_parts.append(f"System: {system_preamble}")
        
        # Add history (truncate to last ~20 messages for token safety)
        MAX_H = 20
        for m in history_pairs[-MAX_H:]:
            role = m.get('role')
            content = m.get('content', '')
            if role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
            else:
                prompt_parts.append(f"User: {content}")
        
        # Add current user message
        prompt_parts.append(f"User: {user_message}")
        
        # Build the full prompt
        full_prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
        
        def _do_call():
            return _make_minimax_request(
                full_prompt,
                system_prompt=system_preamble,
                temperature=0.7,
                max_tokens=2048
            )
        
        result = _call_with_retries(_do_call, "chat answer")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax chat error: {e}")
        return f"Error: {e}"


def refine_code_with_feedback(current_code: str, error_output: str, language_hint: str = None) -> str:
    """Refine code based on error output using Minimax-m2."""
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'minimax'
    
    try:
        system_prompt = (
            "You are a senior engineer. The user ran the generated code and got the following error/output. "
            "Diagnose the issue and provide a corrected version of the code. Preserve the original intent and public API where possible. "
            "If the error indicates missing imports or environment, include minimal fixes. "
            "Return ONLY the corrected code, no explanations, no markdown."
        )
        
        lang_line = f"Target Language: {language_hint}\n" if language_hint else ""
        prompt = (
            f"{lang_line}ERROR/OUTPUT:\n```\n{error_output}\n```\n\n"
            f"CURRENT CODE:\n```\n{current_code}\n```\n\n"
            "CORRECTED CODE:"
        )
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=819200
            )
        
        result = _call_with_retries(_do_call, "code refinement")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax API error (refinement): {e}")
        return f"Error: Could not refine code. {str(e)}"


# Multi-step solver functions for Minimax
def multi_step_layer1_architecture(prompt_text):
    """Layer 1: Problem Decomposition & Strategy using Minimax."""
    try:
        system_prompt = (
            "You are The Architect - Layer 1 of the Multi-Step Algorithmic Solver Architecture.\n\n"
            "Your goal is to fully understand the problem, identify constraints, handle edge cases, "
            "and select the optimal algorithm. Analyze the problem systematically and provide a "
            "detailed, justified plan and strategic outline.\n\n"
            "Structure your response as:\n"
            "1. Problem Understanding & Requirements Analysis\n"
            "2. Input/Output Specifications & Constraints\n"
            "3. Edge Cases & Boundary Conditions\n"
            "4. Algorithm Selection & Justification\n"
            "5. Implementation Strategy & Approach\n"
            "6. Complexity Analysis (Time & Space)\n"
            "7. Risk Assessment & Potential Challenges"
        )
        
        prompt = f"PROBLEM DESCRIPTION:\n{prompt_text}\n\nProvide a comprehensive architectural analysis and strategic plan."
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=327680
            )
        
        result = _call_with_retries(_do_call, "multi-step layer 1 architecture")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax Multi-step Layer 1 error: {e}")
        return f"Error: Could not generate architectural plan. {str(e)}"


def multi_step_layer2_coder(architecture_plan):
    """Layer 2: Code Generation using Minimax."""
    try:
        system_prompt = (
            "You are The Coder - Layer 2 of the Multi-Step Algorithmic Solver Architecture.\n\n"
            "Your goal is to generate clean, fully commented, and robust code based strictly "
            "on the architectural plan from Layer 1. Follow the strategic outline precisely "
            "and implement a complete, executable solution.\n\n"
            "Requirements:\n"
            "- Follow the architecture plan exactly\n"
            "- Include comprehensive inline comments\n"
            "- Handle edge cases as identified in Layer 1\n"
            "- Use clear variable names and proper formatting\n"
            "- Ensure the code is production-ready\n"
            "- Return ONLY the code, no explanations or markdown"
        )
        
        prompt = f"ARCHITECTURE PLAN:\n{architecture_plan}\n\nGENERATE THE COMPLETE CODE:"
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=655360
            )
        
        result = _call_with_retries(_do_call, "multi-step layer 2 coder")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax Multi-step Layer 2 error: {e}")
        return f"Error: Could not generate code. {str(e)}"


def multi_step_layer3_tester(code_block, test_cases=None):
    """Layer 3: Verification & Debugging using Minimax."""
    try:
        system_prompt = (
            "You are The Tester - Layer 3 of the Multi-Step Algorithmic Solver Architecture.\n\n"
            "Your goal is to rigorously test the generated code using provided or self-generated "
            "test cases, identify bugs, and produce the corrected solution.\n\n"
            "Process:\n"
            "1. Analyze the code for potential bugs and edge cases\n"
            "2. Generate comprehensive test cases covering:\n"
            "   - Normal cases\n"
            "   - Edge cases\n"
            "   - Boundary conditions\n"
            "   - Error scenarios\n"
            "3. Simulate execution and identify issues\n"
            "4. Provide corrected code if needed\n"
            "5. Document any bugs found and fixes applied"
        )
        
        test_cases_section = f"\nADDITIONAL TEST CASES:\n{test_cases}" if test_cases else ""
        prompt = f"GENERATED CODE:\n```\n{code_block}\n```\n{test_cases_section}\n\nProvide your verification analysis and corrected code (if any fixes were needed)."
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=491520
            )
        
        result = _call_with_retries(_do_call, "multi-step layer 3 tester")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax Multi-step Layer 3 error: {e}")
        return f"Error: Could not verify and debug code. {str(e)}"


def multi_step_layer4_refiner(verified_code, complexity_analysis=None):
    """Layer 4: Optimization & Final Review using Minimax."""
    try:
        system_prompt = (
            "You are The Refiner - Layer 4 of the Multi-Step Algorithmic Solver Architecture.\n\n"
            "Your goal is to analyze the time and space complexity and optimize the solution "
            "for efficiency (if possible). Provide the final optimized code and complexity summary.\n\n"
            "Tasks:\n"
            "1. Analyze current time and space complexity\n"
            "2. Identify potential optimizations\n"
            "3. Apply optimizations while maintaining correctness\n"
            "4. Provide final optimized code\n"
            "5. Give detailed complexity analysis (Big O notation)\n"
            "6. Explain optimization techniques used"
        )
        
        complexity_section = f"\nCOMPLEXITY ANALYSIS:\n{complexity_analysis}" if complexity_analysis else ""
        prompt = f"VERIFIED CODE:\n```\n{verified_code}\n```\n{complexity_section}\n\nProvide the final optimized solution with comprehensive complexity analysis."
        
        def _do_call():
            return _make_minimax_request(
                prompt, 
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=491520
            )
        
        result = _call_with_retries(_do_call, "multi-step layer 4 refiner")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax Multi-step Layer 4 error: {e}")
        return f"Error: Could not optimize and finalize code. {str(e)}"


def multi_step_complete_solver(prompt_text, test_cases=None):
    """Complete Multi-Step Algorithmic Solver using Minimax."""
    start_time = time.time()
    try:
        # Layer 1: Architecture
        layer1_result = multi_step_layer1_architecture(prompt_text)
        if layer1_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer1_result, "layer": 1, "processing_time": processing_time}
        
        # Layer 2: Code Generation
        layer2_result = multi_step_layer2_coder(layer1_result)
        if layer2_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer2_result, "layer": 2, "layer1": layer1_result, "processing_time": processing_time}
        
        # Layer 3: Testing & Debugging
        layer3_result = multi_step_layer3_tester(layer2_result, test_cases)
        if layer3_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer3_result, "layer": 3, "layer1": layer1_result, "layer2": layer2_result, "processing_time": processing_time}
        
        # Layer 4: Optimization & Final Review
        layer4_result = multi_step_layer4_refiner(layer3_result)
        if layer4_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer4_result, "layer": 4, "layer1": layer1_result, "layer2": layer2_result, "layer3": layer3_result, "processing_time": processing_time}
        
        processing_time = time.time() - start_time
        return {
            "success": True,
            "layer1_architecture": layer1_result,
            "layer2_coder": layer2_result,
            "layer3_tester": layer3_result,
            "layer4_refiner": layer4_result,
            "final_code": layer4_result,
            "processing_time": processing_time
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        current_app.logger.error(f"Minimax Multi-step complete solver error: {e}")
        return {"error": f"Multi-step solver failed: {str(e)}", "processing_time": processing_time}


# Streaming functions (placeholder implementations)
def stream_code_generation(prompt_text, session_id=None):
    """Stream code generation using Minimax (placeholder - requires streaming API)."""
    # For now, generate complete response and yield it
    try:
        code = generate_code_from_prompt(prompt_text)
        if not code.startswith("Error:"):
            yield {
                "type": "code_complete",
                "content": code,
                "status": "completed"
            }
        else:
            yield {
                "type": "error",
                "error": code,
                "status": "error"
            }
    except Exception as e:
        yield {
            "type": "error",
            "error": f"Streaming failed: {str(e)}",
            "status": "error"
        }


def stream_code_explanation(code_content, session_id=None, original_prompt=None):
    """Stream code explanation using Minimax (placeholder - requires streaming API)."""
    try:
        explanation = explain_code(code_content)
        if not explanation.startswith("Error:"):
            yield {
                "type": "explanation_complete",
                "content": explanation,
                "status": "completed"
            }
        else:
            yield {
                "type": "error",
                "error": explanation,
                "status": "error"
            }
    except Exception as e:
        yield {
            "type": "error",
            "error": f"Streaming explanation failed: {str(e)}",
            "status": "error"
        }


def chained_streaming_generation(prompt_text, session_id=None, code_model=None, explanation_model=None):
    """Complete token-efficient chaining pipeline with streaming (placeholder)."""
    try:
        yield {
            "type": "pipeline_start",
            "status": "starting_code_generation"
        }
        
        # Generate code
        code_content = generate_code_from_prompt(prompt_text)
        if code_content.startswith("Error:"):
            yield {
                "type": "error",
                "error": code_content,
                "status": "error"
            }
            return
        
        yield {
            "type": "step_complete",
            "step": 1,
            "content": code_content,
            "status": "completed",
            "next_step": "generating_explanation"
        }
        
        # Generate explanation
        explanation_content = explain_code(code_content)
        if explanation_content.startswith("Error:"):
            yield {
                "type": "error",
                "error": explanation_content,
                "status": "error"
            }
            return
        
        yield {
            "type": "pipeline_complete",
            "code": code_content,
            "explanation": explanation_content,
            "status": "completed"
        }
        
    except Exception as e:
        yield {
            "type": "error",
            "error": f"Pipeline failed: {str(e)}",
            "status": "error"
        }


# Placeholder for embedding generation (Minimax doesn't have embedding API)
def generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    """Generate embedding for text (placeholder - Minimax doesn't have embedding API)."""
    _safe_log_warning("Minimax does not provide embedding API. Returning None.")
    return None


def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    import numpy as np
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return np.dot(v1, v2) / (norm_v1 * norm_v2)


# Model tiering configuration for Minimax
MINIMAX_MODEL_TIERING_CONFIG = {
    "code_generation": {
        "primary": MINIMAX_MODEL_NAME,
        "fallback": MINIMAX_MODEL_NAME,
        "cost_optimized": MINIMAX_MODEL_NAME
    },
    "explanation": {
        "primary": MINIMAX_MODEL_NAME,
        "fallback": MINIMAX_MODEL_NAME,
        "cost_optimized": MINIMAX_MODEL_NAME
    }
}


def get_model_for_task(task_type, tier="primary"):
    """Get appropriate model for task with tiering support."""
    return MINIMAX_MODEL_TIERING_CONFIG.get(task_type, {}).get(tier, MINIMAX_MODEL_NAME)


# LeetCode-specific functions
def generate_leetcode_solution(problem_title, problem_description, language):
    """Generate LeetCode solution using Minimax-m2."""
    try:
        system_prompt = (
            f"You are an expert LeetCode solution generator. "
            f"Generate a complete, correct, and efficient solution in {language} for the following LeetCode problem. "
            f"Provide only the code, without any explanation, preamble, or markdown formatting. "
        )
        
        full_prompt = (
            f"Problem Title: {problem_title}\n"
            f"Problem Description: {problem_description}\n\n"
            f"SOLUTION ({language}):"
        )
        
        def _do_call():
            return _make_minimax_request(
                full_prompt,
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=819200
            )
        
        result = _call_with_retries(_do_call, "leetcode solution generation")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax API error (leetcode solution generation): {e}")
        return f"Error: Could not generate solution. {str(e)}"


def explain_leetcode_solution(solution_code, problem_title, language):
    """Explain LeetCode solution using Minimax-m2."""
    try:
        system_prompt = (
            f"You are an expert at explaining LeetCode solutions. "
            f"Provide a concise but educative explanation for the following {language} solution to the problem '{problem_title}'. "
            f"Structure the answer with Markdown headings and cover:\n"
            f"1. Overview & Intent — what the solution achieves and why this approach.\n"
            f"2. Strategy & Key Ideas — the algorithm/pattern and data structures used.\n"
            f"3. Step-by-Step Walkthrough — the core flow; keep it brief and focused.\n"
            f"4. Correctness Argument — why this works for all cases.\n"
            f"5. Time Complexity — Big-O with a short justification.\n"
            f"6. Space Complexity — Big-O with a short justification.\n"
            f"7. Edge Cases & Pitfalls — tricky inputs and how the code handles them.\n"
            f"8. Possible Improvements/Alternatives — if applicable.\n"
            f"Do not wrap the entire response in a single code block."
        )
        
        prompt = (
            f"SOLUTION ({language}):\n"
            f"```\n{solution_code}\n```"
        )
        
        def _do_call():
            return _make_minimax_request(prompt, system_prompt=system_prompt, temperature=0.3)
        
        result = _call_with_retries(_do_call, "leetcode explanation")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"


def classify_leetcode_solution(solution_code, problem_description):
    """Classify LeetCode solution using Minimax-m2."""
    try:
        system_prompt = (
            "You are an expert in LeetCode problem classification. "
            "Analyze the following problem description and its solution. "
            "Generate a comma-separated list of 3 to 5 relevant classifications "
            "(e.g., 'Dynamic Programming', 'Two Pointers', 'BFS', 'Array', 'Hash Table'). "
            "Do not include any explanation, markdown, or other text. "
            "Example output: Dynamic Programming,Array,Hash Table"
        )
        
        prompt = (
            f"PROBLEM DESCRIPTION:\n{problem_description}\n\n"
            f"SOLUTION CODE:\n```\n{solution_code}\n```"
        )
        
        def _do_call():
            return _make_minimax_request(prompt, system_prompt=system_prompt, temperature=0.3)
        
        result = _call_with_retries(_do_call, "leetcode classification")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Minimax API error (classification): {e}")
        return f"Error: Could not classify solution. {str(e)}"


# Alias for compatibility with router import
MODEL_TIERING_CONFIG = MINIMAX_MODEL_TIERING_CONFIG
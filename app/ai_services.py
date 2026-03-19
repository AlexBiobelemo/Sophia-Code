"""Gemini AI Service - All AI features using Google Gemini API."""

from flask import current_app, g
import google.generativeai as genai
import numpy as np
import time
import random
from typing import Callable, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# Model mapping from user preferences to actual API model names
MODEL_MAPPING = {
    'gemini-2.5-flash': 'gemini-2.5-flash',
    'gemini-2.5-pro': 'gemini-2.5-pro',
    'gemini-3-pro': 'gemini-3-pro',
}

DEFAULT_MODEL = 'gemini-2.5-flash'
MODEL_NAME = DEFAULT_MODEL  # Will be dynamically set based on user preference
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
    'provider': 'gemini'
}

# Model tiering configuration
MODEL_TIERING_CONFIG = {
    "code_generation": {
        "primary": "gemini-2.5-flash",
        "fallback": "gemini-1.5-flash",
        "cost_optimized": "gemini-1.5-flash"
    },
    "explanation": {
        "primary": "gemini-1.5-flash",
        "fallback": "gemini-1.5-flash",
        "cost_optimized": "gemini-1.5-flash"
    }
}


def get_user_preferred_model():
    """Get the current user's preferred AI model."""
    try:
        if hasattr(g, 'user_preferred_model'):
            return g.user_preferred_model
        if hasattr(current_app, 'login_manager') and hasattr(current_app.login_manager, 'current_user'):
            user = current_app.login_manager.current_user
            if user and hasattr(user, 'preferred_ai_model'):
                return user.preferred_ai_model
    except Exception:
        pass
    return 'gemini-2.5-flash'


def get_api_model_name(user_preferred_model):
    """Get the actual API model name based on user's preferred model."""
    return MODEL_MAPPING.get(user_preferred_model, DEFAULT_MODEL)


def update_global_model_name():
    """Update the global MODEL_NAME based on current user's preference."""
    global MODEL_NAME
    preferred_model = get_user_preferred_model()
    MODEL_NAME = get_api_model_name(preferred_model)


def _count_tokens_estimate(text):
    """Provides a rough estimate of token count for input validation."""
    return len(text) // 4


def _validate_input_size(text, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS):
    """Validates that input text doesn't exceed reasonable token limits."""
    estimated_tokens = _count_tokens_estimate(text)
    if estimated_tokens > max_input_tokens:
        return False, f"Input too large ({estimated_tokens} estimated tokens, max {max_input_tokens}). Please reduce input size."
    return True, None


def _handle_api_response(response, operation_name):
    """Centralized response handling for Gemini API calls."""
    if hasattr(response, 'prompt_feedback'):
        if hasattr(response.prompt_feedback, 'block_reason'):
            block_reason = response.prompt_feedback.block_reason
            if block_reason and block_reason != 0:
                error_msg = f"Input blocked by API. Reason: {block_reason}"
                current_app.logger.error(f"Gemini API error ({operation_name}): {error_msg}")
                return False, f"Error: {error_msg}"

    if not response.candidates:
        current_app.logger.error(f"Gemini API error ({operation_name}): No candidates in response. Full response: {response}")
        return False, "Error: The API returned no response candidates."

    candidate = response.candidates[0]
    finish_reason = candidate.finish_reason

    if finish_reason == 1:  # STOP
        if candidate.content.parts:
            return True, candidate.content.parts[0].text.strip()
        else:
            current_app.logger.error(f"Gemini API error ({operation_name}): STOP but no content parts")
            return False, "Error: API completed but returned no content."

    elif finish_reason == 2:  # MAX_TOKENS
        if candidate.content.parts:
            content = candidate.content.parts[0].text.strip()
            current_app.logger.warning(f"Gemini API warning ({operation_name}): Response truncated")
            return True, content + "\n\n[Note: Response may be incomplete due to length limits]"
        else:
            return False, "Error: Output exceeded maximum length."

    elif finish_reason == 3:  # SAFETY
        safety_ratings = candidate.safety_ratings
        safety_reasons = [f"{s.category.name}: {s.probability.name}"
                         for s in safety_ratings if hasattr(s.probability, 'name') and s.probability.name != 'NEGLIGIBLE']
        if safety_reasons:
            reason_str = ', '.join(safety_reasons)
            return False, f"Error: Content blocked due to safety concerns: {reason_str}"
        else:
            return False, "Error: Content blocked due to safety concerns."

    elif finish_reason == 4:  # RECITATION
        return False, "Error: Content blocked due to recitation detection."

    elif finish_reason == 5:  # OTHER
        return False, "Error: Generation stopped for unknown reason."

    else:
        if candidate.content.parts:
            return True, candidate.content.parts[0].text.strip()
        return False, "Error: Unexpected API response format."


def _get_api_key(user_api_key=None, user_use_own_key=False) -> str:
    """Get API key - user's own key if enabled, otherwise app default."""
    # Use provided user API key if enabled
    if user_use_own_key and user_api_key:
        return user_api_key
    
    # Try to get user's API key from current_user if not provided
    if user_api_key is None:
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                if current_user.use_own_api_key and current_user.gemini_api_key:
                    return current_user.gemini_api_key
        except:
            pass

    # Fall back to app's default API key
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        # Check if user has saved a key but not enabled it
        if user_api_key and not user_use_own_key:
            raise RuntimeError("You have saved an API key but haven't enabled it. Please check 'Use my key' in the API key settings.")
        raise RuntimeError("GEMINI_API_KEY is not configured. Please add your API key in the settings or set GEMINI_API_KEY environment variable.")
    return api_key


def _is_retryable_exception(e: Exception) -> bool:
    msg = str(e).lower()
    return any(code in msg for code in ["500", "502", "503", "504"]) or "timeout" in msg or "timed out" in msg or "rate" in msg or "temporarily" in msg


def _call_with_timeout(fn: Callable[[], any], timeout_seconds: int):
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
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            timeout_secs = int(current_app.config.get('AI_REQUEST_TIMEOUT_SECONDS', REQUEST_TIMEOUT_SECONDS))
            result = _call_with_timeout(fn, timeout_secs)
            if attempt > 1:
                LAST_META['retries'] = True
                LAST_META['retry_attempts'] = attempt - 1
            return result
        except Exception as e:
            last_err = e
            if not _is_retryable_exception(e) or attempt == MAX_RETRIES:
                current_app.logger.error(f"Gemini API error ({operation_name}): {e}")
                raise
            delay = min(BACKOFF_MAX, (BACKOFF_BASE ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            sleep_for = delay + jitter
            current_app.logger.warning(f"Transient error during {operation_name} (attempt {attempt}/{MAX_RETRIES}). Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
    raise last_err if last_err else RuntimeError(f"Unknown error during {operation_name}")


def _chunk_text_by_tokens(text: str, max_tokens: int) -> List[str]:
    """Chunk text by approximate token count with light overlap for context."""
    if not text:
        return [""]
    max_chars = max(1000, int(max_tokens * 4 * 0.9))
    overlap = min(400, max_chars // 10)
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = end - overlap
    return chunks


# ============================================================================
# MAIN AI SERVICE FUNCTIONS
# ============================================================================

def generate_code_from_prompt(prompt_text):
    """Generate code from prompt using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        is_valid, error_msg = _validate_input_size(prompt_text, max_input_tokens=200000)
        if not is_valid:
            current_app.logger.error(f"Input validation failed: {error_msg}")
            return error_msg

        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.4,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 819200,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        full_prompt = (
            "You are a code generation expert. "
            "Based on the following prompt, generate only the code block requested. "
            "Do not include any explanation, preamble, or markdown formatting. "
            "Just return the raw code and one line comments where necessary.\n\n"
            f"PROMPT: \"{prompt_text}\""
        )
        def _do_call():
            return model.generate_content(full_prompt)

        response = _call_with_retries(_do_call, "code generation")
        success, result = _handle_api_response(response, "code generation")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (generation): {e}")
        return f"Error: Could not generate code. {str(e)}"


def explain_code(code_to_explain):
    """Generate explanation for code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        is_valid, error_msg = _validate_input_size(code_to_explain, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
        if not is_valid:
            current_app.logger.error(f"Input validation failed: {error_msg}")
            return error_msg

        genai.configure(api_key=_get_api_key())
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME, safety_settings=safety_settings)

        chunks = _chunk_text_by_tokens(code_to_explain, DEFAULT_MAX_INPUT_TOKENS)
        if len(chunks) > 1:
            LAST_META['chunked'] = True
        combined_md = []
        for idx, chunk in enumerate(chunks, start=1):
            prompt = (
                "You are a code analysis expert. Provide clear, structured explanations.\n\n"
                f"CODE (part {idx}/{len(chunks)}):\n```\n{chunk}\n```\n\n"
                "Provide explanation:"
            )
            def _do_call():
                return model.generate_content(prompt)
            response = _call_with_retries(_do_call, f"explanation chunk {idx}")
            success, result = _handle_api_response(response, f"explanation chunk {idx}")
            if success:
                combined_md.append(result)
        return "\n\n".join(combined_md) if combined_md else "Error: Could not generate explanation."

    except Exception as e:
        current_app.logger.error(f"Gemini API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"


# Alias for backward compatibility
explain_code_for_view_snippet = explain_code


def format_code_with_ai(code_to_format: str, language_hint: str = None) -> str:
    """Format code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        is_valid, error_msg = _validate_input_size(code_to_format, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
        if not is_valid:
            current_app.logger.error(f"Input validation failed: {error_msg}")
            return error_msg

        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are a code formatting expert. Format the following code with proper indentation, spacing, and style. "
            "Add one-line comments where necessary to clarify complex logic. "
            "Preserve the original functionality and logic. "
            "Return ONLY the formatted code, no explanations, no markdown formatting, no code blocks."
        )

        lang_line = f"Language: {language_hint}\n" if language_hint else ""
        prompt = f"{lang_line}CODE TO FORMAT:\n```\n{code_to_format}\n```\n\nFORMATTED CODE:"

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "code formatting")
        success, result = _handle_api_response(response, "code formatting")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (formatting): {e}")
        return f"Error: Could not format code. {str(e)}"


def suggest_tags_for_code(code_to_analyze):
    """Suggest tags for code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        is_valid, error_msg = _validate_input_size(code_to_analyze, max_input_tokens=6000)
        if not is_valid:
            current_app.logger.error(f"Input validation failed: {error_msg}")
            return error_msg

        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        # Much more explicit prompt to force tag-only output
        prompt = (
            "You are a tag generator. Return ONLY 3-5 comma-separated programming tags.\n"
            "NO sentences, NO explanations, NO full stops.\n"
            "Format: tag1,tag2,tag3,tag4,tag5\n\n"
            "Code to analyze:\n```\n" + code_to_analyze[:500] + "\n```\n\n"
            "Tags (just comma-separated words, nothing else):"
        )

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "tag suggestion")
        success, result = _handle_api_response(response, "tag suggestion")

        if success:
            # Clean the result - remove any explanatory text
            result = result.strip().lower()
            
            # If result contains sentences or explanations, try to extract just tags
            if '.' in result or 'the ' in result or 'this ' in result:
                # Try to extract programming-related words
                import re
                # Look for common programming terms
                words = re.findall(r'\b(python|javascript|java|cpp|c\+\+|ruby|go|rust|swift|kotlin|php|html|css|sql|typescript|react|vue|angular|flask|django|express|fastapi|spring|laravel|rails|nodejs|node\.js|api|rest|graphql|database|web|backend|frontend|fullstack|algorithm|data-structure|sorting|search|tree|graph|dynamic-programming|recursion|oop|functional|async|await|promise|callback|http|json|xml|regex|validation|authentication|authorization|encryption|hashing|compression|caching|logging|testing|debugging|deployment|docker|kubernetes|cloud|aws|azure|gcp|microservice|serverless|devops|ci-cd|git|version-control)\b', result.lower())
                if words:
                    result = ','.join(list(dict.fromkeys(words))[:5])  # Remove duplicates, keep first 5
                else:
                    # Fallback: extract first few comma-separated words
                    parts = [t.strip() for t in result.replace("\n", ",").split(",") if t.strip() and len(t.strip()) < 30]
                    result = ','.join(parts[:5])
            else:
                # Result looks like tags already
                parts = [t.strip() for t in result.replace("\n", ",").split(",") if t.strip()]
                result = ','.join(parts[:5])
            
            return result if result else "code,programming"
        return "code,programming"

    except Exception as e:
        current_app.logger.error(f"Gemini API error (tagging): {e}")
        return f"Error: Could not suggest tags. {str(e)}"


def chat_answer(system_preamble: str, history_pairs: list, user_message: str) -> str:
    """Return a chatbot answer using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        messages = []
        if system_preamble:
            messages.append({"role": "user", "parts": [system_preamble]})
        
        MAX_H = 20
        for m in history_pairs[-MAX_H:]:
            role = m.get('role')
            content = m.get('content', '')
            messages.append({"role": "user" if role == 'user' else "model", "parts": [content]})
        
        messages.append({"role": "user", "parts": [user_message]})

        def _do_call():
            return model.generate_content(messages)

        response = _call_with_retries(_do_call, "chat answer")
        success, result = _handle_api_response(response, "chat answer")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (chat): {e}")
        return f"Error: Could not generate chat response. {str(e)}"


def refine_code_with_feedback(current_code: str, error_output: str, language_hint: str = None) -> str:
    """Refine code based on error output using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are a senior engineer. The user ran the generated code and got the following error/output. "
            "Diagnose the issue and provide a corrected version of the code. Preserve the original intent and public API where possible. "
            "Return ONLY the corrected code, no explanations, no markdown."
        )

        lang_line = f"Target Language: {language_hint}\n" if language_hint else ""
        prompt = (
            f"{lang_line}ERROR/OUTPUT:\n```\n{error_output}\n```\n\n"
            f"CURRENT CODE:\n```\n{current_code}\n```\n\n"
            "CORRECTED CODE:"
        )

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "code refinement")
        success, result = _handle_api_response(response, "code refinement")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (refinement): {e}")
        return f"Error: Could not refine code. {str(e)}"


def generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    """Generate embedding for text using Gemini API."""
    try:
        genai.configure(api_key=_get_api_key())
        
        import google.generativeai as genai_embed
        result = genai_embed.embed_content(
            model="models/embedding-001",
            content=text_to_embed,
            task_type=task_type
        )
        return np.array(result['embedding'])
    
    except Exception as e:
        current_app.logger.error(f"Gemini API error (embedding): {e}")
        return None


def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    if v1 is None or v2 is None:
        return 0.0
    v1_arr = np.array(v1) if not isinstance(v1, np.ndarray) else v1
    v2_arr = np.array(v2) if not isinstance(v2, np.ndarray) else v2
    if np.linalg.norm(v1_arr) == 0 or np.linalg.norm(v2_arr) == 0:
        return 0.0
    return np.dot(v1_arr, v2_arr) / (np.linalg.norm(v1_arr) * np.linalg.norm(v2_arr))


# Multi-step solver functions
def multi_step_layer1_architecture(prompt_text):
    """Layer 1: Problem Decomposition & Strategy."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are The Architect - Layer 1 of the Multi-Step Algorithmic Solver.\n\n"
            "Analyze the problem systematically and provide:\n"
            "1. Problem Understanding & Requirements\n"
            "2. Input/Output Specifications\n"
            "3. Edge Cases & Boundary Conditions\n"
            "4. Algorithm Selection & Justification\n"
            "5. Implementation Strategy\n"
            "6. Complexity Analysis"
        )

        prompt = f"PROBLEM:\n{prompt_text}\n\nProvide architectural analysis:"

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "multi-step layer 1")
        success, result = _handle_api_response(response, "multi-step layer 1")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (multi-step layer 1): {e}")
        return f"Error: Could not generate architecture. {str(e)}"


def multi_step_layer2_coder(architecture_plan):
    """Layer 2: Code Generation."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are The Coder - Layer 2 of the Multi-Step Algorithmic Solver.\n\n"
            "Generate clean, commented code based on the architecture plan. "
            "Return ONLY the code, no explanations or markdown."
        )

        prompt = f"ARCHITECTURE:\n{architecture_plan}\n\nGENERATE CODE:"

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "multi-step layer 2")
        success, result = _handle_api_response(response, "multi-step layer 2")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (multi-step layer 2): {e}")
        return f"Error: Could not generate code. {str(e)}"


def multi_step_layer3_tester(code_block, test_cases=None):
    """Layer 3: Verification & Debugging."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are The Tester - Layer 3 of the Multi-Step Algorithmic Solver.\n\n"
            "Test the code rigorously and fix any bugs. Return the corrected code."
        )

        test_info = f"\n\nTEST CASES:\n{test_cases}" if test_cases else ""
        prompt = f"CODE:\n{code_block}\n{test_info}\n\nTEST AND FIX:"

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "multi-step layer 3")
        success, result = _handle_api_response(response, "multi-step layer 3")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (multi-step layer 3): {e}")
        return f"Error: Could not test/fix code. {str(e)}"


def multi_step_layer4_refiner(verified_code, complexity_analysis=None):
    """Layer 4: Optimization & Final Review."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        system_prompt = (
            "You are The Refiner - Layer 4 of the Multi-Step Algorithmic Solver.\n\n"
            "Optimize and finalize the code. Return the final optimized code."
        )

        complexity_info = f"\n\nCOMPLEXITY ANALYSIS:\n{complexity_analysis}" if complexity_analysis else ""
        prompt = f"CODE:\n{verified_code}\n{complexity_info}\n\nOPTIMIZE:"

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "multi-step layer 4")
        success, result = _handle_api_response(response, "multi-step layer 4")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (multi-step layer 4): {e}")
        return f"Error: Could not refine code. {str(e)}"


def multi_step_complete_solver(prompt_text, test_cases=None):
    """Complete Multi-Step Algorithmic Solver."""
    from app.models import MultiStepResult
    
    try:
        result = MultiStepResult()
        
        result.architecture_plan = multi_step_layer1_architecture(prompt_text)
        if result.architecture_plan.startswith("Error:"):
            return result
        
        result.initial_code = multi_step_layer2_coder(result.architecture_plan)
        if result.initial_code.startswith("Error:"):
            return result
        
        result.verified_code = multi_step_layer3_tester(result.initial_code, test_cases)
        if result.verified_code.startswith("Error:"):
            return result
        
        result.final_code = multi_step_layer4_refiner(result.verified_code)
        result.completed = True
        
        return result
    
    except Exception as e:
        current_app.logger.error(f"Multi-step solver error: {e}")
        from app.models import MultiStepResult
        result = MultiStepResult()
        result.error_message = str(e)
        return result


# Streaming functions (using Gemini)
def stream_code_generation(prompt_text, session_id=None, user_api_key=None, user_use_own_key=False):
    """Stream code generation using Gemini."""
    try:
        genai.configure(api_key=_get_api_key(user_api_key, user_use_own_key))
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        prompt = (
            "You are a code generation expert. Generate only the code block requested. "
            "No explanations, no markdown.\n\n"
            f"PROMPT: \"{prompt_text}\""
        )

        response = model.generate_content(prompt, stream=True)

        code_content = ""
        for chunk in response:
            # Check if chunk has valid content
            if hasattr(chunk, 'text') and chunk.text:
                code_content += chunk.text
                yield {
                    "type": "chunk",
                    "content": chunk.text,
                    "status": "streaming"
                }
            # Handle case where chunk exists but has no text
            elif hasattr(chunk, 'parts') and chunk.parts:
                for part in chunk.parts:
                    if hasattr(part, 'text') and part.text:
                        code_content += part.text
                        yield {
                            "type": "chunk",
                            "content": part.text,
                            "status": "streaming"
                        }

        if code_content:
            yield {
                "type": "code_complete",
                "content": code_content,
                "status": "complete"
            }
        else:
            yield {
                "type": "error",
                "error": "No code was generated. Please try again with a more specific prompt.",
                "status": "error"
            }

    except Exception as e:
        current_app.logger.error(f"Gemini streaming error: {e}")
        yield {
            "type": "error",
            "error": str(e),
            "status": "error"
        }


def stream_code_explanation(code_content, session_id=None, original_prompt=None, user_api_key=None, user_use_own_key=False):
    """Stream code explanation using Gemini."""
    try:
        genai.configure(api_key=_get_api_key(user_api_key, user_use_own_key))
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME)

        prompt = f"Explain this code clearly:\n```\n{code_content}\n```"

        response = model.generate_content(prompt, stream=True)

        explanation_content = ""
        for chunk in response:
            # Check if chunk has valid content
            if hasattr(chunk, 'text') and chunk.text:
                explanation_content += chunk.text
                yield {
                    "type": "chunk",
                    "content": chunk.text,
                    "status": "streaming"
                }
            # Handle case where chunk exists but has no text
            elif hasattr(chunk, 'parts') and chunk.parts:
                for part in chunk.parts:
                    if hasattr(part, 'text') and part.text:
                        explanation_content += part.text
                        yield {
                            "type": "chunk",
                            "content": part.text,
                            "status": "streaming"
                        }

        if explanation_content:
            yield {
                "type": "explanation_complete",
                "content": explanation_content,
                "status": "complete"
            }
        else:
            yield {
                "type": "error",
                "error": "No explanation was generated. Please try again.",
                "status": "error"
            }

    except Exception as e:
        current_app.logger.error(f"Gemini streaming error: {e}")
        yield {
            "type": "error",
            "error": str(e),
            "status": "error"
        }


def chained_streaming_generation(prompt_text, session_id=None, code_model=None, explanation_model=None, user_api_key=None, user_use_own_key=False):
    """Complete token-efficient chaining pipeline."""
    def _chain_generator():
        code_content = ""
        for chunk in stream_code_generation(prompt_text, session_id, user_api_key, user_use_own_key):
            yield chunk
            if chunk["type"] == "code_complete":
                code_content = chunk["content"]
                break
            elif chunk["type"] == "error":
                return

        if not code_content:
            yield {
                "type": "error",
                "error": "No code content generated",
                "status": "error"
            }
            return

        for chunk in stream_code_explanation(code_content, session_id, prompt_text, user_api_key, user_use_own_key):
            yield chunk

    return _chain_generator()


def get_model_for_task(task_type, tier="primary"):
    """Get appropriate model for task with tiering support."""
    return MODEL_TIERING_CONFIG.get(task_type, {}).get(tier, MODEL_NAME)

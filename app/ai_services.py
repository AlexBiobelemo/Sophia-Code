"""Multi-provider AI service router supporting Gemini and Minimax."""

from flask import current_app, g
import numpy as np

# Import provider-specific services
try:
    from app.ai_services_minimax import (
        generate_code_from_prompt as minimax_generate_code,
        explain_code as minimax_explain_code,
        format_code_with_ai as minimax_format_code,
        suggest_tags_for_code as minimax_suggest_tags,
        chat_answer as minimax_chat_answer,
        refine_code_with_feedback as minimax_refine_code,
        generate_embedding as minimax_generate_embedding,
        generate_leetcode_solution as minimax_leetcode_solution,
        explain_leetcode_solution as minimax_explain_leetcode_solution,
        classify_leetcode_solution as minimax_classify_leetcode_solution,
        multi_step_layer1_architecture as minimax_multi_step_layer1,
        multi_step_layer2_coder as minimax_multi_step_layer2,
        multi_step_layer3_tester as minimax_multi_step_layer3,
        multi_step_layer4_refiner as minimax_multi_step_layer4,
        multi_step_complete_solver as minimax_multi_step_complete,
        stream_code_generation as minimax_stream_code_generation,
        stream_code_explanation as minimax_stream_code_explanation,
        chained_streaming_generation as minimax_chained_streaming_generation,
        cosine_similarity as minimax_cosine_similarity,
        LAST_META as MINIMAX_LAST_META,
        MODEL_TIERING_CONFIG as MINIMAX_MODEL_TIERING_CONFIG
    )
    MINIMAX_AVAILABLE = True
    print("Minimax services imported successfully")
except Exception as e:
    # Catch any exception, not just ImportError, to help with debugging
    MINIMAX_AVAILABLE = False
    MINIMAX_MODEL_TIERING_CONFIG = None  # Provide fallback
    print(f"Failed to import Minimax services: {e}")
    print("   Falling back to Gemini for all AI operations")

# Import Gemini service (existing functionality)
import google.generativeai as genai
import time
import random
from typing import Callable, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# Model mapping from user preferences to actual API model names
MODEL_MAPPING = {
    'gemini-2.5-flash': 'gemini-2.5-flash',
    'gemini-2.5-pro': 'gemini-2.5-pro',
    'gemini-3-pro': 'gemini-3-pro',
    'minimax-m2': 'minimax/minimax-m2:free'
}

DEFAULT_MODEL = 'gemini-2.5-flash'
MODEL_NAME = DEFAULT_MODEL  # Will be dynamically set based on user preference
DEFAULT_MAX_INPUT_TOKENS = 12000   # conservative estimate to avoid server-side rejections
DEFAULT_MAX_OUTPUT_TOKENS = 2048   # keep responses reasonable to reduce timeouts
REQUEST_TIMEOUT_SECONDS = 300      # default per-request timeout (5 minutes)
MAX_RETRIES = 3                    # transient error retries
BACKOFF_BASE = 1.5                 # exponential backoff base
BACKOFF_MAX = 8                    # max backoff seconds

# Per-request metadata for UI banners
LAST_META = {
    'retries': False,
    'retry_attempts': 0,
    'chunked': False,
    'provider': 'gemini'
}

# Global model tiering configuration that combines both providers
MODEL_TIERING_CONFIG = {
    "code_generation": {
        "primary": "gemini-2.5-flash",  # Default to Gemini
        "fallback": "gemini-1.5-flash",
        "cost_optimized": "gemini-1.5-flash"
    },
    "explanation": {
        "primary": "gemini-1.5-flash",  # Default to Gemini
        "fallback": "gemini-1.5-flash",
        "cost_optimized": "gemini-1.5-flash"
    }
}


def get_user_preferred_model():
    """Get the current user's preferred AI model."""
    try:
        # Try to get from Flask's g object (set by before_request handler)
        if hasattr(g, 'user_preferred_model'):
            return g.user_preferred_model
        # Fallback: get from current_user if available
        if hasattr(current_app, 'login_manager') and hasattr(current_app.login_manager, 'current_user'):
            user = current_app.login_manager.current_user
            if user and hasattr(user, 'preferred_ai_model'):
                return user.preferred_ai_model
    except Exception:
        pass
    # Final fallback to default
    return 'gemini-2.5-flash'


def get_api_model_name(user_preferred_model):
    """Get the actual API model name based on user's preferred model."""
    return MODEL_MAPPING.get(user_preferred_model, DEFAULT_MODEL)


def update_global_model_name():
    """Update the global MODEL_NAME based on current user's preference."""
    global MODEL_NAME
    preferred_model = get_user_preferred_model()
    MODEL_NAME = get_api_model_name(preferred_model)


def debug_ai_provider_selection():
    """Debug function to check current AI provider selection status."""
    try:
        from flask import current_app
        print("\n=== AI Provider Debug Info ===")
        print(f"MINIMAX_AVAILABLE: {MINIMAX_AVAILABLE}")
        
        # Check API keys
        minimax_key = current_app.config.get('MINIMAX_API_KEY')
        gemini_key = current_app.config.get('GEMINI_API_KEY')
        print(f"MINIMAX_API_KEY: {'✓ Set' if minimax_key else '✗ Missing'}")
        print(f"GEMINI_API_KEY: {'✓ Set' if gemini_key else '✗ Missing'}")
        
        # Test provider selection
        preferred_model = get_user_preferred_model()
        print(f"User preferred model: {preferred_model}")
        
        provider, services = _get_provider_and_service(preferred_model)
        print(f"Selected provider: {provider}")
        print(f"Services available: {services is not None}")
        
        print("============================\n")
        
    except Exception as e:
        print(f"Debug function error: {e}")


def _resolve_provider_for_task(task_or_user, task_type: Optional[str] = None) -> Tuple[str, Optional[dict]]:
    """
    Determines which AI provider (Minimax or Gemini) should handle a specific task.
    
    Args:
        task_or_user: Either the task type string (for backward compatibility) or a User object.
        task_type: The type of AI task (e.g., 'code_generation', 'explanation', 'chat'). 
                   Required if first parameter is a User object.
        
    Returns:
        A tuple containing the chosen provider ('minimax' or 'gemini') and the
        corresponding services dictionary or None for Gemini (as Gemini services
        are directly called).
    """
    # Handle both calling patterns: (task_type,) or (user, task_type)
    if task_type is None:
        # Old pattern: _resolve_provider_for_task('code_generation')
        task_type = task_or_user
        preferred_model = get_user_preferred_model()
    else:
        # New pattern: _resolve_provider_for_task(user, 'code_generation')
        user = task_or_user
        if hasattr(user, 'preferred_ai_model'):
            preferred_model = user.preferred_ai_model
        else:
            preferred_model = get_user_preferred_model()
        
    # Logic for when minimax-m2 is selected by the user
    if preferred_model == 'minimax-m2' and MINIMAX_AVAILABLE:
        # When minimax-m2 is selected, ALL AI features should use minimax
        minimax_services = {
            'generate_code_from_prompt': minimax_generate_code,
            'explain_code': minimax_explain_code,
            'refine_code_with_feedback': minimax_refine_code,
            'suggest_tags_for_code': minimax_suggest_tags,
            'chat_answer': minimax_chat_answer,
            'generate_embedding': minimax_generate_embedding,
            'generate_leetcode_solution': minimax_leetcode_solution,
            'explain_leetcode_solution': minimax_explain_leetcode_solution,
            'classify_leetcode_solution': minimax_classify_leetcode_solution,
            'multi_step_layer1_architecture': minimax_multi_step_layer1,
            'multi_step_layer2_coder': minimax_multi_step_layer2,
            'multi_step_layer3_tester': minimax_multi_step_layer3,
            'multi_step_layer4_refiner': minimax_multi_step_layer4,
            'multi_step_complete_solver': minimax_multi_step_complete,
            'stream_code_generation': minimax_stream_code_generation,
            'stream_code_explanation': minimax_stream_code_explanation,
            'chained_streaming_generation': minimax_chained_streaming_generation,
            'cosine_similarity': minimax_cosine_similarity,
            'LAST_META': MINIMAX_LAST_META,
            'MODEL_TIERING_CONFIG': MINIMAX_MODEL_TIERING_CONFIG
        }
        
        # Route all task types to minimax when minimax-m2 is selected
        return 'minimax', minimax_services
    
    # Default to Gemini for all other cases or if Minimax is not available/preferred
    return 'gemini', None


def _update_last_meta_provider(provider):
    """Update LAST_META with provider information."""
    global LAST_META
    LAST_META['provider'] = provider
    if provider == 'minimax' and MINIMAX_AVAILABLE:
        LAST_META.update(MINIMAX_LAST_META)
    # No need to update with Gemini's LAST_META as it's handled internally by its functions


# ============================================================================
# WRAPPER FUNCTIONS THAT ROUTE TO APPROPRIATE PROVIDER
# ============================================================================

def generate_code_from_prompt(prompt_text):
    """Generate code from prompt using user's preferred AI model."""
    provider, services = _resolve_provider_for_task('code_generation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['generate_code_from_prompt'](prompt_text)
    else:
        return _gemini_generate_code_from_prompt(prompt_text)


def explain_code(code_to_explain):
    """Explain code using user's preferred model with hybrid approach.
    When minimax-m2 is selected, this routes to Gemini for the explain button on view snippet page."""
    provider, services = _resolve_provider_for_task('explanation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['explain_code'](code_to_explain)
    else:
        return _gemini_explain_code(code_to_explain)


def explain_code_for_view_snippet(code_to_explain):
    """Explain code specifically for the view snippet page explain button.
    This uses the user's preferred model setting."""
    provider, services = _resolve_provider_for_task('explanation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['explain_code'](code_to_explain)
    else:
        return _gemini_explain_code(code_to_explain)


def format_code_with_ai(code_to_format: str, language_hint: str = None) -> str:
    """Format code using user's preferred AI model."""
    provider, services = _resolve_provider_for_task('code_generation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['format_code_with_ai'](code_to_format, language_hint)
    else:
        return _gemini_format_code_with_ai(code_to_format, language_hint)


def suggest_tags_for_code(code_to_analyze):
    """Suggest tags for code using user's preferred model with hybrid approach."""
    provider, services = _resolve_provider_for_task('suggest_tags')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['suggest_tags_for_code'](code_to_analyze)
    else:
        return _gemini_suggest_tags_for_code(code_to_analyze)


def chat_answer(system_preamble: str, history_pairs: list, user_message: str) -> str:
    """Return chatbot answer using user's preferred model with hybrid approach."""
    provider, services = _resolve_provider_for_task('chat_answer')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['chat_answer'](system_preamble, history_pairs, user_message)
    else:
        return _gemini_chat_answer(system_preamble, history_pairs, user_message)


def refine_code_with_feedback(current_code: str, error_output: str, language_hint: str = None) -> str:
    """Refine code based on error output using user's preferred AI model."""
    provider, services = _resolve_provider_for_task('refine_code')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['refine_code_with_feedback'](current_code, error_output, language_hint)
    else:
        return _gemini_refine_code_with_feedback(current_code, error_output, language_hint)


def generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    """Generate embedding for text using user's preferred AI model."""
    # Embedding generation is not explicitly mentioned in the routing rules,
    # so we'll route it based on the general preferred model.
    # Given Minimax doesn't currently support embeddings, it will fall back to Gemini.
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'embedding_generation') # Generic task type
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['generate_embedding'](text_to_embed, task_type)
    else:
        return _gemini_generate_embedding(text_to_embed, task_type)


def generate_leetcode_solution(problem_title, problem_description, language):
    """Generate LeetCode solution using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'leetcode_solution_generation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['generate_leetcode_solution'](problem_title, problem_description, language)
    else:
        return _gemini_generate_leetcode_solution(problem_title, problem_description, language)


def explain_leetcode_solution(solution_code, problem_title, language):
    """Explain LeetCode solution using user's preferred AI model."""
    provider, services = _resolve_provider_for_task('leetcode_explanation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['explain_leetcode_solution'](solution_code, problem_title, language)
    else:
        return _gemini_explain_leetcode_solution(solution_code, problem_title, language)


def classify_leetcode_solution(solution_code, problem_description):
    """Classify LeetCode solution using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'leetcode_classification')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['classify_leetcode_solution'](solution_code, problem_description)
    else:
        return _gemini_classify_leetcode_solution(solution_code, problem_description)


def multi_step_layer1_architecture(prompt_text):
    """Layer 1: Problem Decomposition using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'multi_step_solver')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['multi_step_layer1_architecture'](prompt_text)
    else:
        return _gemini_multi_step_layer1_architecture(prompt_text)


def multi_step_layer2_coder(architecture_plan):
    """Layer 2: Code Generation using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'multi_step_solver')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['multi_step_layer2_coder'](architecture_plan)
    else:
        return _gemini_multi_step_layer2_coder(architecture_plan)


def multi_step_layer3_tester(code_block, test_cases=None):
    """Layer 3: Verification & Debugging using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'multi_step_solver')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['multi_step_layer3_tester'](code_block, test_cases)
    else:
        return _gemini_multi_step_layer3_tester(code_block, test_cases)


def multi_step_layer4_refiner(verified_code, complexity_analysis=None):
    """Layer 4: Optimization & Final Review using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'multi_step_solver')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['multi_step_layer4_refiner'](verified_code, complexity_analysis)
    else:
        return _gemini_multi_step_layer4_refiner(verified_code, complexity_analysis)


def multi_step_complete_solver(prompt_text, test_cases=None):
    """Complete Multi-Step Algorithmic Solver using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'multi_step_solver')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['multi_step_complete_solver'](prompt_text, test_cases)
    else:
        return _gemini_multi_step_complete_solver(prompt_text, test_cases)


def stream_code_generation(prompt_text, session_id=None):
    """Stream code generation using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'stream_code_generation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['stream_code_generation'](prompt_text, session_id)
    else:
        return _gemini_stream_code_generation(prompt_text, session_id)


def stream_code_explanation(code_content, session_id=None, original_prompt=None):
    """Stream code explanation using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'stream_code_explanation')
    _update_last_meta_provider(provider)
    
    if provider == 'minimax' and services:
        return services['stream_code_explanation'](code_content, session_id, original_prompt)
    else:
        return _gemini_stream_code_explanation(code_content, session_id, original_prompt)


def chained_streaming_generation(prompt_text, session_id=None, code_model=None, explanation_model=None):
    """Complete token-efficient chaining pipeline using user's preferred AI model."""
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'chained_streaming_generation')
    
    if provider == 'hybrid_minimax_gemini' and services:
        # For hybrid, we handle the orchestration here to use both providers
        def _hybrid_generator():
            # Minimax for code generation
            code_content = ""
            for chunk in services['minimax_code_gen_stream'](prompt_text, session_id):
                yield chunk
                if chunk["type"] == "code_complete":
                    code_content = chunk["content"]
                    break
                elif chunk["type"] == "error":
                    return # Stop on error
            
            if not code_content:
                yield {
                    "type": "error",
                    "error": "No code content generated by Minimax",
                    "status": "error"
                }
                return
            
            # Gemini for explanation
            for chunk in services['gemini_expl_stream'](code_content, session_id, prompt_text):
                yield chunk
        return _hybrid_generator()
        
    elif provider == 'minimax' and services:
        _update_last_meta_provider(provider)
        return services['chained_streaming_generation'](prompt_text, session_id, code_model, explanation_model)
    else:
        _update_last_meta_provider('gemini')
        return _gemini_chained_streaming_generation(prompt_text, session_id, code_model, explanation_model)


def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    # Cosine similarity is a utility, not directly tied to a model generation,
    # so we'll route it generally, but Minimax currently doesn't provide it,
    # so it will fall back to Gemini.
    # For future proofing, we add a placeholder 'embedding_utility' task type
    from flask_login import current_user
    provider, services = _resolve_provider_for_task(current_user, 'embedding_utility')
    
    if provider == 'minimax' and services:
        return services['cosine_similarity'](v1, v2)
    else:
        return _gemini_cosine_similarity(v1, v2)


def get_model_for_task(task_type, tier="primary"):
    """Get appropriate model for task with tiering support."""
    preferred_model = get_user_preferred_model()
    
    # If minimax-m2 is selected, use minimax for ALL tasks
    if preferred_model == 'minimax-m2' and MINIMAX_AVAILABLE:
        # Use MINIMAX_MODEL_TIERING_CONFIG from minimax_ai_services
        if MINIMAX_MODEL_TIERING_CONFIG and task_type in MINIMAX_MODEL_TIERING_CONFIG:
            return MINIMAX_MODEL_TIERING_CONFIG[task_type].get(tier, MINIMAX_MODEL_NAME)
        return MINIMAX_MODEL_NAME # Fallback to default minimax model
    else:
        # For Gemini models, use the user's specific choice directly
        return get_api_model_name(preferred_model)


# ============================================================================
# ORIGINAL GEMINI IMPLEMENTATION (renamed to avoid conflicts)
# ============================================================================

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
    # Check for prompt feedback (input blocking)
    if hasattr(response, 'prompt_feedback'):
        if hasattr(response.prompt_feedback, 'block_reason'):
            block_reason = response.prompt_feedback.block_reason
            if block_reason and block_reason != 0:  # 0 means BLOCK_REASON_UNSPECIFIED
                error_msg = f"Input blocked by API. Reason: {block_reason}"
                current_app.logger.error(f"Gemini API error ({operation_name}): {error_msg}")
                return False, f"Error: {error_msg}"
    
    # Check if we have valid candidates
    if not response.candidates:
        current_app.logger.error(f"Gemini API error ({operation_name}): No candidates in response. Full response: {response}")
        return False, "Error: The API returned no response candidates."
    
    candidate = response.candidates[0]
    
    # Check finish reason
    finish_reason = candidate.finish_reason
    
    # Handle different finish reasons
    if finish_reason == 1:  # STOP - normal completion
        if candidate.content.parts:
            return True, candidate.content.parts[0].text.strip()
        else:
            current_app.logger.error(f"Gemini API error ({operation_name}): STOP but no content parts. Response: {response}")
            return False, "Error: API completed but returned no content."
    
    elif finish_reason == 2:  # MAX_TOKENS
        if candidate.content.parts:
            # Still return partial content with warning
            content = candidate.content.parts[0].text.strip()
            current_app.logger.warning(f"Gemini API warning ({operation_name}): Response truncated due to MAX_TOKENS")
            return True, content + "\n\n[Note: Response may be incomplete due to length limits]"
        else:
            current_app.logger.error(f"Gemini API error ({operation_name}): MAX_TOKENS reached but no content")
            return False, "Error: Output exceeded maximum length and no content was generated."
    
    elif finish_reason == 3:  # SAFETY
        safety_ratings = candidate.safety_ratings
        safety_reasons = [f"{s.category.name}: {s.probability.name}" 
                         for s in safety_ratings if hasattr(s.probability, 'name') and s.probability.name != 'NEGLIGIBLE']
        if safety_reasons:
            reason_str = ', '.join(safety_reasons)
            current_app.logger.error(f"Gemini API error ({operation_name}): Content blocked - {reason_str}")
            return False, f"Error: Content blocked due to safety concerns: {reason_str}"
        else:
            return False, "Error: Content blocked due to safety concerns."
    
    elif finish_reason == 4:  # RECITATION
        current_app.logger.error(f"Gemini API error ({operation_name}): Content blocked due to recitation")
        return False, "Error: Content blocked due to recitation detection."
    
    elif finish_reason == 5:  # OTHER
        current_app.logger.error(f"Gemini API error ({operation_name}): Generation stopped for OTHER reason")
        return False, "Error: Generation stopped for unknown reason."
    
    else:  # Unknown or unspecified
        current_app.logger.error(f"Gemini API error ({operation_name}): Unknown finish_reason: {finish_reason}")
        if candidate.content.parts:
            return True, candidate.content.parts[0].text.strip()
        return False, "Error: Unexpected API response format."


def _get_api_key() -> str:
    api_key = current_app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return api_key


def _is_retryable_exception(e: Exception) -> bool:
    msg = str(e).lower()
    # treat common transient/server errors as retryable
    return any(code in msg for code in ["500", "502", "503", "504"]) or "timeout" in msg or "timed out" in msg or "rate" in msg or "temporarily" in msg


def _call_with_timeout(fn: Callable[[], any], timeout_seconds: int):
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn)
    try:
        return fut.result(timeout=timeout_seconds)
    except FuturesTimeout as te:
        # Attempt to cancel and return quickly
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
            # success; record if we had any retries before
            if attempt > 1:
                LAST_META['retries'] = True
                LAST_META['retry_attempts'] = attempt - 1
            return result
        except Exception as e:
            last_err = e
            if not _is_retryable_exception(e) or attempt == MAX_RETRIES:
                current_app.logger.error(f"Gemini API error ({operation_name}): {e}")
                raise
            # backoff with jitter
            delay = min(BACKOFF_MAX, (BACKOFF_BASE ** (attempt - 1)))
            jitter = random.uniform(0, 0.5)
            sleep_for = delay + jitter
            current_app.logger.warning(f"Transient error during {operation_name} (attempt {attempt}/{MAX_RETRIES}). Retrying in {sleep_for:.1f}s...")
            time.sleep(sleep_for)
    # Should not reach here
    raise last_err if last_err else RuntimeError(f"Unknown error during {operation_name}")


def _chunk_text_by_tokens(text: str, max_tokens: int) -> List[str]:
    """Chunk text by approximate token count with light overlap for context."""
    if not text:
        return [""]
    # Approx 1 token ~ 4 chars; keep a margin to avoid boundary issues
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
        start = end - overlap  # overlap for continuity
    return chunks


# Gemini-specific implementations (renamed functions)
def _gemini_generate_code_from_prompt(prompt_text):
    """Generate code from prompt using Gemini API."""
    # reset meta for this request
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Validate input size (revert to original high limit)
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
        # Update model name based on user preference
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
        # Use centralized response handler
        success, result = _handle_api_response(response, "code generation")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Gemini API error (generation): {e}")
        return f"Error: Could not generate code. {str(e)}"


def _gemini_explain_code(code_to_explain):
    """Generate explanation for code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Validate input size
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
        # Update model name based on user preference
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME, safety_settings=safety_settings)

        # Chunk very large inputs to avoid timeouts and server-side truncation
        chunks = _chunk_text_by_tokens(code_to_explain, DEFAULT_MAX_INPUT_TOKENS)
        if len(chunks) > 1:
            LAST_META['chunked'] = True
        combined_md = []
        for idx, chunk in enumerate(chunks, start=1):
            prompt = (
                "You are a senior code reviewer and educator. Analyze the code and produce a clear, structured explanation. "
                "Use Markdown with short sections and bullet points. Do NOT wrap the whole response in a single code block.\n\n"
                "Your explanation MUST include:\n"
                "1. Overview & Intent — what the code does and why.\n"
                "2. How It Works — the main steps/flow (not line-by-line unless necessary).\n"
                "3. Key Design Decisions — data structures, algorithms, and trade-offs.\n"
                "4. Complexity — Big-O time and space complexity for the critical path.\n"
                "5. Edge Cases & Correctness — inputs to watch for and why it remains correct.\n"
                "6. Improvements & Alternatives — performance, readability, or robustness ideas.\n"
                "7. Security/Performance Notes — only if applicable.\n\n"
                f"PART {idx}/{len(chunks)} — Code:\n"
                f"```\n{chunk}\n```"
            )
            def _do_call():
                return model.generate_content(prompt)
            response = _call_with_retries(_do_call, f"code explanation (part {idx})")
            success, result = _handle_api_response(response, "code explanation")
            combined_md.append(result)
        return "\n\n".join(combined_md)
        
    except Exception as e:
        current_app.logger.error(f"Gemini API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"


def _gemini_format_code_with_ai(code_to_format: str, language_hint: str = None) -> str:
    """Format code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        # Validate input size
        is_valid, error_msg = _validate_input_size(code_to_format, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
        if not is_valid:
            current_app.logger.error(f"Input validation failed: {error_msg}")
            return error_msg

        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.2,  # Lower temperature for consistent formatting
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
        # Update model name based on user preference
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        lang_line = f"Language: {language_hint}\n" if language_hint else ""
        prompt = (
            "You are a code formatting expert. Format the following code with proper indentation, spacing, and style. "
            "Add one-line comments where necessary to clarify complex logic. "
            "Preserve the original functionality and logic. "
            "Return ONLY the formatted code, no explanations, no markdown formatting, no code blocks.\n\n"
            f"{lang_line}CODE TO FORMAT:\n"
            f"```\n{code_to_format}\n```\n\n"
            "FORMATTED CODE:"
        )

        def _do_call():
            return model.generate_content(prompt)

        response = _call_with_retries(_do_call, "code formatting")
        success, result = _handle_api_response(response, "code formatting")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (formatting): {e}")
        return f"Error: Could not format code. {str(e)}"


def _gemini_suggest_tags_for_code(code_to_analyze):
    """Generate suggested tags for code using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Validate input size
        is_valid, error_msg = _validate_input_size(code_to_analyze, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
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
        model = genai.GenerativeModel(model_name=MODEL_NAME, safety_settings=safety_settings)

        # Chunk if needed; then merge and dedupe tags
        chunks = _chunk_text_by_tokens(code_to_analyze, DEFAULT_MAX_INPUT_TOKENS)
        if len(chunks) > 1:
            LAST_META['chunked'] = True
        all_tags: List[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            prompt = (
                "You are a code analysis expert. Analyze the following code and generate a "
                "comma-separated list of 3 to 5 relevant, lowercase tags. "
                "Prioritize: programming language, paradigm (oop, functional), frameworks/libs (flask, react), "
                "algorithmic techniques (two-pointers, dp, bfs, sorting), and data structures (heap, trie, hashmap). "
                "Do not include any explanation, markdown, or other text. "
                "Example output: python,flask,sqlalchemy,database\n\n"
                f"CODE (part {idx}/{len(chunks)}):\n"
                f"```\n{chunk}\n```"
            )
            def _do_call():
                return model.generate_content(prompt)
            response = _call_with_retries(_do_call, f"tag suggestion (part {idx})")
            success, result = _handle_api_response(response, "tag suggestion")
            # split, clean and collect
            parts = [t.strip().lower() for t in result.replace("\n", ",").split(",") if t.strip()]
            all_tags.extend(parts)
        # Deduplicate while preserving order and cap at 5
        seen = set()
        deduped = []
        for t in all_tags:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        return ",".join(deduped[:5])

    except Exception as e:
        current_app.logger.error(f"Gemini API error (tagging): {e}")
        return f"Error: Could not suggest tags. {str(e)}"


def _gemini_chat_answer(system_preamble: str, history_pairs: list, user_message: str) -> str:
    """Return a chatbot answer using Gemini API."""
    try:
        genai.configure(api_key=_get_api_key())
        full_msgs = []
        # system preface
        full_msgs.append({"role": "user", "parts": [system_preamble]})
        # history (truncate to last ~20 messages for token safety)
        MAX_H = 20
        for m in history_pairs[-MAX_H:]:
            role = m.get('role')
            content = m.get('content','')
            if role == 'assistant':
                full_msgs.append({"role": "model", "parts": [content]})
            else:
                full_msgs.append({"role": "user", "parts": [content]})
        # new user message
        full_msgs.append({"role": "user", "parts": [user_message]})

        model = genai.GenerativeModel(model_name=MODEL_NAME)
        def _do_call():
            return model.generate_content(full_msgs)
        resp = _call_with_retries(_do_call, "chat")
        ok, result = _handle_api_response(resp, "chat")
        return result
    except Exception as e:
        current_app.logger.error(f"Chat error: {e}")
        return f"Error: {e}"


def _gemini_refine_code_with_feedback(current_code: str, error_output: str, language_hint: str = None) -> str:
    """Refine code based on error output using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'

    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.3,
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
        # Update model name based on user preference
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        lang_line = f"Target Language: {language_hint}\n" if language_hint else ""
        prompt = (
            "You are a senior engineer. The user ran the generated code and got the following error/output. "
            "Diagnose the issue and provide a corrected version of the code. Preserve the original intent and public API where possible. "
            "If the error indicates missing imports or environment, include minimal fixes. "
            "Return ONLY the corrected code, no explanations, no markdown.\n\n"
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


def _gemini_generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    """Generate embedding for text using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        genai.configure(api_key=_get_api_key())
        def _do_call():
            return genai.embed_content(
                model="models/text-embedding-004",
                content=text_to_embed,
                task_type=task_type,
            )
        result = _call_with_retries(_do_call, "embedding")
        # Support both possible response shapes
        # - { 'embedding': {'values': [...] } }
        # - { 'embedding': [...] }
        if isinstance(result, dict) and 'embedding' in result:
            emb = result['embedding']
            if isinstance(emb, dict) and 'values' in emb:
                return emb['values']
            if isinstance(emb, list):
                return emb
        # Fallback: try attribute access
        if hasattr(result, 'embedding'):
            emb = getattr(result, 'embedding')
            if isinstance(emb, dict) and 'values' in emb:
                return emb['values']
            if isinstance(emb, list):
                return emb
        current_app.logger.error(f"Unexpected embedding response shape: {result}")
        return None
    except Exception as e:
        current_app.logger.error(f"Gemini API error (embedding): {e}")
        return None


def _gemini_generate_leetcode_solution(problem_title, problem_description, language):
    """Generate LeetCode solution using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Combine inputs for validation
        combined_input = f"Title: {problem_title}\nDescription: {problem_description}\nLanguage: {language}"
        is_valid, error_msg = _validate_input_size(combined_input, max_input_tokens=16000)
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
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        full_prompt = (
            f"You are an expert LeetCode solution generator. "
            f"Generate a complete, correct, and efficient solution in {language} for the following LeetCode problem. "
            f"Provide only the code, without any explanation, preamble, or markdown formatting. "
            f"Problem Title: {problem_title}\n"
            f"Problem Description: {problem_description}\n\n"
            f"SOLUTION ({language}):"
        )
        def _do_call():
            return model.generate_content(full_prompt)
        response = _call_with_retries(_do_call, "leetcode solution generation")

        # Use centralized response handler
        success, result = _handle_api_response(response, "leetcode solution generation")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (solution generation): {e}")
        return f"Error: Could not generate solution. {str(e)}"


def _gemini_explain_leetcode_solution(solution_code, problem_title, language):
    """Explain LeetCode solution using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Combine inputs for validation
        combined_input = f"Title: {problem_title}\nSolution: {solution_code}\nLanguage: {language}"
        is_valid, error_msg = _validate_input_size(combined_input, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
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
        model = genai.GenerativeModel(model_name=MODEL_NAME, safety_settings=safety_settings)
        prompt = (
            f"You are an expert at explaining LeetCode solutions. "
            f"Provide a concise but educative explanation for the following {language} solution to the problem '{problem_title}'. "
            f"Structure the answer with Markdown headings and cover:\n"
            f"1.  Overview & Intent — what the solution achieves and why this approach.\n"
            f"2.  Strategy & Key Ideas — the algorithm/pattern (e.g., Two Pointers, DP, BFS) and data structures used.\n"
            f"3.  Step-by-Step Walkthrough — the core flow; keep it brief and focused.\n"
            f"4.  Correctness Argument — why this works for all cases.\n"
            f"5.  Time Complexity — Big-O with a short justification.\n"
            f"6.  Space Complexity — Big-O with a short justification.\n"
            f"7.  Edge Cases & Pitfalls — tricky inputs and how the code handles them.\n"
            f"8.  Possible Improvements/Alternatives — if applicable.\n"
            f"Do not wrap the entire response in a single code block.\n\n"
            f"SOLUTION ({language}):\n"
            f"```\n{solution_code}\n```"
        )
        def _do_call():
            return model.generate_content(prompt)
        response = _call_with_retries(_do_call, "leetcode explanation")

        # Use centralized response handler
        success, result = _handle_api_response(response, "leetcode explanation")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (explanation): {e}")
        return f"Error: Could not generate explanation. {str(e)}"


def _gemini_classify_leetcode_solution(solution_code, problem_description):
    """Classify LeetCode solution using Gemini API."""
    global LAST_META
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    LAST_META['provider'] = 'gemini'
    
    try:
        # Combine inputs for validation
        combined_input = f"Description: {problem_description}\nSolution: {solution_code}"
        is_valid, error_msg = _validate_input_size(combined_input, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS)
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
        model = genai.GenerativeModel(model_name=MODEL_NAME, safety_settings=safety_settings)
        prompt = (
            "You are an expert in LeetCode problem classification. "
            "Analyze the following problem description and its solution. "
            "Generate a comma-separated list of 3 to 5 relevant classifications "
            "(e.g., 'Dynamic Programming', 'Two Pointers', 'BFS', 'Array', 'Hash Table'). "
            "Do not include any explanation, markdown, or other text. "
            "Example output: Dynamic Programming,Array,Hash Table\n\n"
            f"PROBLEM DESCRIPTION:\n{problem_description}\n\n"
            f"SOLUTION CODE:\n```\n{solution_code}\n```"
        )
        def _do_call():
            return model.generate_content(prompt)
        response = _call_with_retries(_do_call, "leetcode classification")

        # Use centralized response handler
        success, result = _handle_api_response(response, "leetcode classification")
        return result

    except Exception as e:
        current_app.logger.error(f"Gemini API error (classification): {e}")
        return f"Error: Could not classify solution. {str(e)}"


def _gemini_cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return np.dot(v1, v2) / (norm_v1 * norm_v2)


# Multi-Step Algorithmic Solver Architecture Functions for Gemini
def _gemini_multi_step_layer1_architecture(prompt_text):
    """Layer 1: Problem Decomposition & Strategy (Gemini implementation)."""
    try:
        genai.configure(api_key=_get_api_key())

        generation_config = {
            "temperature": 0.3,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 327680,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        # Update model name based on user preference
        update_global_model_name()
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        prompt = (
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
            "7. Risk Assessment & Potential Challenges\n\n"
            f"PROBLEM DESCRIPTION:\n{prompt_text}\n\n"
            "Provide a comprehensive architectural analysis and strategic plan."
        )
        
        def _do_call():
            return model.generate_content(prompt)
        
        response = _call_with_retries(_do_call, "multi-step layer 1 architecture")
        success, result = _handle_api_response(response, "multi-step layer 1 architecture")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Multi-step Layer 1 error: {e}")
        return f"Error: Could not generate architectural plan. {str(e)}"


def _gemini_multi_step_layer2_coder(architecture_plan):
    """Layer 2: Code Generation (Gemini implementation)."""
    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.2,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 655360,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        prompt = (
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
            "- Return ONLY the code, no explanations or markdown\n\n"
            f"ARCHITECTURE PLAN:\n{architecture_plan}\n\n"
            "GENERATE THE COMPLETE CODE:"
        )
        
        def _do_call():
            return model.generate_content(prompt)
        
        response = _call_with_retries(_do_call, "multi-step layer 2 coder")
        success, result = _handle_api_response(response, "multi-step layer 2 coder")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Multi-step Layer 2 error: {e}")
        return f"Error: Could not generate code. {str(e)}"


def _gemini_multi_step_layer3_tester(code_block, test_cases=None):
    """Layer 3: Verification & Debugging (Gemini implementation)."""
    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.3,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 491520,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        test_cases_section = f"\nADDITIONAL TEST CASES:\n{test_cases}" if test_cases else ""
        
        prompt = (
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
            "5. Document any bugs found and fixes applied\n\n"
            f"GENERATED CODE:\n```\n{code_block}\n```{test_cases_section}\n\n"
            "Provide your verification analysis and corrected code (if any fixes were needed)."
        )
        
        def _do_call():
            return model.generate_content(prompt)
        
        response = _call_with_retries(_do_call, "multi-step layer 3 tester")
        success, result = _handle_api_response(response, "multi-step layer 3 tester")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Multi-step Layer 3 error: {e}")
        return f"Error: Could not verify and debug code. {str(e)}"


def _gemini_multi_step_layer4_refiner(verified_code, complexity_analysis=None):
    """Layer 4: Optimization & Final Review (Gemini implementation)."""
    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.2,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 491520,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        complexity_section = f"\nCOMPLEXITY ANALYSIS:\n{complexity_analysis}" if complexity_analysis else ""
        
        prompt = (
            "You are The Refiner - Layer 4 of the Multi-Step Algorithmic Solver Architecture.\n\n"
            "Your goal is to analyze the time and space complexity and optimize the solution "
            "for efficiency (if possible). Provide the final optimized code and complexity summary.\n\n"
            "Tasks:\n"
            "1. Analyze current time and space complexity\n"
            "2. Identify potential optimizations\n"
            "3. Apply optimizations while maintaining correctness\n"
            "4. Provide final optimized code\n"
            "5. Give detailed complexity analysis (Big O notation)\n"
            "6. Explain optimization techniques used\n\n"
            f"VERIFIED CODE:\n```\n{verified_code}\n```{complexity_section}\n\n"
            "Provide the final optimized solution with comprehensive complexity analysis."
        )
        
        def _do_call():
            return model.generate_content(prompt)
        
        response = _call_with_retries(_do_call, "multi-step layer 4 refiner")
        success, result = _handle_api_response(response, "multi-step layer 4 refiner")
        return result
        
    except Exception as e:
        current_app.logger.error(f"Multi-step Layer 4 error: {e}")
        return f"Error: Could not optimize and finalize code. {str(e)}"


def _gemini_multi_step_complete_solver(prompt_text, test_cases=None):
    """Complete Multi-Step Algorithmic Solver (Gemini implementation)."""
    start_time = time.time()
    try:
        # Layer 1: Architecture
        layer1_result = _gemini_multi_step_layer1_architecture(prompt_text)
        if layer1_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer1_result, "layer": 1, "processing_time": processing_time}
        
        # Layer 2: Code Generation
        layer2_result = _gemini_multi_step_layer2_coder(layer1_result)
        if layer2_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer2_result, "layer": 2, "layer1": layer1_result, "processing_time": processing_time}
        
        # Layer 3: Testing & Debugging
        layer3_result = _gemini_multi_step_layer3_tester(layer2_result, test_cases)
        if layer3_result.startswith("Error:"):
            processing_time = time.time() - start_time
            return {"error": layer3_result, "layer": 3, "layer1": layer1_result, "layer2": layer2_result, "processing_time": processing_time}
        
        # Layer 4: Optimization & Final Review
        layer4_result = _gemini_multi_step_layer4_refiner(layer3_result)
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
        current_app.logger.error(f"Multi-step complete solver error: {e}")
        return {"error": f"Multi-step solver failed: {str(e)}", "processing_time": processing_time}


# Token-Efficient Streaming Pipeline Functions for Gemini
def _gemini_stream_code_generation(prompt_text, session_id=None):
    """Stream code generation using Gemini (token-efficient prompting)."""
    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.4,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 819200
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        # Token-efficient prompt - focused on code only
        optimized_prompt = (
            "Generate ONLY the algorithmic code solution for the following problem. "
            "Return only raw code without explanations, comments, or markdown formatting.\n\n"
            f"PROBLEM: {prompt_text}\n\n"
            "CODE:"
        )
        
        def _do_stream_call():
            return model.generate_content(optimized_prompt, stream=True)
        
        response = _call_with_retries(_do_stream_call, "streaming code generation")
        
        # Save session state if provided
        if session_id:
            from app.utils.state_manager import StreamingStateManager
            StreamingStateManager.save_session_start(session_id, "code_generation", prompt_text)
        
        accumulated_code = ""
        chunk_count = 0
        
        for chunk in response:
            if chunk.text:
                accumulated_code += chunk.text
                chunk_count += 1
                
                # Yield streaming chunk
                yield {
                    "type": "code_chunk",
                    "content": chunk.text,
                    "accumulated": accumulated_code,
                    "chunk_count": chunk_count,
                    "status": "streaming"
                }
                
                # Save intermediate state
                if session_id:
                    from app.utils.state_manager import StreamingStateManager
                    StreamingStateManager.save_intermediate_code(session_id, accumulated_code)
        
        # Final completion
        yield {
            "type": "code_complete",
            "content": accumulated_code,
            "total_chunks": chunk_count,
            "status": "completed",
            "token_savings": "Optimized prompt used - no explanation overhead"
        }
        
        # Save final state
        if session_id:
            from app.utils.state_manager import StreamingStateManager
            StreamingStateManager.save_final_code(session_id, accumulated_code)
            
    except Exception as e:
        # Safely log the error - check if we have an application context
        try:
            current_app.logger.error(f"Streaming code generation error: {e}")
        except RuntimeError:
            # Working outside of application context, use print instead
            print(f"Streaming code generation error: {e}")
        yield {
            "type": "error",
            "error": f"Could not generate code: {str(e)}",
            "status": "error"
        }


def _gemini_stream_code_explanation(code_content, session_id=None, original_prompt=None):
    """Stream code explanation generation (Gemini implementation)."""
    try:
        genai.configure(api_key=_get_api_key())
        generation_config = {
            "temperature": 0.3,
            "top_p": 1,
            "top_k": 32,
            "max_output_tokens": 409600
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)
        
        # Context-pruned prompt - only uses the code, not original problem description
        explanation_prompt = (
            "You are a senior code reviewer and educator. Analyze the following code and provide a comprehensive explanation.\n\n"
            "STRUCTURE YOUR RESPONSE AS:\n"
            "1. **Overview & Intent** — what the code does and why this approach\n"
            "2. **How It Works** — main steps/flow (not line-by-line unless necessary)\n"
            "3. **Key Design Decisions** — data structures, algorithms, trade-offs\n"
            "4. **Complexity Analysis** — Big-O time and space complexity\n"
            "5. **Edge Cases & Correctness** — inputs to watch for and why it remains correct\n"
            "6. **Improvements & Alternatives** — performance, readability, robustness ideas\n"
            "7. **Security/Performance Notes** — only if applicable\n\n"
            "CODE TO EXPLAIN:\n"
            f"```\n{code_content}\n```\n\n"
            "Provide a clear, structured explanation:"
        )
        
        def _do_stream_call():
            return model.generate_content(explanation_prompt, stream=True)
        
        response = _call_with_retries(_do_stream_call, "streaming explanation generation")
        
        accumulated_explanation = ""
        chunk_count = 0
        
        for chunk in response:
            if chunk.text:
                accumulated_explanation += chunk.text
                chunk_count += 1
                
                # Yield streaming chunk
                yield {
                    "type": "explanation_chunk",
                    "content": chunk.text,
                    "accumulated": accumulated_explanation,
                    "chunk_count": chunk_count,
                    "status": "streaming"
                }
        
        # Final completion
        yield {
            "type": "explanation_complete",
            "content": accumulated_explanation,
            "total_chunks": chunk_count,
            "status": "completed",
            "context_optimization": "Context pruned - only code used as input, original problem excluded"
        }
        
    except Exception as e:
        print(f"Streaming explanation generation error: {e}")
        yield {
            "type": "error",
            "error": f"Could not generate explanation: {str(e)}",
            "status": "error"
        }


def _gemini_chained_streaming_generation(prompt_text, session_id=None, code_model=None, explanation_model=None):
    """Complete token-efficient chaining pipeline (Gemini implementation)."""
    try:
        # Step 1: Generate code with streaming
        yield {
            "type": "pipeline_start",
            "step": 1,
            "total_steps": 2,
            "status": "starting_code_generation"
        }
        
        code_content = ""
        code_chunks = 0
        
        for code_chunk in _gemini_stream_code_generation(prompt_text, session_id):
            if code_chunk["type"] == "code_chunk":
                code_content = code_chunk["accumulated"]
                code_chunks = code_chunk["chunk_count"]
                yield {
                    "type": "code_progress",
                    "step": 1,
                    "content": code_chunk["content"],
                    "accumulated": code_content,
                    "progress": f"Code chunks: {code_chunks}",
                    "status": "generating"
                }
            elif code_chunk["type"] == "code_complete":
                code_content = code_chunk["content"]
                yield {
                    "type": "step_complete",
                    "step": 1,
                    "total_chunks": code_chunks,
                    "content": code_content,
                    "status": "completed",
                    "next_step": "generating_explanation"
                }
                break
            elif code_chunk["type"] == "error":
                yield code_chunk
                return
        
        if not code_content:
            yield {
                "type": "error",
                "error": "No code content generated",
                "status": "error"
            }
            return
        
        # Step 2: Generate explanation with streaming (context pruning applied)
        yield {
            "type": "pipeline_progress",
            "step": 2,
            "total_steps": 2,
            "status": "starting_explanation_generation"
        }
        
        explanation_content = ""
        explanation_chunks = 0
        
        for explanation_chunk in _gemini_stream_code_explanation(code_content, session_id, prompt_text):
            if explanation_chunk["type"] == "explanation_chunk":
                explanation_content = explanation_chunk["accumulated"]
                explanation_chunks = explanation_chunk["chunk_count"]
                yield {
                    "type": "explanation_progress",
                    "step": 2,
                    "content": explanation_chunk["content"],
                    "accumulated": explanation_content,
                    "progress": f"Explanation chunks: {explanation_chunks}",
                    "status": "generating"
                }
            elif explanation_chunk["type"] == "explanation_complete":
                explanation_content = explanation_chunk["content"]
                yield {
                    "type": "pipeline_complete",
                    "step": 2,
                    "total_chunks": explanation_chunks,
                    "code": code_content,
                    "explanation": explanation_content,
                    "status": "completed",
                    "optimizations": {
                        "token_efficient": True,
                        "context_pruned": True,
                        "streaming_enabled": True,
                        "code_chunks": code_chunks,
                        "explanation_chunks": explanation_chunks
                    }
                }
                break
            elif explanation_chunk["type"] == "error":
                yield explanation_chunk
                return
        
    except Exception as e:
        # Safely log the error - check if we have an application context
        try:
            current_app.logger.error(f"Chained streaming generation error: {e}")
        except RuntimeError:
            # Working outside of application context, use print instead
            print(f"Chained streaming generation error: {e}")
        yield {
            "type": "error",
            "error": f"Pipeline failed: {str(e)}",
            "status": "error"
        }


def _gemini_get_model_for_task(task_type, tier="primary"):
    """Get appropriate model for task with tiering support (Gemini implementation)."""
    MODEL_TIERING_CONFIG = {
        "code_generation": {
            "primary": "gemini-2.5-flash",  # High reasoning for code
            "fallback": "gemini-1.5-flash",  # Faster fallback
            "cost_optimized": "gemini-1.5-flash"
        },
        "explanation": {
            "primary": "gemini-1.5-flash",  # Faster, cheaper for explanations
            "fallback": "gemini-1.5-flash",
            "cost_optimized": "gemini-1.5-flash"
        }
    }
    return MODEL_TIERING_CONFIG.get(task_type, {}).get(tier, MODEL_NAME)

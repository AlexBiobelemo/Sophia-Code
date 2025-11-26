"""Handles all interactions with the external Google Gemini API."""

import google.generativeai as genai
from flask import current_app
import numpy as np
import time
import random
from typing import Callable, Tuple, Optional, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout


MODEL_NAME = "gemini-2.5-flash"
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
}


def _count_tokens_estimate(text):
    """
    Provides a rough estimate of token count for input validation.
    
    Args:
        text (str): The text to estimate tokens for.
    
    Returns:
        int: Estimated token count (roughly 1 token per 4 characters).
    """
    return len(text) // 4


def _validate_input_size(text, max_input_tokens=DEFAULT_MAX_INPUT_TOKENS):
    """
    Validates that input text doesn't exceed reasonable token limits.
    
    Args:
        text (str): The text to validate.
        max_input_tokens (int): Maximum allowed input tokens.
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    estimated_tokens = _count_tokens_estimate(text)
    if estimated_tokens > max_input_tokens:
        return False, f"Input too large ({estimated_tokens} estimated tokens, max {max_input_tokens}). Please reduce input size."
    return True, None


def _handle_api_response(response, operation_name):
    """
    Centralized response handling for Gemini API calls.
    
    Args:
        response: The Gemini API response object.
        operation_name (str): Name of the operation for logging.
    
    Returns:
        tuple: (success: bool, result: str)
    """
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



def generate_code_from_prompt(prompt_text):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates code from a text prompt using the Gemini API.

    Args:
        prompt_text (str): The user's natural language prompt.

    Returns:
        str: The generated code block as a string, or an error message.
    """
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

def explain_code(code_to_explain):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates an explanation for a block of code using the Gemini API.

    Args:
        code_to_explain (str): The block of code to be explained.

    Returns:
        str: The AI-generated explanation in Markdown format, or an error message.
    """
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

def format_code_with_ai(code_to_format: str, language_hint: str = None) -> str:
    """
    Formats code using the Gemini API.

    Args:
        code_to_format (str): The code to be formatted.
        language_hint (str): Optional hint for the language (e.g., 'python', 'javascript').

    Returns:
        str: The formatted code, or an error message starting with 'Error:'.
    """
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False

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


def suggest_tags_for_code(code_to_analyze):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates suggested tags for a block of code using the Gemini API.

    Args:
        code_to_analyze (str): The block of code to be analyzed.

    Returns:
        str: A comma-separated string of tags, or an error message.
    """
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

def chat_answer(system_preamble: str, history_pairs: list, user_message: str) -> str:
    """Return a chatbot answer constrained to the app purpose.

    Args:
        system_preamble (str): The preprompt / instructions.
        history_pairs (list): list of {"role": "user"|"assistant", "content": str}
        user_message (str): latest user question
    Returns:
        str: assistant reply text
    """
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


def refine_code_with_feedback(current_code: str, error_output: str, language_hint: str = None) -> str:
    """
    Refines/regenerates code based on runtime error output.

    Args:
        current_code: The current code that produced an error.
        error_output: The error/stack trace or failing test output.
        language_hint: Optional hint for the language (e.g., 'python').

    Returns:
        str: The revised code. Returns an error string starting with 'Error:' on failure.
    """
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False

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


def generate_embedding(text_to_embed, task_type="RETRIEVAL_DOCUMENT"):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates a vector embedding for a block of text using the Gemini API.

    Args:
        text_to_embed (str): The text to create an embedding for.
        task_type (str): The type of task ('RETRIEVAL_DOCUMENT' for storing,
                         'RETRIEVAL_QUERY' for searching).

    Returns:
        list: A list of floats representing the vector embedding, or None on error.
    """
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


def generate_leetcode_solution(problem_title, problem_description, language):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates a LeetCode solution using the Gemini API.

    Args:
        problem_title (str): The title of the LeetCode problem.
        problem_description (str): The description of the problem.
        language (str): The programming language for the solution.

    Returns:
        str: The generated code solution, or an error message.
    """
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

def explain_leetcode_solution(solution_code, problem_title, language):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates an explanation for a LeetCode solution using the Gemini API.

    Args:
        solution_code (str): The code of the solution to explain.
        problem_title (str): The title of the LeetCode problem.
        language (str): The programming language of the solution.

    Returns:
        str: The AI-generated explanation, or an error message.
    """
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

def classify_leetcode_solution(solution_code, problem_description):
    # reset meta for this request
    LAST_META['retries'] = False
    LAST_META['retry_attempts'] = 0
    LAST_META['chunked'] = False
    """
    Generates classification tags for a LeetCode solution using the Gemini API.

    Args:
        solution_code (str): The code of the solution.
        problem_description (str): The description of the LeetCode problem.

    Returns:
        str: A comma-separated string of classification tags, or an error message.
    """
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


def cosine_similarity(v1, v2):
    """
    Calculates the cosine similarity between two vectors.

    Args:
        v1 (np.array): The first vector.
        v2 (np.array): The second vector.

    Returns:
        float: The cosine similarity between v1 and v2, or 0.0 if a norm is zero.
    """
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return np.dot(v1, v2) / (norm_v1 * norm_v2)

"""Defines the routes and view functions for the Sophia application."""

import numpy as np
import sqlalchemy as sa
from sqlalchemy import or_
from flask import (Blueprint, render_template, flash, redirect, url_for,
                   request, current_app, jsonify)
from flask_login import current_user, login_user, logout_user, login_required
import time, uuid
from datetime import datetime, timedelta, timezone
import json

from app import db, ai_services
from app.forms import (RegistrationForm, LoginForm, SnippetForm,
                       AIGenerationForm, CollectionForm, NoteForm,
                       LeetcodeProblemForm, GenerateSolutionForm, ApproveSolutionForm,
                       MoveSnippetForm, EditProfileForm, BulkActionForm, SettingsForm)
from app.models import User, Snippet, Collection, LeetcodeProblem, LeetcodeSolution, SnippetVersion, ChatSession, ChatMessage, Badge, UserBadge, Point, Note, MultiStepResult
from app.utils.state_manager import StateManager, preserve_form_state, restore_form_state, preserve_search_state, restore_search_state
from io import StringIO

# Create the main Blueprint
bp = Blueprint('main', __name__)

def check_and_award_badges(user):
    """Checks user activity and awards badges if criteria are met."""
    # Badge: First Snippet
    if user.snippets.count() >= 1:
        user.award_badge("First Snippet")

    # Badge: Snippet Enthusiast (e.g., 10 snippets, 100 snippets, 250 snippets, 500 snippets)
    if user.snippets.count() >= 500:
        user.award_badge("Snippet Master")
    elif user.snippets.count() >= 250:
        user.award_badge("Snippet Virtuoso")
    elif user.snippets.count() >= 100:
        user.award_badge("Snippet Grandmaster")
    elif user.snippets.count() >= 10:
        user.award_badge("Snippet Enthusiast")

    # Badge: Collection Creator (e.g., 1 collection)
    if user.collections.count() >= 1:
        user.award_badge("Collection Creator")

    # Badge: Leetcode Contributor (e.g., 1 problem or solution)
    if user.leetcode_problems.count() >= 1 or user.leetcode_solutions.count() >= 1:
        user.award_badge("Leetcode Contributor")

    # Badge: Point Accumulator (e.g., 50 points)
    if user.get_total_points() >= 50:
        user.award_badge("Point Accumulator")

    db.session.commit() # Commit any badge awards


@bp.route('/')
@bp.route('/index')
def index():
    """Renders the homepage with unified controls (language, tags, sort, text) and server-side pagination.
    If partial=1 is provided, returns only the snippet cards fragment for infinite scroll.
    """
    page = request.args.get('page', 1, type=int)
    language = request.args.get('language') or ''
    tag = request.args.get('tag') or ''
    sort = request.args.get('sort') or 'date_desc'  # one of: alpha, date_asc, date_desc
    text = request.args.get('q') or ''             # contains-text filter
    partial = request.args.get('partial') == '1'

    pagination = None
    languages = []
    bulk_action_form = None # Initialize outside if block

    if current_user.is_authenticated:
        bulk_action_form = BulkActionForm() # Instantiate form
        
        # Preserve search state
        preserve_search_state({
            'language': language,
            'tag': tag,
            'sort': sort,
            'q': text,
            'page': page
        })
        
        # Base query scoped to current user
        q = current_user.snippets

        if language:
            q = q.filter(Snippet.language == language)
        if tag:
            # CSV tags: simple substring match (case-insensitive)
            q = q.filter(Snippet.tags.ilike(f'%{tag}%'))
        if text:
            ilike = f"%{text}%"
            q = q.filter(or_(
                Snippet.title.ilike(ilike),
                Snippet.description.ilike(ilike),
                Snippet.code.ilike(ilike),
                Snippet.tags.ilike(ilike),
            ))

        # Sorting
        if sort == 'alpha':
            q = q.order_by(Snippet.title.asc())
        elif sort == 'date_asc':
            q = q.order_by(Snippet.timestamp.asc())
        else:  # default newest first
            q = q.order_by(Snippet.timestamp.desc())

        # Paginate (server-side) — scalable to large datasets
        pagination = q.paginate(
            page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)

        # Distinct languages for dropdown (cheap and bounded)
        languages = [row[0] for row in (
            current_user.snippets.with_entities(Snippet.language)
            .distinct().order_by(Snippet.language.asc()).all()
        ) if row[0]]

    if partial:
        # Return just the cards for infinite scrolling
        return render_template('_snippets_list.html', snippets=(pagination.items if pagination else []))

    return render_template(
        'index.html',
        title='Home',
        snippets=pagination,
        languages=languages,
        selected_language=language,
        selected_tag=tag,
        selected_sort=sort,
        text_query=text,
        form=bulk_action_form
    )


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with rate limiting and account lockout."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data)
        )

        LOGIN_ATTEMPTS_LIMIT = current_app.config.get('LOGIN_ATTEMPTS_LIMIT', 5)
        LOGIN_LOCKOUT_PERIOD_MINUTES = current_app.config.get('LOGIN_LOCKOUT_PERIOD_MINUTES', 30)

        now = datetime.now(timezone.utc)

        if user:
            # Check for lockout
            if user.locked_until and user.locked_until > now:
                remaining_time = user.locked_until - now
                flash(f'Account locked. Please try again in {int(remaining_time.total_seconds() / 60)} minutes.', 'danger')
                return redirect(url_for('main.login'))

            if user.check_password(form.password.data):
                # Successful login: reset failed attempts
                user.failed_login_attempts = 0
                user.last_failed_login = None
                user.locked_until = None
                db.session.commit()
                login_user(user, remember=form.remember_me.data)
                return redirect(url_for('main.index'))
            else:
                # Failed login: increment attempts
                user.failed_login_attempts = user.failed_login_attempts + 1
                user.last_failed_login = now

                if user.failed_login_attempts >= LOGIN_ATTEMPTS_LIMIT:
                    user.locked_until = now + timedelta(minutes=LOGIN_LOCKOUT_PERIOD_MINUTES)
                    flash(f'Too many failed login attempts. Your account has been locked for {LOGIN_LOCKOUT_PERIOD_MINUTES} minutes.', 'danger')
                else:
                    flash('Invalid username or password', 'danger')
                db.session.commit()
                return redirect(url_for('main.login'))
        else:
            # User not found (to prevent enumeration attacks, respond generically)
            flash('Invalid username or password', 'danger')
            return redirect(url_for('main.login'))
    return render_template('login.html', title='Sign In', form=form)


@bp.route('/logout')
def logout():
    """Handles user logout."""
    logout_user()
    return redirect(url_for('main.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)


@bp.route('/notes')
@login_required
def notes():
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q') or ''
    
    # Preserve search state
    preserve_search_state({'q': q, 'page': page})
    
    user_notes = current_user.notes
    if q:
        user_notes = user_notes.filter(Note.title.ilike(f'%{q}%') | Note.content.ilike(f'%{q}%'))
    user_notes = user_notes.order_by(Note.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False
    )
    return render_template('notes.html', title='My Notes', notes=user_notes, query=q)



@bp.route('/create_note', methods=['GET', 'POST'])
@login_required
def create_note():
    """Handles creation of new notes."""
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(
            title=form.title.data,
            content=form.content.data,
            author=current_user
        )
        db.session.add(note)
        db.session.commit()
        
        # Award points for creating a note
        current_app.award_points(current_user, 5, "Note Created")
        
        # Check badges
        check_and_award_badges(current_user)
            
        flash('Your note has been saved!', 'success')
        return redirect(url_for('main.notes'))
    return render_template('create_note.html', title='Create Note', form=form)


@bp.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    """Displays a single note in detail."""
    note = db.session.get(Note, note_id)
    if note is None or note.author != current_user:
        flash('Note not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('main.notes'))
    return render_template('view_note.html', title=note.title, note=note)


@bp.route('/note/<int:note_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    """Handles editing an existing note."""
    note = db.session.get(Note, note_id)
    if note is None or note.author != current_user:
        flash('Note not found or you do not have permission to edit it.', 'danger')
        return redirect(url_for('main.notes'))

    form = NoteForm(obj=note)
    
    # Restore form data if available
    if request.method == 'GET':
        saved_data = restore_form_state(f'edit_note_{note_id}')
        if saved_data:
            form.title.data = saved_data.get('title', note.title)
            form.content.data = saved_data.get('content', note.content)
    
    if form.validate_on_submit():
        note.title = form.title.data
        note.content = form.content.data
        db.session.commit()
        # Clear saved form state after successful submission
        StateManager.clear_state('form_data', f'edit_note_{note_id}')
        flash('Your note has been updated!', 'success')
        return redirect(url_for('main.view_note', note_id=note.id))
    
    # Preserve form data on POST with validation errors
    if request.method == 'POST' and not form.validate_on_submit():
        preserve_form_state({
            'title': form.title.data,
            'content': form.content.data
        }, f'edit_note_{note_id}')
    
    return render_template('edit_note.html', title='Edit Note', form=form, note=note)


@bp.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    """Handles deleting a note."""
    note = db.session.get(Note, note_id)
    if note is None or note.author != current_user:
        flash('Note not found or you do not have permission to delete it.', 'danger')
        return redirect(url_for('main.notes'))

    db.session.delete(note)
    db.session.commit()
    flash('Your note has been deleted.', 'success')
    return redirect(url_for('main.notes'))


@bp.route('/api/note/<int:note_id>/explain', methods=['POST'])
@login_required
def api_explain_note(note_id):
    """API endpoint to get an AI explanation for a note's content."""
    note = db.session.get(Note, note_id)
    if note is None or note.author != current_user:
        return jsonify({'error': 'Note not found or unauthorized.'}), 404

    try:
        explanation = ai_services.explain_code(note.content)
        return jsonify({'explanation': explanation})
    except Exception as e:
        current_app.logger.error(f"AI explanation for note {note_id} failed: {e}")
        return jsonify({'error': 'Failed to generate explanation.'}), 500


@bp.route('/snippet/<int:snippet_id>')
@login_required
def view_snippet(snippet_id):
    """Displays a single code snippet in detail and computes prev/next for fast navigation."""
    snippet = db.session.get(Snippet, snippet_id)
    # Security check: ensure snippet exists and belongs to the current user
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('main.index'))

    # Determine previous/next snippet for navigation (ordered by most recent first)
    prev_snippet = db.session.scalar(
        sa.select(Snippet)
          .where(Snippet.user_id == current_user.id, Snippet.timestamp > snippet.timestamp)
          .order_by(Snippet.timestamp.asc())
    )
    next_snippet = db.session.scalar(
        sa.select(Snippet)
          .where(Snippet.user_id == current_user.id, Snippet.timestamp < snippet.timestamp)
          .order_by(Snippet.timestamp.desc())
    )

    return render_template(
        'view_snippet.html',
        title=snippet.title,
        snippet=snippet,
        prev_snippet_id=prev_snippet.id if prev_snippet else None,
        next_snippet_id=next_snippet.id if next_snippet else None,
    )


@bp.route('/create_snippet', methods=['GET', 'POST'])
@login_required
def create_snippet():
    """Handles creation of new snippets."""
    form = SnippetForm()
    # Populate the collection dropdown with the user's collections
    form.collection.choices = [(c.id, c.name) for c in current_user.collections.all()]
    form.collection.choices.insert(0, (0, '--- No Collection ---'))

    if request.method == 'GET':
        # If code was generated by AI, pre-populate the form
        generated_code = request.args.get('generated_code')
        generated_explanation = request.args.get('generated_explanation')
        if generated_code:
            form.code.data = generated_code
        if generated_explanation:
            form.description.data = generated_explanation

    if form.validate_on_submit():
        collection_id = form.collection.data if form.collection.data != 0 else None
        snippet = Snippet(
            title=form.title.data,
            description=form.description.data,
            code=form.code.data,
            author=current_user,
            tags=form.tags.data,
            language=form.language.data,
            collection_id=collection_id
        )
        # Handle thinking_steps if provided from multi-step generation
        thinking_steps = request.args.get('thinking_steps')
        if thinking_steps:
            try:
                import json
                snippet.thought_steps = json.loads(thinking_steps)
            except (json.JSONDecodeError, TypeError):
                # If invalid JSON, store as None or empty dict
                snippet.thought_steps = None
        try:
            snippet.generate_and_set_embedding()
        except Exception as e:
            current_app.logger.warning(f"embedding generation failed (create_snippet): {e}")
        db.session.add(snippet)
        db.session.commit()
        # Save initial version snapshot
        version = SnippetVersion(
            snippet_id=snippet.id,
            title=snippet.title,
            description=snippet.description,
            code=snippet.code,
            language=snippet.language,
            tags=snippet.tags,
        )
        db.session.add(version)
        db.session.commit()
        current_app.award_points(current_user, 10, "Snippet Created") # Award points for creating a snippet
        check_and_award_badges(current_user) # Check and award badges
        
        # Trigger backup after snippet creation
        try:
            from database_backup import increment_snippet_save_counter
            increment_snippet_save_counter()
        except Exception as e:
            current_app.logger.warning(f"Backup trigger failed (create_snippet): {e}")
            
        flash('Your snippet has been saved!', 'success')
        return redirect(url_for('main.index'))

    return render_template('create_snippet.html', title='Create Snippet', form=form)


@bp.route('/snippet/<int:snippet_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_snippet(snippet_id):
    """Handles editing an existing snippet."""
    snippet = db.session.get(Snippet, snippet_id)
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to edit it.', 'danger')
        return redirect(url_for('main.index'))

    form = SnippetForm(obj=snippet)
    form.collection.choices = [(c.id, c.name) for c in current_user.collections.all()]
    form.collection.choices.insert(0, (0, '--- No Collection ---'))

    if form.validate_on_submit():
        collection_id = form.collection.data if form.collection.data != 0 else None
        # Persist a version of the current state before changing
        version = SnippetVersion(
            snippet_id=snippet.id,
            title=snippet.title,
            description=snippet.description,
            code=snippet.code,
            language=snippet.language,
            tags=snippet.tags,
        )
        db.session.add(version)

        snippet.title = form.title.data
        snippet.description = form.description.data
        snippet.code = form.code.data
        snippet.tags = form.tags.data
        snippet.language = form.language.data
        snippet.collection_id = collection_id
        try:
            snippet.generate_and_set_embedding()
        except Exception as e:
            current_app.logger.warning(f"embedding generation failed (edit_snippet): {e}")
        db.session.commit()
        
        # Trigger backup after snippet editing
        try:
            from database_backup import increment_snippet_save_counter
            increment_snippet_save_counter()
        except Exception as e:
            current_app.logger.warning(f"Backup trigger failed (edit_snippet): {e}")
            
        flash('Your snippet has been updated!', 'success')
        return redirect(url_for('main.view_snippet', snippet_id=snippet.id))

    elif request.method == 'GET':
        # Pre-select the correct collection in the dropdown
        form.collection.data = snippet.collection_id or 0

    return render_template('edit_snippet.html', title='Edit Snippet', form=form, snippet=snippet)


@bp.route('/snippet/<int:snippet_id>/history')
@login_required
def snippet_history(snippet_id):
    """Displays a snippet's version history."""
    snippet = db.session.get(Snippet, snippet_id)
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to view it.', 'danger')
        return redirect(url_for('main.index'))
    versions = snippet.versions.order_by(SnippetVersion.created_at.desc()).all()
    return render_template('snippet_history.html', title=f"History: {snippet.title}", snippet=snippet, versions=versions)


@bp.route('/snippet/<int:snippet_id>/revert', methods=['POST'])
@login_required
def revert_snippet(snippet_id, version_id):
    """Reverts a snippet to a previous version."""
    snippet = db.session.get(Snippet, snippet_id)
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to modify it.', 'danger')
        return redirect(url_for('main.index'))
    version = db.session.get(SnippetVersion, version_id)
    if version is None or version.snippet_id != snippet.id:
        flash('Version not found.', 'danger')
        return redirect(url_for('main.snippet_history', snippet_id=snippet.id))
    # Save current state as a new version before reverting
    db.session.add(SnippetVersion(
        snippet_id=snippet.id,
        title=snippet.title,
        description=snippet.description,
        code=snippet.code,
        language=snippet.language,
        tags=snippet.tags,
    ))
    # Revert fields
    snippet.title = version.title
    snippet.description = version.description
    snippet.code = version.code
    snippet.language = version.language
    snippet.tags = version.tags
    try:
        snippet.generate_and_set_embedding()
    except Exception as e:
        current_app.logger.warning(f"embedding generation failed (revert_snippet): {e}")
    db.session.commit()
    flash('Snippet reverted to selected version.', 'success')
    return redirect(url_for('main.view_snippet', snippet_id=snippet.id))


@bp.route('/snippet/<int:snippet_id>/delete', methods=['POST'])
@login_required
def delete_snippet(snippet_id):
    """Handles deleting a snippet and redirects to the appropriate next snippet or index."""
    snippet = db.session.get(Snippet, snippet_id)
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to delete it.', 'danger')
        return redirect(url_for('main.index'))

    # Determine previous/next snippet for navigation before deletion
    # 'Previous' means an earlier (older timestamp) snippet in the descending list
    prev_snippet = db.session.scalar(
        sa.select(Snippet)
          .where(Snippet.user_id == current_user.id, Snippet.timestamp > snippet.timestamp)
          .order_by(Snippet.timestamp.asc())
    )
    # 'Next' means a later (newer timestamp) snippet in the descending list
    next_snippet = db.session.scalar(
        sa.select(Snippet)
          .where(Snippet.user_id == current_user.id, Snippet.timestamp < snippet.timestamp)
          .order_by(Snippet.timestamp.desc())
    )

    db.session.delete(snippet)
    db.session.commit()
    flash('Your snippet has been deleted.', 'success')

    # Redirect logic
    if prev_snippet:
        return redirect(url_for('main.view_snippet', snippet_id=prev_snippet.id))
    elif next_snippet:
        return redirect(url_for('main.view_snippet', snippet_id=next_snippet.id))
    else:
        return redirect(url_for('main.index'))


@bp.route('/generate', methods=['GET', 'POST'])
@login_required
def generate():
    """Renders the AI code generation page and handles form submission."""
    form = AIGenerationForm()
    
    # Pre-fill prompt if provided via URL parameter (for retry functionality)
    if request.method == 'GET':
        prompt_param = request.args.get('prompt')
        if prompt_param:
            form.prompt.data = prompt_param
    
    if form.validate_on_submit():
        prompt = form.prompt.data
        flash('Generating your code... please wait.', 'info')
        generated_code = ai_services.generate_code_from_prompt(prompt)
        gen_meta = getattr(ai_services, 'LAST_META', {}) or {}

        if "Error:" in generated_code:
            flash(generated_code, 'danger')
            return redirect(url_for('main.generate'))

        generated_explanation = ai_services.explain_code(generated_code)
        expl_meta = getattr(ai_services, 'LAST_META', {}) or {}

        # Small banners for retries/chunking
        if gen_meta.get('retries'):
            attempts = gen_meta.get('retry_attempts', 0)
            flash(f"Notice: The AI request was retried {attempts} time(s) due to transient errors.", 'warning')
        if expl_meta.get('retries'):
            attempts = expl_meta.get('retry_attempts', 0)
            flash(f"Notice: The explanation step was retried {attempts} time(s).", 'warning')
        if expl_meta.get('chunked'):
            flash('Large input was processed in multiple parts; the explanation shown is combined.', 'info')

        # Redirect to create page with code and explanation pre-filled
        return redirect(url_for('main.create_snippet', generated_code=generated_code, generated_explanation=generated_explanation))

    return render_template('generate.html', title='AI Code Generation', form=form)


@bp.route('/generate_multi_step', methods=['POST'])
@login_required
def generate_multi_step():
    """Handle multi-step thinking AI code generation."""
    try:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt', '').strip()
        test_cases = data.get('test_cases', '').strip()
        
        if not prompt:
            return jsonify({'error': 'Prompt is required.'}), 400
            
        # Generate unique result ID
        result_id = str(uuid.uuid4())
        
        # Create database record for multi-step result
        multi_step_record = MultiStepResult(
            result_id=result_id,
            user_id=current_user.id,
            prompt=prompt,
            test_cases=test_cases,
            status='processing'
        )
        db.session.add(multi_step_record)
        db.session.commit()
        
        # Call the multi-step solver
        result = ai_services.multi_step_complete_solver(prompt, test_cases)
        
        # Update the database record with results
        if 'error' in result:
            multi_step_record.status = 'error'
            multi_step_record.error_message = result['error']
            multi_step_record.completed_at = datetime.now(timezone.utc)
        else:
            multi_step_record.status = 'completed'
            multi_step_record.layer1_architecture = result.get('layer1_architecture')
            multi_step_record.layer2_coder = result.get('layer2_coder')
            multi_step_record.layer3_tester = result.get('layer3_tester')
            multi_step_record.layer4_refiner = result.get('layer4_refiner')
            multi_step_record.final_code = result.get('final_code')
            
            # Ensure processing_time is always a valid float
            processing_time = result.get('processing_time')
            if processing_time is not None and isinstance(processing_time, (int, float)):
                multi_step_record.processing_time = float(processing_time)
            else:
                multi_step_record.processing_time = None
                
            multi_step_record.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'result_id': result_id,
            'message': 'Multi-step thinking completed successfully!'
        })
        
    except Exception as e:
        current_app.logger.error(f"Multi-step generation failed: {e}")
        return jsonify({'error': f'Multi-step generation failed: {str(e)}'}), 500


@bp.route('/get_multi_step_result/<result_id>')
@login_required
def get_multi_step_result(result_id):
    """Retrieve multi-step thinking results."""
    try:
        # Query database for multi-step result
        result_record = db.session.scalar(
            sa.select(MultiStepResult).where(
                MultiStepResult.result_id == result_id,
                MultiStepResult.user_id == current_user.id
            )
        )
        
        if not result_record:
            current_app.logger.warning(f"Result ID {result_id} not found in database")
            return jsonify({'error': 'Result not found.'}), 404

        # Clean up old results (keep only last 10 per user)
        old_results = db.session.execute(
            sa.select(MultiStepResult).where(
                MultiStepResult.user_id == current_user.id
            ).order_by(MultiStepResult.timestamp.desc()).offset(10)
        ).scalars().all()
        
        for old_result in old_results:
            db.session.delete(old_result)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'result': result_record.to_dict()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to retrieve multi-step result: {e}")
        return jsonify({'error': f'Failed to retrieve result: {str(e)}'}), 500


@bp.route('/multi_step_results/<result_id>')
@login_required
def multi_step_results(result_id):
    """Display multi-step thinking results in a formatted page."""
    try:
        # Query database for multi-step result
        result_record = db.session.scalar(
            sa.select(MultiStepResult).where(
                MultiStepResult.result_id == result_id,
                MultiStepResult.user_id == current_user.id
            )
        )
        
        if not result_record:
            current_app.logger.warning(f"Result ID {result_id} not found in database")
            flash('Results not found or expired.', 'warning')
            return redirect(url_for('main.generate'))
        
        # Clean up old results (keep only last 10 per user)
        old_results = db.session.execute(
            sa.select(MultiStepResult).where(
                MultiStepResult.user_id == current_user.id
            ).order_by(MultiStepResult.timestamp.desc()).offset(10)
        ).scalars().all()
        
        for old_result in old_results:
            db.session.delete(old_result)
        db.session.commit()
        
        return render_template('multi_step_results.html', title='Multi-Step Results', result=result_record)
        
    except Exception as e:
        current_app.logger.error(f"Failed to display multi-step results: {e}")
        flash('Error loading results.', 'danger')
        return redirect(url_for('main.generate'))


@bp.route('/explain', methods=['POST'])
@login_required
def explain():
    """API endpoint to get an AI explanation for a code block.
    This specifically uses Gemini for the explain button on the view snippet page."""
    data = request.get_json()
    if not data or 'code' not in data:
        return jsonify({'error': 'Missing code in request.'}), 400

    code = data['code']
    explanation = ai_services.explain_code_for_view_snippet(code)
    return jsonify({'explanation': explanation})


@bp.route('/suggest-tags', methods=['POST'])
@login_required
def suggest_tags():
    """API endpoint to get AI-suggested tags for code."""
    try:
        data = request.get_json(silent=True) or {}
        code = data.get('code')
        if not code:
            return jsonify({'error': 'Missing code in request.'}), 400
        suggested = ai_services.suggest_tags_for_code(code)
        if isinstance(suggested, str) and suggested.strip().lower().startswith('error:'):
            return jsonify({'error': suggested}), 500
        # normalize: ensure comma-separated, trimmed
        if isinstance(suggested, str):
            parts = [p.strip() for p in suggested.split(',') if p.strip()]
            suggested = ','.join(parts)
        return jsonify({'tags': suggested})
    except Exception as e:
        current_app.logger.error(f"suggest_tags failed: {e}")
        return jsonify({'error': 'Failed to suggest tags'}), 500


@bp.route('/format-code', methods=['POST'])
@login_required
def format_code():
    """API endpoint to format code using AI."""
    try:
        data = request.get_json(silent=True) or {}
        code = data.get('code')
        language = data.get('language')
        if not code:
            return jsonify({'error': 'Missing code in request.'}), 400
        formatted_code = ai_services.format_code_with_ai(code, language)
        if isinstance(formatted_code, str) and formatted_code.strip().lower().startswith('error:'):
            return jsonify({'error': formatted_code}), 500
        return jsonify({'code': formatted_code})
    except Exception as e:
        current_app.logger.error(f"format_code failed: {e}")
        return jsonify({'error': 'Failed to format code'}), 500


@bp.route('/refine', methods=['POST'])
@login_required
def refine():
    """Refine AI-generated code based on runtime error output and update explanation."""
    data = request.get_json()
    if not data or 'code' not in data or 'error' not in data:
        return jsonify({'error': 'Missing code or error in request.'}), 400

    code = data['code']
    error_text = data['error']
    language_hint = data.get('language')

    refined_code = ai_services.refine_code_with_feedback(code, error_text, language_hint)
    if isinstance(refined_code, str) and refined_code.startswith('Error:'):
        return jsonify({'error': refined_code}), 500

    explanation = ai_services.explain_code(refined_code)
    return jsonify({'code': refined_code, 'explanation': explanation, 'meta': getattr(ai_services, 'LAST_META', {})})


@bp.route('/intelligent_search')
@login_required
def intelligent_search():
    """Renders the intelligent search page without requiring a search query."""
    # Get languages for dropdown
    languages = [row[0] for row in (
        current_user.snippets.with_entities(Snippet.language)
        .distinct().order_by(Snippet.language.asc()).all()
    ) if row[0]]

    # Get selected values from query parameters
    selected_language = request.args.get('language') or ''
    selected_tag = request.args.get('tag') or ''
    selected_sort = request.args.get('sort') or 'date_desc'
    text_query = request.args.get('q') or ''

    return render_template('intelligent_search.html', title='Intelligent Search', results=[], highlights={}, query=text_query, languages=languages, selected_language=selected_language, selected_tag=selected_tag, selected_sort=selected_sort, text_query=text_query)


@bp.route('/search')
@login_required
def search():
    """Multi-approach search: structured filters + keyword + semantic with weighted ranking."""
    import math, re, html
    from datetime import datetime, timezone

    q_text = (request.args.get('q') or '').strip()
    if not q_text:
        return redirect(url_for('main.intelligent_search'))

    # Parse basic operators with a simple, dependency-free parser
    # Supports: tag:foo, lang:python, in:title|desc|code|tags, collection:Name,
    #          before:YYYY-MM-DD, after:YYYY-MM-DD, -term (exclude), quoted phrases
    def parse_query(s: str):
        import shlex, re
        tokens = shlex.split(s)  # respects quotes
        include_terms, exclude_terms, phrases = [], [], []
        tags, languages, collections = [], [], []
        in_fields = set()
        before_dt = after_dt = None
        for t in tokens:
            lo = t.lower()
            if lo.startswith('tag:'):
                tags.append(t[4:])
            elif lo.startswith('lang:') or lo.startswith('language:'):
                languages.append(t.split(':', 1)[1])
            elif lo.startswith('in:'):
                # allow comma separated
                for f in t.split(':',1)[1].split(','):
                    f = f.strip().lower()
                    if f in {'title','desc','description','code','tags'}:
                        in_fields.add('description' if f in {'desc','description'} else f)
            elif lo.startswith('collection:'):
                collections.append(t.split(':',1)[1])
            elif lo.startswith('before:'):
                try:
                    dt = datetime.fromisoformat(t.split(':',1)[1])
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    before_dt = dt
                except Exception:
                    pass
            elif lo.startswith('after:'):
                try:
                    dt = datetime.fromisoformat(t.split(':',1)[1])
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    after_dt = dt
                except Exception:
                    pass
            elif lo.startswith('-') and len(t) > 1:
                exclude_terms.append(t[1:])
            elif ' ' in t and t.startswith('"') and t.endswith('"'):
                phrases.append(t.strip('"'))
            else:
                include_terms.append(t)
        return {
            'include_terms': include_terms,
            'exclude_terms': exclude_terms,
            'phrases': phrases,
            'tags': tags,
            'languages': languages,
            'collections': collections,
            'in_fields': in_fields,
            'before_dt': before_dt,
            'after_dt': after_dt,
        }

    parsed = parse_query(q_text)

    # Base selectable
    sel = sa.select(Snippet).where(Snippet.user_id == current_user.id)

    # Filters
    if parsed['languages']:
        sel = sel.where(Snippet.language.in_(parsed['languages']))
    for t in parsed['tags']:
        sel = sel.where(Snippet.tags.ilike(f'%{t}%'))
    for cname in parsed['collections']:
        sel = sel.where(Snippet.collection.has(Collection.name.ilike(f'%{cname}%')))
    if parsed['before_dt'] is not None:
        sel = sel.where(Snippet.timestamp <= parsed['before_dt'])
    if parsed['after_dt'] is not None:
        sel = sel.where(Snippet.timestamp >= parsed['after_dt'])

    # Determine fields for ILIKE matches
    fields = parsed['in_fields'] or {'title','description','code','tags'}

    # AND across include_terms; each term OR across selected fields
    for term in parsed['include_terms']:
        like = f'%{term}%'
        ors = []
        if 'title' in fields:
            ors.append(Snippet.title.ilike(like))
        if 'description' in fields:
            ors.append(Snippet.description.ilike(like))
        if 'code' in fields:
            ors.append(Snippet.code.ilike(like))
        if 'tags' in fields:
            ors.append(Snippet.tags.ilike(like))
        if ors:
            sel = sel.where(or_(*ors))

    # AND across phrases (phrase must appear in at least one selected field)
    for phrase in parsed['phrases']:
        like = f'%{phrase}%'
        ors = []
        if 'title' in fields:
            ors.append(Snippet.title.ilike(like))
        if 'description' in fields:
            ors.append(Snippet.description.ilike(like))
        if 'code' in fields:
            ors.append(Snippet.code.ilike(like))
        if 'tags' in fields:
            ors.append(Snippet.tags.ilike(like))
        if ors:
            sel = sel.where(or_(*ors))

    # Exclude terms (appear in none of the selected fields)
    for term in parsed['exclude_terms']:
        like = f'%{term}%'
        ands = []
        if 'title' in fields:
            ands.append(~Snippet.title.ilike(like))
        if 'description' in fields:
            ands.append(~Snippet.description.ilike(like))
        if 'code' in fields:
            ands.append(~Snippet.code.ilike(like))
        if 'tags' in fields:
            ands.append(~Snippet.tags.ilike(like))
        if ands:
            sel = sel.where(*ands)

    # Candidate set capped for safety; order by recency initially
    CANDIDATE_CAP = 2000
    sel = sel.order_by(Snippet.timestamp.desc()).limit(CANDIDATE_CAP)
    candidates = db.session.execute(sel).scalars().all()

    if not candidates:
        flash('No snippets found matching your search.', 'info')
        return render_template('intelligent_search.html', title='Intelligent Search', results=[], query=q_text, languages=[], selected_language='', selected_tag='', selected_sort='date_desc', text_query='')

    # Prepare semantic vector
    query_embedding = ai_services.generate_embedding(q_text, task_type="RETRIEVAL_QUERY")
    query_vector = np.array(query_embedding) if query_embedding is not None else None

    # Compute scores
    def keyword_score(sn: Snippet) -> float:
        s = 0.0
        qt = q_text.lower()
        title = (sn.title or '').lower()
        desc = (sn.description or '').lower()
        code = (sn.code or '').lower()
        tags = (sn.tags or '').lower()
        # Field weights
        w_title, w_desc, w_code, w_tags = 3.0, 1.5, 1.0, 2.0
        # Terms
        for t in parsed['include_terms']:
            tl = t.lower()
            if tl in title: s += w_title
            if tl in desc: s += w_desc
            if tl in code: s += w_code
            if tl in tags: s += w_tags
        # Phrases bonus
        for ph in parsed['phrases']:
            pl = ph.lower()
            bonus = 4.0
            if pl in title or pl in desc or pl in code or pl in tags:
                s += bonus
        # Tags exact bonus
        for tg in parsed['tags']:
            tgl = tg.lower()
            if any(part.strip().lower() == tgl for part in (sn.tags or '').split(',')):
                s += 3.0
        # Language boost if queried
        if parsed['languages'] and (sn.language in parsed['languages']):
            s += 2.0
        return s

    # Semantic score for candidates (only compute where embedding exists)
    snippet_vectors = {}
    if query_vector is not None:
        for s in candidates:
            if s.embedding and isinstance(s.embedding, list) and len(s.embedding) > 0 and all(isinstance(x,(int,float)) for x in s.embedding):
                snippet_vectors[s.id] = np.array(s.embedding, dtype=np.float32)
        sem_sims = {sid: ai_services.cosine_similarity(query_vector, vec) for sid, vec in snippet_vectors.items()}
    else:
        sem_sims = {}

    # Recency boost (<= 180 days ~ noticeable; older decays)
    def recency_boost(sn: Snippet) -> float:
        age_days = max(0.0, (datetime.utcnow() - sn.timestamp).days if sn.timestamp else 365.0)
        return math.exp(-age_days / 180.0)  # 1.0 for fresh; ~0.2 at 300 days

    # Weighted fusion
    KW_W, SEM_W, REC_W = 0.6, 0.35, 0.05
    # If user specified in: filters or exact tags/lang, increase KW_W
    if parsed['in_fields'] or parsed['tags'] or parsed['languages']:
        KW_W, SEM_W = 0.7, 0.25

    scored = []
    for sn in candidates:
        kw = keyword_score(sn)
        sem = sem_sims.get(sn.id, 0.0)
        rec = recency_boost(sn)
        score = KW_W * kw + SEM_W * sem + REC_W * rec
        scored.append((score, sn))

    # Also consider top purely semantic matches not in candidates (fallback)
    extra_semantic = []
    if query_vector is not None and not parsed['include_terms'] and not parsed['phrases']:
        # Fetch additional embeddings from user snippets not already in candidates
        all_valid = []
        cand_ids = {s.id for s in candidates}
        for s in current_user.snippets.order_by(Snippet.timestamp.desc()).limit(5000).all():
            if s.id in cand_ids: continue
            if s.embedding and isinstance(s.embedding, list) and len(s.embedding) > 0 and all(isinstance(x,(int,float)) for x in s.embedding):
                all_valid.append(s)
        if all_valid:
            for s in all_valid:
                vec = np.array(s.embedding, dtype=np.float32)
                sim = ai_services.cosine_similarity(query_vector, vec)
                if sim > 0.65:
                    extra_semantic.append((sim, s))
    # Merge extras with a modest weight
    for sim, sn in extra_semantic:
        scored.append((SEM_W * sim, sn))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [sn for _, sn in scored[:500]]

    if not results:
        flash('No snippets found matching your search.', 'info')

    # Build highlights and badges
    highlights = {}
    hi_title, hi_desc, hi_text = {}, {}, {}
    # Build a regex for terms and phrases
    terms = [t for t in parsed['include_terms']] + [p for p in parsed['phrases']]
    pat = None
    if terms:
        safe_terms = [re.escape(t) for t in terms if t]
        try:
            pat = re.compile(r"(" + "|".join(safe_terms) + r")", re.IGNORECASE)
        except re.error:
            pat = None

    def mark(text: str) -> str:
        if not text:
            return ''
        esc = html.escape(text)
        if not pat:
            return esc
        return pat.sub(lambda m: f"<mark>{m.group(0)}</mark>", esc)

    for _, sn in scored:
        badges = []
        if any(t.lower() in (sn.title or '').lower() for t in parsed['include_terms']): badges.append('title')
        if any(t.lower() in (sn.description or '').lower() for t in parsed['include_terms']): badges.append('description')
        if any(t.lower() in (sn.code or '').lower() for t in parsed['include_terms']): badges.append('code')
        if any(t.lower() in (sn.tags or '').lower() for t in parsed['include_terms']): badges.append('tags')
        if any(ph.lower() in ((sn.title or '') + ' ' + (sn.description or '') + ' ' + (sn.code or '') + ' ' + (sn.tags or '')).lower() for ph in parsed['phrases']): badges.append('phrase')
        if parsed['tags'] and any(any(part.strip().lower()==tg.lower() for part in (sn.tags or '').split(',')) for tg in parsed['tags']): badges.append('tag')
        if parsed['languages'] and (sn.language in parsed['languages']): badges.append('language')
        if sem_sims.get(sn.id, 0.0) > 0.65: badges.append('semantic')
        highlights[sn.id] = badges
        hi_title[sn.id] = mark(sn.title or '')
        hi_desc[sn.id] = mark(sn.description or '')
        hi_text[sn.id] = mark(sn.code or '')

    # Get languages for dropdown
    languages = [row[0] for row in (
        current_user.snippets.with_entities(Snippet.language)
        .distinct().order_by(Snippet.language.asc()).all()
    ) if row[0]]

    # Get selected values from query parameters
    selected_language = request.args.get('language') or ''
    selected_tag = request.args.get('tag') or ''
    selected_sort = request.args.get('sort') or 'date_desc'
    text_query = request.args.get('q') or ''

    return render_template('intelligent_search.html', title='Intelligent Search', results=results, highlights=highlights, query=q_text, hi_title=hi_title, hi_desc=hi_desc, hi_text=hi_text, languages=languages, selected_language=selected_language, selected_tag=selected_tag, selected_sort=selected_sort, text_query=text_query)


@bp.route('/collections', methods=['GET', 'POST'])
@login_required
def collections():
    """Page for viewing and managing collections."""
    form = CollectionForm()
    # Populate parent_collection choices, excluding the collection itself if editing
    form.parent_collection.choices = [(0, '--- No Parent ---')] + \
                                     [(c.id, c.name) for c in current_user.collections.filter_by(parent_id=None).order_by(Collection.name).all()]

    if form.validate_on_submit():
        parent_id = form.parent_collection.data if form.parent_collection.data != 0 else None
        collection = Collection(name=form.name.data, user_id=current_user.id, parent_id=parent_id)
        db.session.add(collection)
        db.session.commit()
        check_and_award_badges(current_user) # Check and award badges
            
        flash('New collection created!', 'success')
        return redirect(url_for('main.collections'))

    # Fetch top-level collections (those without a parent)
    user_collections = db.session.query(Collection).filter_by(
        user_id=current_user.id, parent_id=None).order_by(Collection.order.asc(), Collection.name.asc()).all()

    # Get total snippet count for the user
    total_snippets_count = current_user.snippets.count()

    # Get snippet count for each collection
    collections_with_counts = []
    for collection in user_collections:
        snippet_count = collection.snippets.count()
        collections_with_counts.append({'collection': collection, 'snippet_count': snippet_count})

    return render_template('collections.html', title='My Solutions', form=form,
                           collections=collections_with_counts, total_snippets_count=total_snippets_count)

@bp.route('/collection/<int:collection_id>')
@login_required
def view_collection(collection_id):
    """Page to view all snippets within a single collection."""
    page = request.args.get('page', 1, type=int)
    collection = db.session.get(Collection, collection_id)
    if collection is None or collection.owner != current_user:
        flash('Collection not found.', 'danger')
        return redirect(url_for('main.collections'))

    # Query for snippets in this collection and paginate the results
    pagination = collection.snippets.order_by(Snippet.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False)
    
    # Fetch sub-collections
    sub_collections = collection.children.order_by(Collection.name.asc()).all()

    return render_template(
        'view_collection.html',
        title=f"Collection: {collection.name}",
        collection=collection,
        snippets=pagination,
        snippet_count=collection.snippets.count(),
        sub_collections=sub_collections
    )

@bp.route('/collection/<int:collection_id>/rename', methods=['GET', 'POST'])
@login_required
def rename_collection(collection_id):
    """Handles renaming a collection."""
    collection = db.session.get(Collection, collection_id)
    if collection is None or collection.owner != current_user:
        flash('Collection not found.', 'danger')
        return redirect(url_for('main.collections'))

    form = CollectionForm(obj=collection)
    # Populate parent_collection choices, excluding the collection itself and its descendants
    form.parent_collection.choices = [(0, '--- No Parent ---')]
    
    # Compute all descendant collection IDs to prevent cycles
    desc_ids = set()
    pending = [collection]
    while pending:
        node = pending.pop()
        children = node.children.all()
        for ch in children:
            if ch.id not in desc_ids:
                desc_ids.add(ch.id)
                pending.append(ch)

    # Get all collections that are not the current collection or any of its descendants
    query = current_user.collections.filter(Collection.id != collection.id)
    if desc_ids:
        query = query.filter(~Collection.id.in_(list(desc_ids)))
    eligible_parents = query.order_by(Collection.name).all()

    form.parent_collection.choices.extend([(c.id, c.name) for c in eligible_parents])

    if form.validate_on_submit():
        collection.name = form.name.data
        parent_id = form.parent_collection.data if form.parent_collection.data != 0 else None
        # Validate no cycles
        if parent_id == collection.id or (parent_id in desc_ids if parent_id is not None else False):
            flash('Invalid parent collection selection.', 'danger')
            return render_template('rename_collection.html', title='Edit Collection', form=form, collection=collection)
        collection.parent_id = parent_id
        db.session.commit()
        flash('Collection has been updated!', 'success')
        return redirect(url_for('main.collections'))

    elif request.method == 'GET':
        form.name.data = collection.name
        form.parent_collection.data = collection.parent_id or 0

    return render_template('rename_collection.html', title='Edit Collection', form=form, collection=collection)


@bp.route('/collection/<int:collection_id>/delete', methods=['POST'])
@login_required
def delete_collection(collection_id):
    """Handles deleting a collection."""
    collection = db.session.get(Collection, collection_id)
    if collection is None or collection.owner != current_user:
        flash('Collection not found.', 'danger')
        return redirect(url_for('main.collections'))

    # Un-assign snippets from the collection before deleting it
    for snippet in collection.snippets:
        snippet.collection_id = None

    db.session.delete(collection)
    db.session.commit()
    flash('Collection deleted successfully.', 'success')
    return redirect(url_for('main.collections'))


@bp.route('/add_problem', methods=['GET', 'POST'])
@login_required
def add_problem():
    form = LeetcodeProblemForm()
    if form.validate_on_submit():
        problem = LeetcodeProblem(
            title=form.title.data,
            description=form.description.data,
            difficulty=form.difficulty.data,
            tags=form.tags.data,
            leetcode_url=form.leetcode_url.data,
            author=current_user
        )
        db.session.add(problem)
        db.session.commit()
        check_and_award_badges(current_user) # Check and award badges
        flash('Leetcode problem added successfully!', 'success')
        return redirect(url_for('main.index'))
    return render_template('add_problem.html', title='Add Leetcode Problem', form=form)


@bp.route('/problem/<int:problem_id>')
@login_required
def view_problem(problem_id):
    problem = db.session.get(LeetcodeProblem, problem_id)
    if problem is None:
        flash('Problem not found.', 'danger')
        return redirect(url_for('main.index'))
    
    solutions = problem.solutions.filter_by(approved=True).order_by(LeetcodeSolution.timestamp.desc()).all()
    return render_template('view_problem.html', title=problem.title, problem=problem, solutions=solutions)


@bp.route('/generate_solution/<int:problem_id>', methods=['GET', 'POST'])
@login_required
def generate_solution(problem_id):
    problem = db.session.get(LeetcodeProblem, problem_id)
    if problem is None:
        flash('Problem not found.', 'danger')
        return redirect(url_for('main.index'))

    form = GenerateSolutionForm()
    form.problem.choices = [(problem.id, problem.title)] # Pre-select the current problem
    form.problem.data = problem.id # Set default value

    if form.validate_on_submit():
        language = form.language.data
        flash(f'Generating {language} solution for "{problem.title}"...', 'info')
        
        solution_code = ai_services.generate_leetcode_solution(
            problem.title, problem.description, language
        )
        sol_meta = getattr(ai_services, 'LAST_META', {}) or {}
        
        if "Error:" in solution_code:
            flash(solution_code, 'danger')
            return redirect(url_for('main.view_problem', problem_id=problem.id))

        explanation = ai_services.explain_leetcode_solution(
            solution_code, problem.title, language
        )
        expl_meta = getattr(ai_services, 'LAST_META', {}) or {}

        classification = ai_services.classify_leetcode_solution(
            solution_code, problem.description
        )
        cls_meta = getattr(ai_services, 'LAST_META', {}) or {}

        # Small banners for retries/chunking across steps
        if sol_meta.get('retries'):
            attempts = sol_meta.get('retry_attempts', 0)
            flash(f"Notice: Solution generation was retried {attempts} time(s).", 'warning')
        if expl_meta.get('retries'):
            attempts = expl_meta.get('retry_attempts', 0)
            flash(f"Notice: Explanation was retried {attempts} time(s).", 'warning')
        if expl_meta.get('chunked'):
            flash('Large input was processed in multiple parts; the explanation shown is combined.', 'info')
        if cls_meta.get('retries'):
            attempts = cls_meta.get('retry_attempts', 0)
            flash(f"Notice: Classification was retried {attempts} time(s).", 'warning')

        solution = LeetcodeSolution(
            problem=problem,
            contributor=current_user,
            solution_code=solution_code,
            language=language,
            explanation=explanation,
            classification=classification,
            approved=False # Solutions need approval
        )
        try:
            solution.generate_and_set_embedding()
        except Exception as e:
            current_app.logger.warning(f"embedding generation failed (generate_solution): {e}")
        db.session.add(solution)
        db.session.commit()
        flash('Solution generated and awaiting approval!', 'success')
        return redirect(url_for('main.view_solution', solution_id=solution.id))

    return render_template('generate_solution.html', title='Generate Solution', form=form, problem=problem)


@bp.route('/solution/<int:solution_id>')
@login_required
def view_solution(solution_id):
    solution = db.session.get(LeetcodeSolution, solution_id)
    if solution is None:
        flash('Solution not found.', 'danger')
        return redirect(url_for('main.index'))
    
    # Only allow viewing if approved or if current user is the contributor
    if not solution.approved and solution.contributor != current_user:
        flash('This solution is awaiting approval and cannot be viewed yet.', 'warning')
        return redirect(url_for('main.view_problem', problem_id=solution.problem.id))

    return render_template('view_solution.html', title=f"Solution for {solution.problem.title}", solution=solution)


@bp.route('/solution/<int:solution_id>/approve', methods=['GET', 'POST'])
@login_required
def approve_solution(solution_id):
    solution = db.session.get(LeetcodeSolution, solution_id)
    if solution is None:
        flash('Solution not found.', 'danger')
        return redirect(url_for('main.index'))
        
    # Only the problem author or an admin (if we implement roles) can approve
    if solution.problem.author != current_user:
        flash('You do not have permission to approve this solution.', 'danger')
        return redirect(url_for('main.view_solution', solution_id=solution.id))

    form = ApproveSolutionForm(obj=solution)
    if form.validate_on_submit():
        solution.approved = form.approve.data
        db.session.commit()
        if solution.approved:
            current_app.award_points(current_user, 20, "Solution Approved") # Award points for approving a solution
            check_and_award_badges(current_user) # Check and award badges
        flash('Solution approval status updated.', 'success')
        return redirect(url_for('main.view_problem', problem_id=solution.problem.id))
    
    return render_template('approve_solution.html', title='Approve Solution', form=form, solution=solution)


@bp.route('/export_snippets')
@login_required
def export_snippets():
    """Renders the page for exporting snippets."""
    # Provide user's collections for selection
    user_collections = current_user.collections.order_by(Collection.name.asc()).all()
    return render_template('export_snippets.html', title='Export Snippets', collections=user_collections)

@bp.route('/api/export_snippets')
@login_required
def api_export_snippets():
    """Exports user's snippets as segmented JSON for rendering."""
    snippets_data = []
    for snippet in current_user.snippets.order_by(Snippet.timestamp.desc()).all():
        snippets_data.append({
            'id': snippet.id,
            'title': snippet.title,
            'description': snippet.description,
            'code': snippet.code,
            'language': snippet.language,
            'tags': snippet.tags,
            'collection': snippet.collection.name if snippet.collection else 'None',
        })
    return jsonify(snippets_data)


@bp.route('/export/selected_snippets_zip')
@login_required
def export_selected_snippets_zip():
    """Exports selected user snippets as individual Markdown files within a ZIP archive."""
    snippet_ids_str = request.args.get('ids')
    sort = request.args.get('sort') or 'date_desc'

    if not snippet_ids_str:
        flash('No snippets selected for export.', 'danger')
        return redirect(url_for('main.export_snippets'))

    try:
        snippet_ids = [int(s_id) for s_id in snippet_ids_str.split(',') if s_id]
    except ValueError:
        flash('Invalid snippet IDs provided.', 'danger')
        return redirect(url_for('main.export_snippets'))

    sel = sa.select(Snippet).where(
        Snippet.user_id == current_user.id,
        Snippet.id.in_(snippet_ids)
    )

    # Apply ordering
    if sort == 'alpha':
        sel = sel.order_by(Snippet.title.asc())
    elif sort == 'date_asc':
        sel = sel.order_by(Snippet.timestamp.asc())
    else:
        sel = sel.order_by(Snippet.timestamp.desc())

    snippets_to_export = db.session.execute(sel).scalars().all()

    if not snippets_to_export:
        flash('No matching snippets found or you do not have permission to download them.', 'danger')
        return redirect(url_for('main.export_snippets'))

    # Generate ZIP in-memory
    from io import BytesIO
    import zipfile

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for snippet in snippets_to_export:
            # Construct content for each snippet file
            content = f"## {snippet.title}\n"
            content += f"**Language:** {snippet.language}\n"
            if snippet.tags:
                content += f"**Tags:** {snippet.tags}\n"
            if snippet.description:
                content += "\n### Description:\n"
                content += f"{snippet.description}\n"
            content += "\n### Code:\n"
            content += f"```{snippet.language.lower() if snippet.language else ''}\n"
            content += f"{snippet.code}\n"
            content += "```\n"

            # Clean filename - use spaces instead of underscores
            filename = f"{snippet.title.replace('/', '_')}.md"
            zipf.writestr(filename, content.encode('utf-8'))

    zip_buffer.seek(0)
    
    return current_app.response_class(
        zip_buffer.getvalue(),
        headers={
            'Content-Disposition': 'attachment;filename=sophia_selected_snippets.zip',
            'Content-Type': 'application/zip'
        },
        mimetype='application/zip'
    )


# simple in-memory TTL cache for tag suggestions
TAGS_CACHE = {}
TAGS_TTL_SECS = 60

@bp.route('/api/tags')
@login_required
def api_tags():
    """Return unique tag suggestions for the current user.

    Query params:
      q: optional substring filter (case-insensitive)
      limit: max number of results (default 50)
    """
    q = (request.args.get('q') or '').strip()
    try:
        limit = max(1, min(200, int(request.args.get('limit', 50))))
    except ValueError:
        limit = 50

    # Check cache
    cache_key = (current_user.id, q.lower())
    now = time.time()
    cached = TAGS_CACHE.get(cache_key)
    if cached and now - cached['ts'] < TAGS_TTL_SECS:
        return jsonify({'tags': cached['tags']})

    # Fetch only the tags column to reduce payload; cap scan size for safety
    # Prefer most recent first so the suggestions feel relevant
    tag_rows = (
        current_user.snippets.with_entities(Snippet.tags)
        .order_by(Snippet.timestamp.desc())
        .limit(5000)  # defensive cap for scalability
        .all()
    )
    seen = set()
    results = []
    for (tag_str,) in tag_rows:
        if not tag_str:
            continue
        for tok in [p.strip() for p in tag_str.split(',') if p.strip()]:
            if q and q.lower() not in tok.lower():
                continue
            key = tok.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(tok)
            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    # set cache
    TAGS_CACHE[cache_key] = {'tags': results, 'ts': now}
    return jsonify({'tags': results})


@bp.route('/export/current')
@login_required
def export_current_filtered():
    """Export the current filtered set from index as Markdown (streaming)."""
    # reuse index filters
    language = request.args.get('language') or ''
    tag = request.args.get('tag') or ''
    sort = request.args.get('sort') or 'date_desc'
    text = request.args.get('q') or ''

    # Build a selectable and order_by for streaming
    sel = sa.select(Snippet).where(Snippet.user_id == current_user.id)
    if language:
        sel = sel.where(Snippet.language == language)
    if tag:
        sel = sel.where(Snippet.tags.ilike(f'%{tag}%'))
    if text:
        ilike = f"%{text}%"
        sel = sel.where(or_(
            Snippet.title.ilike(ilike),
            Snippet.description.ilike(ilike),
            Snippet.code.ilike(ilike),
            Snippet.tags.ilike(ilike),
        ))
    if sort == 'alpha':
        sel = sel.order_by(Snippet.title.asc())
    elif sort == 'date_asc':
        sel = sel.order_by(Snippet.timestamp.asc())
    else:
        sel = sel.order_by(Snippet.timestamp.desc())

    # Existence check (lightweight)
    exists_row = db.session.execute(sel.limit(1)).scalars().first()
    if not exists_row:
        flash('No snippets match your current filters.', 'warning')
        return redirect(url_for('main.index'))

    def generate():
        yield "# Exported Filtered Snippets\n\n"
        yield "---"
        stream = db.session.execute(
            sel.execution_options(yield_per=200, stream_results=True)
        ).scalars()
        for s in stream:
            yield f"\n\n## {s.title}\n"
            yield f"**Language:** {s.language}\n"
            if s.tags:
                yield f"**Tags:** {s.tags}\n"
            if s.collection:
                yield f"**Collection:** {s.collection.name}\n"
            yield f"**Created At:** {s.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if s.description:
                yield "\n### Description:\n"
                yield f"{s.description}\n"
            yield "\n### Code:\n"
            yield f"```{s.language.lower() if s.language else ''}\n"
            yield f"{s.code}\n"
            yield "```\n"
            yield "\n---"

    return current_app.response_class(
        generate(),
        headers={
            'Content-Disposition': 'attachment;filename=filtered_snippets.md',
            'Content-Type': 'text/markdown'
        },
        mimetype='text/markdown'
    )


@bp.route('/export/download')
@login_required
def download_selected_snippets():
    """Handles downloading selected snippets as a Markdown file (streaming).

    Query options (GET):
      - ids: comma-separated snippet IDs to export
      - collections: comma-separated collection IDs to export
      - include_sub: if '1', include sub-collections of the selected collections
      - sort: optional 'date_desc' (default), 'date_asc', or 'alpha'
    """
    snippet_ids_str = request.args.get('ids')
    collection_ids_str = request.args.get('collections')
    include_sub = request.args.get('include_sub') == '1'
    sort = request.args.get('sort') or 'date_desc'

    sel = sa.select(Snippet).where(Snippet.user_id == current_user.id)

    # Case 1: explicit snippet IDs
    if snippet_ids_str:
        try:
            snippet_ids = [int(s_id) for s_id in snippet_ids_str.split(',') if s_id]
        except ValueError:
            flash('Invalid snippet IDs provided.', 'danger')
            return redirect(url_for('main.export_snippets'))
        sel = sel.where(Snippet.id.in_(snippet_ids))

    # Case 2: collection selection
    elif collection_ids_str:
        try:
            collection_ids = [int(c_id) for c_id in collection_ids_str.split(',') if c_id]
        except ValueError:
            flash('Invalid collection IDs provided.', 'danger')
            return redirect(url_for('main.export_snippets'))

        target_ids = set(collection_ids)
        if include_sub:
            # BFS/DFS to collect descendants
            pending = list(collection_ids)
            seen = set(collection_ids)
            while pending:
                cid = pending.pop()
                col = db.session.get(Collection, cid)
                if not col or col.owner != current_user:
                    continue
                children = col.children.order_by(Collection.name.asc()).all()
                for ch in children:
                    if ch.id not in seen:
                        seen.add(ch.id)
                        target_ids.add(ch.id)
                        pending.append(ch.id)
        sel = sel.where(Snippet.collection_id.in_(list(target_ids)))

    # Case 3: fallback to all snippets for user
    else:
        pass

    # Apply ordering
    if sort == 'alpha':
        sel = sel.order_by(Snippet.title.asc())
    elif sort == 'date_asc':
        sel = sel.order_by(Snippet.timestamp.asc())
    else:
        sel = sel.order_by(Snippet.timestamp.desc())

    # Existence check
    exists_row = db.session.execute(sel.limit(1)).scalars().first()
    if not exists_row:
        flash('No matching snippets found or you do not have permission to download them.', 'danger')
        return redirect(url_for('main.export_snippets'))

    # Capture current_app here
    app = current_app._get_current_object()

    def generate():
        yield "# Exported Snippets from Project Sophia\n\n"
        yield "---"
        with app.app_context():
            stream = db.session.execute(
                sel.execution_options(yield_per=200, stream_results=True)
            ).scalars()
            for snippet in stream:
                yield f"\n\n## {snippet.title}\n"
                yield f"**Language:** {snippet.language}\n"
                if snippet.tags:
                    yield f"**Tags:** {snippet.tags}\n"
                if snippet.collection:
                    yield f"**Collection:** {snippet.collection.name}\n"
                yield f"**Created At:** {snippet.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                if snippet.description:
                    yield "\n### Description:\n"
                    yield f"{snippet.description}\n"
                yield "\n### Code:\n"
                yield f"```{snippet.language.lower() if snippet.language else ''}\n"
                yield f"{snippet.code}\n"
                yield "```\n"
                yield "\n---"  # Separator between snippets

    # Count the number of snippets being exported
    snippets_count = db.session.execute(sel.with_only_columns(sa.func.count())).scalar()
    
    # If only one snippet is selected, use its title as the filename
    if snippets_count == 1:
        single_snippet = db.session.execute(sel.limit(1)).scalars().first()
        if single_snippet:
            filename = f"{single_snippet.title.replace('/', '_')}.md"
        else:
            filename = "snippet.md"
    else:
        filename = "sophia_snippets.md"

    return current_app.response_class(
        generate(),
        headers={
            'Content-Disposition': f'attachment;filename={filename}',
            'Content-Type': 'text/markdown'
        },
        mimetype='text/markdown'
    )


@bp.route('/search_combined')
@login_required
def search_combined():
    """Combined search: runs snippet and solution searches and presents both sections."""
    q_text = (request.args.get('q') or '').strip()
    if not q_text:
        return redirect(url_for('main.index'))
    return redirect(url_for('main.search', q=q_text))

@bp.route('/search_solutions')
@login_required
def search_solutions():
    """Multi-approach search for approved Leetcode solutions with weighted ranking and highlights."""
    import math
    from datetime import datetime, timezone

    q_text = (request.args.get('q') or '').strip()
    if not q_text:
        return redirect(url_for('main.index'))

    # Reuse the same simple parser from snippet search
    def parse_query(s: str):
        import shlex
        tokens = shlex.split(s)
        include_terms, exclude_terms, phrases = [], [], []
        tags, languages = [], []
        in_fields = set()  # title/desc/code/tags map to problem.title/problem.description/solution_code/classification,tags
        before_dt = after_dt = None
        for t in tokens:
            lo = t.lower()
            if lo.startswith('tag:'):
                tags.append(t[4:])
            elif lo.startswith('lang:') or lo.startswith('language:'):
                languages.append(t.split(':', 1)[1])
            elif lo.startswith('in:'):
                for f in t.split(':',1)[1].split(','):
                    f = f.strip().lower()
                    if f in {'title','desc','description','code','tags','explanation','problem'}:
                        in_fields.add('description' if f in {'desc','description'} else f)
            elif lo.startswith('before:'):
                try:
                    dt = datetime.fromisoformat(t.split(':',1)[1])
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    before_dt = dt
                except Exception:
                    pass
            elif lo.startswith('after:'):
                try:
                    dt = datetime.fromisoformat(t.split(':',1)[1])
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                    after_dt = dt
                except Exception:
                    pass
            elif lo.startswith('-') and len(t) > 1:
                exclude_terms.append(t[1:])
            elif ' ' in t and t.startswith('"') and t.endswith('"'):
                phrases.append(t.strip('"'))
            else:
                include_terms.append(t)
        return {
            'include_terms': include_terms,
            'exclude_terms': exclude_terms,
            'phrases': phrases,
            'tags': tags,
            'languages': languages,
            'in_fields': in_fields,
            'before_dt': before_dt,
            'after_dt': after_dt,
        }

    parsed = parse_query(q_text)

    # Base selectable: only approved
    sel = sa.select(LeetcodeSolution).where(LeetcodeSolution.approved == True)

    # Filters
    if parsed['languages']:
        sel = sel.where(LeetcodeSolution.language.in_(parsed['languages']))
    for t in parsed['tags']:
        sel = sel.where(or_(
            LeetcodeSolution.classification.ilike(f'%{t}%'),
            LeetcodeSolution.problem.has(LeetcodeProblem.tags.ilike(f'%{t}%'))
        ))
    if parsed['before_dt'] is not None:
        sel = sel.where(LeetcodeSolution.timestamp <= parsed['before_dt'])
    if parsed['after_dt'] is not None:
        sel = sel.where(LeetcodeSolution.timestamp >= parsed['after_dt'])

    fields = parsed['in_fields'] or {'title','description','code','tags','explanation'}

    # Include terms across chosen fields
    for term in parsed['include_terms']:
        like = f'%{term}%'
        ors = []
        if 'title' in fields:
            ors.append(LeetcodeSolution.problem.has(LeetcodeProblem.title.ilike(like)))
        if 'description' in fields or 'problem' in fields:
            ors.append(LeetcodeSolution.problem.has(LeetcodeProblem.description.ilike(like)))
        if 'code' in fields:
            ors.append(LeetcodeSolution.solution_code.ilike(like))
        if 'tags' in fields:
            ors.append(LeetcodeSolution.classification.ilike(like))
            ors.append(LeetcodeSolution.problem.has(LeetcodeProblem.tags.ilike(like)))
        if 'explanation' in fields:
            ors.append(LeetcodeSolution.explanation.ilike(like))
        if ors:
            sel = sel.where(or_(*ors))

    # Phrases
    for phrase in parsed['phrases']:
        like = f'%{phrase}%'
        ors = []
        ors.append(LeetcodeSolution.problem.has(LeetcodeProblem.title.ilike(like)))
        ors.append(LeetcodeSolution.problem.has(LeetcodeProblem.description.ilike(like)))
        ors.append(LeetcodeSolution.solution_code.ilike(like))
        ors.append(LeetcodeSolution.classification.ilike(like))
        ors.append(LeetcodeSolution.explanation.ilike(like))
        sel = sel.where(or_(*ors))

    # Exclude terms
    for term in parsed['exclude_terms']:
        like = f'%{term}%'
        sel = sel.where(
            ~LeetcodeSolution.solution_code.ilike(like),
            ~LeetcodeSolution.explanation.ilike(like),
            ~LeetcodeSolution.classification.ilike(like),
            ~LeetcodeSolution.problem.has(LeetcodeProblem.title.ilike(like)),
            ~LeetcodeSolution.problem.has(LeetcodeProblem.description.ilike(like)),
            ~LeetcodeSolution.problem.has(LeetcodeProblem.tags.ilike(like)),
        )

    # Candidate cap
    CANDIDATE_CAP = 2000
    sel = sel.order_by(LeetcodeSolution.timestamp.desc()).limit(CANDIDATE_CAP)
    candidates = db.session.execute(sel).scalars().all()

    if not candidates:
        flash('No solutions found matching your search.', 'info')
        return render_template('search_results_solutions.html', title='Search Results', results=[], highlights={}, query=q_text)

    # Semantic
    query_embedding = ai_services.generate_embedding(q_text, task_type="RETRIEVAL_QUERY")
    query_vector = np.array(query_embedding) if query_embedding is not None else None
    sol_vectors = {}
    if query_vector is not None:
        for s in candidates:
            if s.embedding and isinstance(s.embedding, list) and len(s.embedding) > 0 and all(isinstance(x,(int,float)) for x in s.embedding):
                sol_vectors[s.id] = np.array(s.embedding, dtype=np.float32)
        sem_sims = {sid: ai_services.cosine_similarity(query_vector, vec) for sid, vec in sol_vectors.items()}
    else:
        sem_sims = {}

    # Keyword score + badges
    def keyword_score_and_badges(sol: LeetcodeSolution):
        s = 0.0
        b = []
        qt = q_text.lower()
        title = (sol.problem.title or '').lower() if sol.problem else ''
        pdesc = (sol.problem.description or '').lower() if sol.problem else ''
        code = (sol.solution_code or '').lower()
        expl = (sol.explanation or '').lower()
        cls = (sol.classification or '').lower()
        ptags = (sol.problem.tags or '').lower() if sol.problem else ''
        w = {
            'title': 3.0,
            'pdesc': 1.5,
            'code': 1.0,
            'expl': 1.2,
            'cls': 1.2,
            'ptags': 2.0,
        }
        def touch(field):
            if field not in b:
                b.append(field)
        for t in parsed['include_terms']:
            tl = t.lower()
            if tl in title: s += w['title']; touch('title')
            if tl in pdesc: s += w['pdesc']; touch('problem')
            if tl in code: s += w['code']; touch('code')
            if tl in expl: s += w['expl']; touch('explanation')
            if tl in cls: s += w['cls']; touch('classification')
            if tl in ptags: s += w['ptags']; touch('tags')
        for ph in parsed['phrases']:
            pl = ph.lower()
            bonus = 4.0
            if pl in title or pl in pdesc or pl in code or pl in expl or pl in cls or pl in ptags:
                s += bonus; touch('phrase')
        for tg in parsed['tags']:
            tgl = tg.lower()
            if any(part.strip().lower() == tgl for part in (cls or '').split(',')) or (tgl in ptags):
                s += 3.0; touch('tag')
        if parsed['languages'] and (sol.language in parsed['languages']):
            s += 2.0; touch('language')
        return s, b

    KW_W, SEM_W, REC_W = 0.6, 0.35, 0.05
    if parsed['in_fields'] or parsed['tags'] or parsed['languages']:
        KW_W, SEM_W = 0.7, 0.25

    def recency_boost(sol: LeetcodeSolution):
        age_days = max(0.0, (datetime.utcnow() - sol.timestamp).days if sol.timestamp else 365.0)
        return math.exp(-age_days / 180.0)

    scored = []
    highlights = {}
    for sol in candidates:
        kw, badges = keyword_score_and_badges(sol)
        sem = sem_sims.get(sol.id, 0.0)
        rec = recency_boost(sol)
        score = KW_W * kw + SEM_W * sem + REC_W * rec
        if sem > 0.65: badges.append('semantic')
        highlights[sol.id] = badges
        scored.append((score, sol))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [sol for _, sol in scored[:500]]

    # Build highlight maps
    import re, html
    terms = parsed['include_terms'] + parsed['phrases']
    pat = None
    if terms:
        safe_terms = [re.escape(t) for t in terms if t]
        try:
            pat = re.compile(r"(" + "|".join(safe_terms) + r")", re.IGNORECASE)
        except re.error:
            pat = None
    def mark(text: str) -> str:
        if not text:
            return ''
        esc = html.escape(text)
        if not pat:
            return esc
        return pat.sub(lambda m: f"<mark>{m.group(0)}</mark>", esc)
    hi_title = {sol.id: mark(sol.problem.title if sol.problem else '') for sol in results}
    hi_text = {sol.id: mark(sol.explanation or sol.classification or '') for sol in results}

    return render_template('search_results_solutions.html', title='Search Results', results=results, highlights=highlights, query=q_text, hi_title=hi_title, hi_text=hi_text)


@bp.route('/api/user_activity')
@login_required
def user_activity():
    """Provides daily snippet activity data for the logged-in user for the last 90 days."""
    from datetime import datetime, timedelta
    
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=90)
    
    # Get daily snippet counts for the last 90 days
    activity_data = db.session.execute(
        sa.select(
            sa.func.date(Snippet.timestamp).label('date'),
            sa.func.count(Snippet.id).label('count')
        )
        .where(
            Snippet.user_id == current_user.id,
            Snippet.timestamp >= start_date,
            Snippet.timestamp < today + timedelta(days=1)
        )
        .group_by(sa.func.date(Snippet.timestamp))
    ).all()
    
    # Convert to dictionary for easy lookup
    daily_counts = {str(row.date): row.count for row in activity_data}
    
    # Generate all dates in range with 0 for missing dates
    result = []
    for i in range(90):
        date = today - timedelta(days=i)
        date_str = str(date)
        result.append({
            'date': date_str,
            'count': daily_counts.get(date_str, 0)
        })
    
    return jsonify(result)


@bp.route('/user_profile')
@login_required
def user_profile():
    """Displays the current user's profile, points, and badges, and statistics."""
    user_badges = current_user.badges.all()

    # Calculate language distribution for snippets
    language_distribution = db.session.execute(
        sa.select(Snippet.language, sa.func.count(Snippet.id))
        .where(Snippet.user_id == current_user.id)
        .group_by(Snippet.language)
        .order_by(sa.func.count(Snippet.id).desc())
    ).all()

    # Convert to a list of dicts for easier JSON serialization
    language_stats = [{'language': lang, 'count': count} for lang, count in language_distribution]

    # Other relevant analytics
    total_snippets = current_user.snippets.count()
    total_collections = current_user.collections.count()
    total_points = current_user.get_total_points()

    # Calculate average snippet length
    average_snippet_length = db.session.scalar(
        sa.select(sa.func.avg(sa.func.length(Snippet.code)))
        .where(Snippet.user_id == current_user.id)
    )
    # Format to two decimal places, or None if no snippets
    average_snippet_length = f"{average_snippet_length:.2f}" if average_snippet_length is not None else "N/A"

    # Calculate total characters for tokens across snippets, problems, and solutions (roughly 1 token per 4 characters)
    # Snippets
    snippet_char_count = db.session.scalar(
        sa.select(sa.func.sum(sa.func.length(Snippet.code) + sa.func.length(Snippet.description) + sa.func.length(Snippet.tags)))
        .where(Snippet.user_id == current_user.id)
    )

    total_characters_for_tokens = (snippet_char_count or 0)
    total_tokens = round(total_characters_for_tokens / 4)

    # Calculate activity data for the last 12 months for a bar chart
    today = datetime.utcnow().date()
    activity_data = []
    for i in range(12):
        # Go back month by month
        month_date = today - timedelta(days=i * 30)
        # Get the first day of that month
        first_day = month_date.replace(day=1)
        # Get the next month's first day, then subtract one day to get the last day of the current month
        next_month = (first_day + timedelta(days=32)).replace(day=1)
        last_day = next_month - timedelta(days=1)

        count = db.session.scalar(
            sa.select(sa.func.count(Snippet.id))
            .where(
                Snippet.user_id == current_user.id,
                Snippet.timestamp >= first_day,
                Snippet.timestamp <= last_day
            )
        )
        activity_data.append({
            'month': first_day.strftime('%Y-%m'),
            'count': count or 0
        })
    activity_data.reverse() # To show oldest month first

    # Top tags usage
    tag_usage = db.session.execute(
        sa.select(Snippet.tags, sa.func.count(Snippet.id))
        .where(
            Snippet.user_id == current_user.id,
            Snippet.tags.isnot(None)
        )
        .group_by(Snippet.tags)
        .order_by(sa.func.count(Snippet.id).desc())
        .limit(6)
    ).all()
    
    top_tags = []
    for tags_str, count in tag_usage:
        if tags_str:
            for tag in tags_str.split(','):
                tag = tag.strip()
                if tag:
                    # Check if tag already exists
                    existing_tag = next((t for t in top_tags if t['name'] == tag), None)
                    if existing_tag:
                        existing_tag['count'] += count
                    else:
                        top_tags.append({'name': tag, 'count': count})
    
    # Sort by count and limit to top 6
    top_tags = sorted(top_tags, key=lambda x: x['count'], reverse=True)[:6]    # Calculate additional statistics
    # Code quality score (based on average snippet length and diversity)
    if total_snippets > 0:
        # Calculate based on: average length, language diversity, tags usage
        avg_length = float(average_snippet_length) if average_snippet_length != "N/A" else 0
        
        # Length score (optimal: 100-500 chars): 0-40 points
        if avg_length < 50:
            length_score = 20
        elif avg_length > 1000:
            length_score = 25
        else:
            length_score = min(40, int(avg_length / 25))
        
        # Language diversity score: 0-30 points
        language_count = len(language_stats)
        language_score = min(30, language_count * 10)
        
        # Tags usage score: 0-30 points
        tags_count = len([t for t in top_tags if t.get('count', 0) > 0])
        tags_score = min(30, tags_count * 6)
        
        code_quality_score = f"{length_score + language_score + tags_score}%"
    else:
        code_quality_score = "N/A"
    
    # Current streak calculation (consecutive days with activity)
    current_streak = 0
    if total_snippets > 0:
        # Get the last 30 days of activity
        activity_dates = []
        for i in range(30):
            date = (today - timedelta(days=i))
            count = db.session.scalar(
                sa.select(sa.func.count(Snippet.id))
                .where(
                    Snippet.user_id == current_user.id,
                    sa.func.date(Snippet.timestamp) == date
                )
            )
            if count and count > 0:
                activity_dates.append(date)
        
        # Calculate current streak
        if activity_dates:
            current_streak = 1
            for i in range(1, len(activity_dates)):
                if (activity_dates[i-1] - activity_dates[i]).days == 1:
                    current_streak += 1
                else:
                    break
    
    # Total views - calculate based on actual snippet views if view tracking exists
    # For now, calculate as sum of description length (proxy for engagement)
    total_views = db.session.scalar(
        sa.select(sa.func.count(Snippet.id))
        .where(Snippet.user_id == current_user.id)
    ) or 0
    
    # Favorite coding time (most active hour)
    favorite_hour = db.session.execute(
        sa.select(sa.func.strftime('%H', Snippet.timestamp), sa.func.count(Snippet.id))
        .where(Snippet.user_id == current_user.id)
        .group_by(sa.func.strftime('%H', Snippet.timestamp))
        .order_by(sa.func.count(Snippet.id).desc())
        .limit(1)
    ).first()
    
    favorite_coding_time = f"{favorite_hour[0]}:00" if favorite_hour else "Unknown"
    


    return render_template(
        'user_profile.html',
        title='My Profile',
        user_badges=user_badges,
        language_stats=language_stats,
        total_snippets=total_snippets,
        total_collections=total_collections,
        total_points=total_points,
        average_snippet_length=average_snippet_length,
        total_tokens=total_tokens,
        activity_data=activity_data,
        code_quality_score=code_quality_score,
        current_streak=current_streak,
        total_views=total_views,
        favorite_coding_time=favorite_coding_time,
        top_tags=top_tags
    )


@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Allows the current user to change username, email, and password."""
    form = EditProfileForm(obj=current_user)
    if form.validate_on_submit():
        # Check current password
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('edit_profile.html', title='Account Settings', form=form)
        # Uniqueness checks if changed
        new_username = form.username.data.strip()
        new_email = form.email.data.strip()
        if new_username != current_user.username:
            exists = db.session.scalar(sa.select(User).where(User.username == new_username))
            if exists:
                flash('Username already taken.', 'danger')
                return render_template('edit_profile.html', title='Account Settings', form=form)
            current_user.username = new_username
        if new_email != current_user.email:
            exists = db.session.scalar(sa.select(User).where(User.email == new_email))
            if exists:
                flash('Email already in use.', 'danger')
                return render_template('edit_profile.html', title='Account Settings', form=form)
            current_user.email = new_email
        # Optional new password
        if form.new_password.data:
            current_user.set_password(form.new_password.data)
        # Avatar upload (optional)
        try:
            file = request.files.get(form.avatar.name)
            if file and file.filename:
                import os
                from werkzeug.utils import secure_filename
                fn = secure_filename(file.filename)
                ext = (fn.rsplit('.',1)[1].lower() if '.' in fn else 'png')
                if ext not in {'png','jpg','jpeg','gif','webp'}:
                    flash('Unsupported image type.', 'danger')
                    return render_template('edit_profile.html', title='Account Settings', form=form)
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
                os.makedirs(upload_dir, exist_ok=True)
                final_name = f"{current_user.id}.{ext}"
                path = os.path.join(upload_dir, final_name)
                file.save(path)
                current_user.avatar_filename = final_name
        except Exception as e:
            current_app.logger.warning(f"avatar upload failed: {e}")
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('main.user_profile'))
    # Pre-fill
    form.username.data = current_user.username
    form.email.data = current_user.email
    return render_template('edit_profile.html', title='Account Settings', form=form)


@bp.route('/user_settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    """Allows the current user to manage their preferences and AI settings."""
    form = SettingsForm(obj=current_user)
    if form.validate_on_submit():
        # Update user preferences
        current_user.preferred_ai_model = form.preferred_ai_model.data
        current_user.code_generation_style = form.code_generation_style.data
        current_user.auto_explain_code = form.auto_explain_code.data
        current_user.show_line_numbers = form.show_line_numbers.data
        current_user.enable_animations = form.enable_animations.data
        current_user.enable_tooltips = form.enable_tooltips.data
        current_user.tooltip_delay = form.tooltip_delay.data
        current_user.dark_mode = form.dark_mode.data
        current_user.email_notifications = form.email_notifications.data
        current_user.auto_save_snippets = form.auto_save_snippets.data
        current_user.public_profile = form.public_profile.data
        current_user.show_activity = form.show_activity.data
        current_user.snippet_visibility = form.snippet_visibility.data
        
        db.session.commit()
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('main.user_profile'))
    
    # Pre-fill form with current user preferences
    form.preferred_ai_model.data = current_user.preferred_ai_model
    form.code_generation_style.data = current_user.code_generation_style
    form.auto_explain_code.data = current_user.auto_explain_code
    form.show_line_numbers.data = current_user.show_line_numbers
    form.enable_animations.data = current_user.enable_animations
    form.enable_tooltips.data = current_user.enable_tooltips
    form.tooltip_delay.data = current_user.tooltip_delay
    form.dark_mode.data = current_user.dark_mode
    form.email_notifications.data = current_user.email_notifications
    form.auto_save_snippets.data = current_user.auto_save_snippets
    form.public_profile.data = current_user.public_profile
    form.show_activity.data = current_user.show_activity
    form.snippet_visibility.data = current_user.snippet_visibility
    
    return render_template('user_settings.html', title='User Settings', form=form)


@bp.route('/help')
@login_required
def help():
    """Renders the help page."""
    return render_template('help.html', title='Help')


# Individual help topic routes
@bp.route('/help/quick-start')
@login_required
def help_quick_start():
    """Renders the quick start guide help page."""
    return render_template('help_quick_start.html', title='Quick Start Guide')


@bp.route('/help/search-tips')
@login_required
def help_search_tips():
    """Renders the search tips help page."""
    return render_template('help_search_tips.html', title='Search Tips')


@bp.route('/help/ai-features')
@login_required
def help_ai_features():
    """Renders the AI features help page."""
    return render_template('help_ai_features.html', title='AI Features Guide')


@bp.route('/help/navigation-shortcuts')
@login_required
def help_navigation_shortcuts():
    """Renders the navigation shortcuts help page."""
    return render_template('help_navigation_shortcuts.html', title='Navigation Shortcuts')


@bp.route('/help/useful-tips')
@login_required
def help_useful_tips():
    """Renders the useful tips help page."""
    return render_template('help_useful_tips.html', title='Useful Tips')


@bp.route('/help/points-badges')
@login_required
def help_points_badges():
    """Renders the points & badges help page."""
    return render_template('help_points_badges.html', title='Points & Badges Guide')


@bp.route('/help/common-tasks')
@login_required
def help_common_tasks():
    """Renders the common tasks help page."""
    return render_template('help_common_tasks.html', title='Common Tasks Guide')


@bp.route('/help/snippet-actions')
@login_required
def help_snippet_actions():
    """Renders the snippet actions help page."""
    return render_template('help_snippet_actions.html', title='Snippet Actions Guide')


@bp.route('/snippet_actions')
@login_required
def snippet_actions():
    """Renders the snippet actions page."""
    return render_template('snippet_actions.html', title='Snippet Actions')


# --- Chatbot ---
CHAT_SYSTEM_PROMPT = (
    "You are Sophia, the in-app coding assistant for the user's private knowledge base. "
    "Purpose: help the user understand, organize, and apply their code snippets and solutions. "
    "Behaviors: be concise, technical, and accurate. When appropriate, refer to standard terminology, "
    "give step-by-step reasoning, and propose improvements. Avoid unrelated chit-chat. "
    "If asked about topics outside software/code/snippets/solutions, politely steer the user back to the app's domain. "
    "Always respond in clean Markdown. Use headings, bullet points, and fenced code blocks (```lang) for code."
)

@bp.route('/chat')
@login_required
def chat():
    # Load sessions list
    sessions = current_user.chat_sessions.order_by(ChatSession.updated_at.desc()).all()
    # Active session by query or create if none
    q = request.args.get('q')
    active = None
    if sessions:
        active = sessions[0]
    else:
        active = ChatSession(user_id=current_user.id, title='New Chat')
        db.session.add(active)
        db.session.commit()
    messages = active.messages.order_by(ChatMessage.created_at.asc()).all()
    return render_template('chat.html', title='Chat', sessions=sessions, active=active, messages=messages, prefill=q or '')

@bp.route('/api/chat/new', methods=['POST'])
@login_required
def api_chat_new():
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    title = title[:200]
    s = ChatSession(user_id=current_user.id, title=title)
    db.session.add(s)
    db.session.commit()
    return jsonify({'session_id': s.id, 'title': s.title})

@bp.route('/api/chat/history')
@login_required
def api_chat_history():
    sessions = current_user.chat_sessions.order_by(ChatSession.updated_at.desc()).all()
    return jsonify([{'id': s.id, 'title': s.title, 'updated_at': s.updated_at.isoformat()} for s in sessions])

@bp.route('/api/chat/session/<int:session_id>')
@login_required
def api_chat_session(session_id):
    s = db.session.get(ChatSession, session_id)
    if not s or s.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    msgs = s.messages.order_by(ChatMessage.created_at.asc()).all()
    return jsonify([{'role': m.role, 'content': m.content, 'created_at': m.created_at.isoformat()} for m in msgs])

@bp.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Empty message'}), 400
    s = db.session.get(ChatSession, session_id) if session_id else None
    if not s:
        s = ChatSession(user_id=current_user.id, title='New Chat')
        db.session.add(s)
        db.session.commit()
    # Persist user message
    um = ChatMessage(session_id=s.id, role='user', content=user_msg)
    db.session.add(um)
    db.session.commit()
    # Build history
    history = [{'role': m.role, 'content': m.content} for m in s.messages.order_by(ChatMessage.created_at.asc()).all()]
    # Get answer (non-streaming fallback)
    answer = ai_services.chat_answer(CHAT_SYSTEM_PROMPT, history[:-1], user_msg)
    am = ChatMessage(session_id=s.id, role='assistant', content=answer)
    db.session.add(am)
    s.updated_at = sa.func.now()
    db.session.commit()
    return jsonify({'session_id': s.id, 'answer': answer})

@bp.route('/api/chat/stream', methods=['POST'])
@login_required
def api_chat_stream():
    """Streams the assistant answer in calm-paced chunks for the inline widget.
    This uses a simple chunker over the full answer (model streaming not required).
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Empty message'}), 400

    s = db.session.get(ChatSession, session_id) if session_id else None
    if not s:
        s = ChatSession(user_id=current_user.id, title='New Chat')
        db.session.add(s)
        db.session.commit()

    # Save user msg first
    db.session.add(ChatMessage(session_id=s.id, role='user', content=user_msg))
    db.session.commit()

    # Build history excluding the new user message at the end for system context
    history = [{'role': m.role, 'content': m.content} for m in s.messages.order_by(ChatMessage.created_at.asc()).all()]
    answer = ai_services.chat_answer(CHAT_SYSTEM_PROMPT, history[:-1], user_msg)

    # Persist assistant msg now so history is up-to-date in other views
    db.session.add(ChatMessage(session_id=s.id, role='assistant', content=answer))
    s.updated_at = sa.func.now()
    db.session.commit()

    def generate():
        # Calm pace: ~35 chars per 75ms (tunable)
        CHUNK = 35
        DELAY = 0.075
        text = answer or ''
        for i in range(0, len(text), CHUNK):
            yield text[i:i+CHUNK]
            time.sleep(DELAY)
        # End marker (client ignores visually)
        yield "\n"

    return current_app.response_class(generate(), mimetype='text/plain')

@bp.route('/api/chat/delete/<int:session_id>', methods=['POST'])
@login_required
def api_chat_delete(session_id):
    s = db.session.get(ChatSession, session_id)
    if not s or s.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(s)
    db.session.commit()
    return jsonify({'ok': True})

@bp.route('/api/chat/rename/<int:session_id>', methods=['POST'])
@login_required
def api_chat_rename(session_id):
    s = db.session.get(ChatSession, session_id)
    if not s or s.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Title required'}), 400
    s.title = title[:200]
    s.updated_at = sa.func.now()
    db.session.commit()
    return jsonify({'ok': True, 'title': s.title})


@bp.route('/collections/reorder', methods=['POST'])
@login_required
def reorder_collections():
    """Handles reordering of collections via AJAX."""
    data = request.get_json()
    if not data or 'collection_ids' not in data:
        return jsonify({'error': 'Missing collection_ids in request.'}), 400

    collection_ids = data['collection_ids']
    
    try:
        for index, collection_id in enumerate(collection_ids):
            collection = db.session.get(Collection, collection_id)
            if collection and collection.owner == current_user:
                collection.order = index
            else:
                current_app.logger.warning(f"Unauthorized or missing collection_id {collection_id} during reorder for user {current_user.id}")
                return jsonify({'success': False, 'message': f'Unauthorized or missing collection_id {collection_id}.'}), 403
        db.session.commit()
        return jsonify({'success': True, 'message': 'Collections reordered successfully.'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error reordering collections for user {current_user.id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to reorder collections.'}), 500


@bp.route('/snippet/<int:snippet_id>/move', methods=['GET', 'POST'])
@login_required
def move_snippet(snippet_id):
    """Handles moving or copying a snippet to a different collection."""
    snippet = db.session.get(Snippet, snippet_id)
    if snippet is None or snippet.author != current_user:
        flash('Snippet not found or you do not have permission to modify it.', 'danger')
        return redirect(url_for('main.index'))

    form = MoveSnippetForm()
    form.target_collection.choices = [(c.id, c.name) for c in current_user.collections.all()]
    form.target_collection.choices.insert(0, (0, '--- No Collection ---'))

    if form.validate_on_submit():
        target_collection_id = form.target_collection.data if form.target_collection.data != 0 else None
        action = form.action.data

        if action == 'move':
            snippet.collection_id = target_collection_id
            db.session.commit()
            flash(f'Snippet "{snippet.title}" moved successfully!', 'success')
        elif action == 'copy':
            new_snippet = Snippet(
                title=f"Copy of {snippet.title}",
                description=snippet.description,
                code=snippet.code,
                author=current_user,
                tags=snippet.tags,
                language=snippet.language,
                collection_id=target_collection_id
            )
            try:
                new_snippet.generate_and_set_embedding()
            except Exception as e:
                current_app.logger.warning(f"embedding generation failed (copy snippet): {e}")
            db.session.add(new_snippet)
            db.session.commit()
            current_app.award_points(current_user, 5, "Snippet Copied") # Award points for copying a snippet
            
            # Trigger backup after snippet copy
            try:
                from database_backup import increment_snippet_save_counter
                increment_snippet_save_counter()
            except Exception as e:
                current_app.logger.warning(f"Backup trigger failed (copy snippet): {e}")
                
            flash(f'Snippet "{snippet.title}" copied successfully!', 'success')
        
        return redirect(url_for('main.view_snippet', snippet_id=snippet.id))

    return render_template('move_snippet.html', title='Move/Copy Snippet', form=form, snippet=snippet)


@bp.route('/bulk_delete_snippets', methods=['POST'])
@login_required
def bulk_delete_snippets():
    """Handles bulk deletion of snippets."""
    form = BulkActionForm()
    # Manually populate choices for target_collection if needed, though not directly used for delete
    form.target_collection.choices = [(c.id, c.name) for c in current_user.collections.all()]
    form.target_collection.choices.insert(0, (0, '--- No Collection ---'))

    if form.validate_on_submit() and form.action.data == 'delete':
        snippet_ids_str = request.form.get('snippet_ids')
        if not snippet_ids_str:
            flash('No snippets selected for deletion.', 'danger')
            return redirect(url_for('main.index'))

        try:
            snippet_ids = [int(s_id) for s_id in snippet_ids_str.split(',') if s_id]
        except ValueError:
            flash('Invalid snippet IDs provided.', 'danger')
            return redirect(url_for('main.index'))

        deleted_count = 0
        snippets_to_delete = db.session.scalars(
            sa.select(Snippet).where(
                Snippet.id.in_(snippet_ids),
                Snippet.user_id == current_user.id
            )
        ).all()

        for snippet in snippets_to_delete:
            db.session.delete(snippet)
            deleted_count += 1
        db.session.commit()
        flash(f'Successfully deleted {deleted_count} snippets.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')
        flash('Invalid request for bulk deletion.', 'danger')
    return redirect(url_for('main.index'))


@bp.route('/bulk_copy_move_snippets', methods=['POST'])
@login_required
def bulk_copy_move_snippets():
    """Handles bulk copy or move of snippets to a target collection."""
    form = BulkActionForm()
    form.target_collection.choices = [(c.id, c.name) for c in current_user.collections.all()]
    form.target_collection.choices.insert(0, (0, '--- No Collection ---'))

    if form.validate_on_submit():
        snippet_ids_str = request.form.get('snippet_ids')
        action = form.action.data
        target_collection_id = form.target_collection.data if form.target_collection.data != 0 else None

        if not snippet_ids_str:
            flash(f'No snippets selected for {action}.', 'danger')
            return redirect(url_for('main.index'))

        try:
            snippet_ids = [int(s_id) for s_id in snippet_ids_str.split(',') if s_id]
        except ValueError:
            flash('Invalid snippet IDs provided.', 'danger')
            return redirect(url_for('main.index'))

        processed_count = 0
        snippets_to_process = db.session.scalars(
            sa.select(Snippet).where(
                Snippet.id.in_(snippet_ids),
                Snippet.user_id == current_user.id
            )
        ).all()

        for snippet in snippets_to_process:
            if action == 'move':
                snippet.collection_id = target_collection_id
                processed_count += 1
            elif action == 'copy':
                new_snippet = Snippet(
                    title=f"Copy of {snippet.title}",
                    description=snippet.description,
                    code=snippet.code,
                    author=current_user,
                    tags=snippet.tags,
                    language=snippet.language,
                    collection_id=target_collection_id
                )
                try:
                    new_snippet.generate_and_set_embedding()
                except Exception as e:
                    current_app.logger.warning(f"embedding generation failed (bulk copy snippet): {e}")
                db.session.add(new_snippet)
                current_app.award_points(current_user, 5, "Snippet Copied (Bulk)")
                processed_count += 1
                
                # Trigger backup after bulk snippet copy
                try:
                    from database_backup import increment_snippet_save_counter
                    increment_snippet_save_counter()
                except Exception as e:
                    current_app.logger.warning(f"Backup trigger failed (bulk copy snippet): {e}")
        db.session.commit()
        flash(f'Successfully {action}ed {processed_count} snippets.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')
        flash('Invalid request for bulk operation.', 'danger')
    return redirect(url_for('main.index'))


# --- Badge API Endpoints ---

@bp.route('/api/badges')
@login_required
def api_get_badges():
    """Get user's badges with progress information."""
    user_badges = current_user.badges.all()
    badges_data = []
    
    for user_badge in user_badges:
        badges_data.append({
            'id': user_badge.badge.id,
            'name': user_badge.badge.name,
            'description': user_badge.badge.description,
            'image_url': user_badge.badge.image_url,
            'earned_at': user_badge.timestamp.isoformat()
        })
    
    return jsonify({
        'badges': badges_data,
        'total_count': len(badges_data)
    })


@bp.route('/api/badge_progress')
@login_required
def api_badge_progress():
    """Get overall progress towards next badges."""
    # Get user's current stats
    snippet_count = current_user.snippets.count()
    collection_count = current_user.collections.count()
    total_points = current_user.get_total_points()
    
    from app.badge_system import calculate_current_streak, calculate_days_active
    current_streak = calculate_current_streak(current_user)
    days_active = calculate_days_active(current_user)
    
    # Calculate language diversity
    language_count = db.session.scalar(
        sa.select(sa.func.count(sa.distinct(Snippet.language)))
        .where(Snippet.user_id == current_user.id)
    ) or 0
    
    progress = {
        'snippets': {
            'current': snippet_count,
            'next_badge': None,
            'progress_to_next': 0
        },
        'collections': {
            'current': collection_count,
            'next_badge': None,
            'progress_to_next': 0
        },
        'points': {
            'current': total_points,
            'next_badge': None,
            'progress_to_next': 0
        },
        'streak': {
            'current': current_streak,
            'next_badge': None,
            'progress_to_next': 0
        },
        'days_active': {
            'current': days_active,
            'next_badge': None,
            'progress_to_next': 0
        },
        'languages': {
            'current': language_count,
            'next_badge': None,
            'progress_to_next': 0
        }
    }
    
    # Define badge thresholds for progress calculation
    thresholds = {
        'snippets': [1, 5, 10, 25, 50, 100, 250],
        'collections': [1, 5, 10],
        'points': [10, 50, 100, 250],
        'streak': [3, 7, 14, 30],
        'days_active': [30],
        'languages': [3, 5]
    }
    
    for category, current_value in progress.items():
        category_thresholds = thresholds.get(category, [])
        
        # Find next badge threshold
        next_threshold = None
        for threshold in category_thresholds:
            if current_value < threshold:
                next_threshold = threshold
                break
        
        if next_threshold:
            current_value['next_badge'] = next_threshold
            # Calculate progress percentage
            prev_threshold = 0
            for threshold in category_thresholds:
                if current_value < threshold:
                    break
                prev_threshold = threshold
            
            if next_threshold > prev_threshold:
                progress[category]['progress_to_next'] = min(100, (current_value - prev_threshold) / (next_threshold - prev_threshold) * 100)
    
    return jsonify(progress)


# --- Token-Efficient Streaming Pipeline API Routes ---

@bp.route('/api/stream-code-generation', methods=['POST'])
@login_required
def api_stream_code_generation():
    """API endpoint for streaming code generation with token-efficient prompting."""
    try:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt', '').strip()
        session_id = data.get('session_id') or str(uuid.uuid4())
        
        if not prompt:
            return jsonify({'error': 'Prompt is required.'}), 400
        
        def generate():
            try:
                for chunk in ai_services.stream_code_generation(prompt, session_id):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"Streaming code generation failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Streaming failed'})}\n\n"
        
        return current_app.response_class(
            generate(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Stream-Type': 'code_generation'
            }
        )
        
    except Exception as e:
        print(f"Code generation streaming endpoint failed: {e}")
        return jsonify({'error': 'Failed to start code generation stream'}), 500


@bp.route('/api/stream-code-explanation', methods=['POST'])
@login_required
def api_stream_code_explanation():
    """API endpoint for streaming code explanation generation with context pruning."""
    try:
        data = request.get_json(silent=True) or {}
        code_content = data.get('code_content', '').strip()
        session_id = data.get('session_id')
        original_prompt = data.get('original_prompt')
        
        if not code_content:
            return jsonify({'error': 'Code content is required.'}), 400
        
        def generate():
            try:
                for chunk in ai_services.stream_code_explanation(code_content, session_id, original_prompt):
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"Streaming explanation generation failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Streaming explanation failed'})}\n\n"
        
        return current_app.response_class(
            generate(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Stream-Type': 'code_explanation'
            }
        )
        
    except Exception as e:
        print(f"Explanation streaming endpoint failed: {e}")
        return jsonify({'error': 'Failed to start explanation stream'}), 500


@bp.route('/api/chained-streaming-generation', methods=['POST'])
@login_required
def api_chained_streaming_generation():
    """API endpoint for complete token-efficient chaining pipeline with streaming."""
    try:
        data = request.get_json(silent=True) or {}
        prompt = data.get('prompt', '').strip()
        session_id = data.get('session_id') or str(uuid.uuid4())
        code_model = data.get('code_model')
        explanation_model = data.get('explanation_model')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required.'}), 400
        
        # Capture the current app object to use in the generator
        app = current_app._get_current_object()
        
        def generate():
            with app.app_context():
                try:
                    for chunk in ai_services.chained_streaming_generation(prompt, session_id, code_model, explanation_model):
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                    # End of stream marker
                    yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                except Exception as e:
                    # Now we can use current_app.logger since we're in app context
                    current_app.logger.error(f"Chained streaming generation failed: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Pipeline failed'})}\n\n"
        
        return current_app.response_class(
            generate(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Stream-Type': 'chained_generation'
            }
        )
        
    except Exception as e:
        # Use print for logging since we're outside app context
        print(f"Chained streaming endpoint failed: {e}")
        return jsonify({'error': 'Failed to start chained streaming'}), 500


@bp.route('/api/streaming-session/<session_id>')
@login_required
def api_get_streaming_session(session_id):
    """API endpoint to retrieve streaming session state and intermediate results."""
    try:
        from app.utils.state_manager import StreamingStateManager
        
        session_data = StreamingStateManager.get_session_data(session_id)
        if not session_data:
            return jsonify({'error': 'Session not found or expired'}), 404
        
        # Clean up sensitive data
        cleaned_data = {
            'session_id': session_id,
            'pipeline_type': session_data.get('pipeline_type'),
            'status': session_data.get('status'),
            'steps_completed': session_data.get('steps_completed', 0),
            'start_time': session_data.get('start_time'),
            'prompt': session_data.get('prompt')
        }
        
        # Add intermediate results if available
        if session_data.get('intermediate_code'):
            cleaned_data['intermediate_code'] = session_data['intermediate_code']['content']
            cleaned_data['code_timestamp'] = session_data['intermediate_code']['timestamp']
        
        if session_data.get('final_code'):
            cleaned_data['final_code'] = session_data['final_code']['content']
            cleaned_data['code_completed'] = session_data['final_code']['timestamp']
        
        if session_data.get('intermediate_explanation'):
            cleaned_data['intermediate_explanation'] = session_data['intermediate_explanation']['content']
            cleaned_data['explanation_timestamp'] = session_data['intermediate_explanation']['timestamp']
        
        if session_data.get('final_explanation'):
            cleaned_data['final_explanation'] = session_data['final_explanation']['content']
            cleaned_data['explanation_completed'] = session_data['final_explanation']['timestamp']
        
        return jsonify({
            'success': True,
            'session': cleaned_data
        })
        
    except Exception as e:
        print(f"Failed to retrieve streaming session: {e}")
        return jsonify({'error': 'Failed to retrieve session data'}), 500


@bp.route('/api/clear-streaming-session/<session_id>', methods=['POST'])
@login_required
def api_clear_streaming_session(session_id):
    """API endpoint to clear streaming session data."""
    try:
        from app.utils.state_manager import StreamingStateManager
        
        StreamingStateManager.clear_session(session_id)
        
        return jsonify({
            'success': True,
            'message': 'Streaming session cleared'
        })
        
    except Exception as e:
        print(f"Failed to clear streaming session: {e}")
        return jsonify({'error': 'Failed to clear session'}), 500


@bp.route('/api/model-tiering-config')
@login_required
def api_model_tiering_config():
    """API endpoint to get model tiering configuration for client-side optimization."""
    try:
        config = ai_services.MODEL_TIERING_CONFIG
        
        # Return configuration with descriptions
        return jsonify({
            'success': True,
            'config': {
                'code_generation': {
                    'primary': {
                        'model': config['code_generation']['primary'],
                        'description': 'High-reasoning model for complex code generation',
                        'cost': 'medium',
                        'speed': 'medium'
                    },
                    'fallback': {
                        'model': config['code_generation']['fallback'],
                        'description': 'Faster fallback model for code generation',
                        'cost': 'low',
                        'speed': 'fast'
                    },
                    'cost_optimized': {
                        'model': config['code_generation']['cost_optimized'],
                        'description': 'Most cost-effective model for basic code',
                        'cost': 'very_low',
                        'speed': 'very_fast'
                    }
                },
                'explanation': {
                    'primary': {
                        'model': config['explanation']['primary'],
                        'description': 'Fast model for code explanations',
                        'cost': 'low',
                        'speed': 'fast'
                    },
                    'fallback': {
                        'model': config['explanation']['fallback'],
                        'description': 'Backup model for explanations',
                        'cost': 'low',
                        'speed': 'fast'
                    },
                    'cost_optimized': {
                        'model': config['explanation']['cost_optimized'],
                        'description': 'Most cost-effective for explanations',
                        'cost': 'very_low',
                        'speed': 'very_fast'
                    }
                }
            }
        })
        
    except Exception as e:
        print(f"Failed to get model tiering config: {e}")
        return jsonify({'error': 'Failed to get model configuration'}), 500


@bp.route('/api/user-preferences')
@login_required
def api_user_preferences():
    """API endpoint to get user tooltip and other UI preferences."""
    try:
        return jsonify({
            'success': True,
            'preferences': {
                'enable_tooltips': current_user.enable_tooltips,
                'tooltip_delay': current_user.tooltip_delay,
                'enable_animations': current_user.enable_animations,
                'show_line_numbers': current_user.show_line_numbers,
                'dark_mode': current_user.dark_mode
            }
        })
    except Exception as e:
        current_app.logger.error(f"Failed to get user preferences: {e}")
        return jsonify({'error': 'Failed to get user preferences'}), 500

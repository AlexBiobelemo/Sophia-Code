# Additional settings route to add to routes.py

# Add this import to the top of routes.py (around line 14-17)
from app.forms import (RegistrationForm, LoginForm, SnippetForm,
                       AIGenerationForm, CollectionForm, NoteForm,
                       LeetcodeProblemForm, GenerateSolutionForm, ApproveSolutionForm,
                       MoveSnippetForm, EditProfileForm, BulkActionForm, SettingsForm)

# Add this route after the edit_profile route (around line 1901)
@bp.route('/app_settings', methods=['GET', 'POST'])
@login_required
def app_settings():
    """Allows users to manage their AI preferences and app settings."""
    form = SettingsForm(obj=current_user)
    
    if form.validate_on_submit():
        # Update all settings fields
        current_user.preferred_ai_model = form.preferred_ai_model.data
        current_user.code_generation_style = form.code_generation_style.data
        current_user.auto_explain_code = form.auto_explain_code.data
        current_user.show_line_numbers = form.show_line_numbers.data
        current_user.enable_animations = form.enable_animations.data
        current_user.dark_mode = form.dark_mode.data
        current_user.email_notifications = form.email_notifications.data
        current_user.auto_save_snippets = form.auto_save_snippets.data
        current_user.public_profile = form.public_profile.data
        current_user.show_activity = form.show_activity.data
        current_user.snippet_visibility = form.snippet_visibility.data
        
        db.session.commit()
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('main.app_settings'))
    
    # Pre-fill form with current values
    form.preferred_ai_model.data = current_user.preferred_ai_model or 'gemini-2.5-flash'
    form.code_generation_style.data = current_user.code_generation_style or 'balanced'
    form.auto_explain_code.data = current_user.auto_explain_code or True
    form.show_line_numbers.data = current_user.show_line_numbers or True
    form.enable_animations.data = current_user.enable_animations or True
    form.dark_mode.data = current_user.dark_mode or True
    form.email_notifications.data = current_user.email_notifications or True
    form.auto_save_snippets.data = current_user.auto_save_snippets or True
    form.public_profile.data = current_user.public_profile or False
    form.show_activity.data = current_user.show_activity or True
    form.snippet_visibility.data = current_user.snippet_visibility or 'private'
    
    return render_template('app_settings.html', title='App Settings', form=form)
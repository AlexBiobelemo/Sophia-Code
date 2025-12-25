@bp.route('/help')
@login_required
def help():
    """Renders the help page with comprehensive tips and guides."""
    return render_template('help.html', title='Help & Tips')
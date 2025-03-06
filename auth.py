from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
import logging

from extensions import db
from models import User
from helpers.arcade import (
    start_linkedin_auth, start_x_auth,
    check_auth_status, post_to_linkedin, post_to_x,
    LINKEDIN_TOOL, X_TOOL
)
from helpers.openai import validate_post_length, SocialPlatform

# Set up logging
logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if not email or not password or not name:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('auth.register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))
            
        user = User(email=email, name=name)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember', '0') == '1'
        
        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('auth.login'))
            
        user = User.query.filter_by(email=email).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))
            
        login_user(user, remember=remember)
        
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('index')
            
        return redirect(next_page)
        
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Debug log the form data
        logger.info(f"Profile form data: {request.form}")
        
        # Get form data
        name = request.form.get('name')
        email = request.form.get('email')
        bio = request.form.get('bio')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        # Handle checkbox which will only be in the form data if checked
        autonomous_mode = 'autonomous_mode' in request.form
        
        # Debug log the autonomous_mode value
        logger.info(f"Autonomous mode in form: {'autonomous_mode' in request.form}")
        logger.info(f"Autonomous mode setting: {autonomous_mode}")
        
        # Validate required fields
        if not name or not email:
            flash('Name and email are required.', 'error')
            return redirect(url_for('auth.profile'))
            
        # Check if email is taken by another user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != current_user.id:
            flash('Email already taken.', 'error')
            return redirect(url_for('auth.profile'))
            
        # Update user information
        current_user.name = name
        current_user.email = email
        
        # Handle bio - strip whitespace and set to None if empty
        if bio:
            bio = bio.strip()
            current_user.bio = bio if bio else None
        else:
            current_user.bio = None
            
        current_user.autonomous_mode = autonomous_mode
        
        # Handle password change if requested and not using SSO
        if current_password and new_password and current_user.auth_type != 'okta':
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')
        elif current_password and new_password and current_user.auth_type == 'okta':
            flash('Password changes are not allowed for SSO users.', 'warning')
            
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')

@bp.route('/linkedin/connect')
@login_required
def linkedin_connect():
    """Start LinkedIn authorization through Arcade."""
    try:
        auth_result = start_linkedin_auth(current_user)
        if auth_result['status'] == 'pending':
            return redirect(auth_result['url'])
        else:
            db.session.commit()
            flash('Successfully connected to LinkedIn!', 'success')
    except Exception as e:
        flash(f'Error connecting to LinkedIn: {str(e)}', 'error')
    
    return redirect(url_for('auth.profile'))

@bp.route('/linkedin/check-auth')
@login_required
def check_linkedin_auth():
    """Check LinkedIn authorization status."""
    try:
        is_authorized = check_auth_status(current_user, LINKEDIN_TOOL)
        if is_authorized and not current_user.linkedin_authorized:
            current_user.linkedin_authorized = True
            db.session.commit()
            return jsonify({'status': 'completed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'status': 'pending'})

@bp.route('/linkedin/post', methods=['POST'])
@login_required
def linkedin_post():
    """Post content to LinkedIn using Arcade."""
    content = request.json.get('content')
    if not content:
        return jsonify({'success': False, 'error': 'No content provided'}), 400
        
    try:
        # Validate content for LinkedIn
        is_valid, total_length, limit = validate_post_length(content, platform=SocialPlatform.LINKEDIN)
        
        if not is_valid:
            return jsonify({
                'success': False, 
                'error': f'Content exceeds LinkedIn character limit ({total_length}/{limit} characters)'
            }), 400
            
        response = post_to_linkedin(current_user, content)
        # Return a simplified response with just the success status
        return jsonify({
            'success': True,
            'message': 'Successfully posted to LinkedIn'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/x/connect')
@login_required
def x_connect():
    """Start X authorization through Arcade."""
    try:
        auth_result = start_x_auth(current_user)
        if auth_result['status'] == 'pending':
            return redirect(auth_result['url'])
        else:
            db.session.commit()
            flash('Successfully connected to X!', 'success')
    except Exception as e:
        flash(f'Error connecting to X: {str(e)}', 'error')
    
    return redirect(url_for('auth.profile'))

@bp.route('/x/check-auth')
@login_required
def check_x_auth():
    """Check X authorization status."""
    try:
        is_authorized = check_auth_status(current_user, X_TOOL)
        if is_authorized and not current_user.x_authorized:
            current_user.x_authorized = True
            db.session.commit()
            return jsonify({'status': 'completed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'status': 'pending'})

@bp.route('/x/post', methods=['POST'])
@login_required
def x_post():
    """Post content to X using Arcade."""
    content = request.json.get('content')
    if not content:
        return jsonify({'success': False, 'error': 'No content provided'}), 400
        
    try:
        # Validate content for Twitter/X
        is_valid, total_length, limit = validate_post_length(content, platform=SocialPlatform.TWITTER)
        
        if not is_valid:
            return jsonify({
                'success': False, 
                'error': f'Content exceeds Twitter character limit ({total_length}/{limit} characters)'
            }), 400
            
        response = post_to_x(current_user, content)
        return jsonify({
            'success': True,
            'message': 'Successfully posted to X'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500 
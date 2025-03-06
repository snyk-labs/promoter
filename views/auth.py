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

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if not email or not password or not name:
            flash('Email, password, and name are required.', 'error')
            return render_template('auth/register.html')
            
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')
            
        # Create new user
        user = User(
            email=email,
            name=name,
            auth_type='password'
        )
        user.set_password(password)
        
        # Add user to database
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Log in an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = bool(request.form.get('remember_me'))
        
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('auth/login.html')
            
        # Validate user credentials
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html')
            
        # Log in the user
        login_user(user, remember=remember_me)
        
        # Redirect to the next page or home
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for('main.index')
            
        return redirect(next_page)
    
    return render_template('auth/login.html')

@bp.route('/logout')
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    return redirect(url_for('main.index'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """View and edit user profile."""
    if request.method == 'POST':
        # Update user information
        name = request.form.get('name')
        bio = request.form.get('bio')
        
        if not name:
            flash('Name is required.', 'error')
            return render_template('auth/profile.html')
            
        # Update the user's profile
        current_user.name = name
        current_user.bio = bio
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        
    return render_template('auth/profile.html')

@bp.route('/linkedin/connect')
@login_required
def linkedin_connect():
    """Start LinkedIn authentication process."""
    try:
        auth_url, request_token = start_linkedin_auth()
        
        # Store the request token for later verification
        session['linkedin_request_token'] = request_token
        
        # Redirect user to LinkedIn authorization page
        return redirect(auth_url)
    except Exception as e:
        flash(f'Error connecting to LinkedIn: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))

@bp.route('/linkedin/check-auth')
@login_required
def check_linkedin_auth():
    """Check if user is authenticated with LinkedIn."""
    try:
        # Check if user has LinkedIn token
        is_authenticated, expiry = check_auth_status(current_user.id, LINKEDIN_TOOL)
        
        return jsonify({
            'authenticated': is_authenticated,
            'expiry': expiry
        })
    except Exception as e:
        return jsonify({
            'authenticated': False,
            'error': str(e)
        })

@bp.route('/linkedin/post', methods=['POST'])
@login_required
def linkedin_post():
    """Post content to LinkedIn."""
    try:
        # Get post content
        data = request.get_json()
        post_content = data.get('post')
        
        if not post_content:
            return jsonify({
                'success': False,
                'error': 'Post content is required'
            })
            
        # Validate post length
        is_valid_for_twitter, is_valid_for_linkedin, length = validate_post_length(post_content)
        
        if not is_valid_for_linkedin:
            return jsonify({
                'success': False,
                'error': f'Post exceeds LinkedIn character limit ({length} characters)'
            })
            
        # Post to LinkedIn
        result = post_to_linkedin(current_user.id, post_content)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Posted to LinkedIn successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@bp.route('/x/connect')
@login_required
def x_connect():
    """Start X/Twitter authentication process."""
    try:
        auth_url, request_token = start_x_auth()
        
        # Store the request token for later verification
        session['x_request_token'] = request_token
        
        # Redirect user to X/Twitter authorization page
        return redirect(auth_url)
    except Exception as e:
        flash(f'Error connecting to X/Twitter: {str(e)}', 'error')
        return redirect(url_for('auth.profile'))

@bp.route('/x/check-auth')
@login_required
def check_x_auth():
    """Check if user is authenticated with X/Twitter."""
    try:
        # Check if user has X/Twitter token
        is_authenticated, expiry = check_auth_status(current_user.id, X_TOOL)
        
        return jsonify({
            'authenticated': is_authenticated,
            'expiry': expiry
        })
    except Exception as e:
        return jsonify({
            'authenticated': False,
            'error': str(e)
        })

@bp.route('/x/post', methods=['POST'])
@login_required
def x_post():
    """Post content to X/Twitter."""
    try:
        # Get post content
        data = request.get_json()
        post_content = data.get('post')
        
        if not post_content:
            return jsonify({
                'success': False,
                'error': 'Post content is required'
            })
            
        # Validate post length
        is_valid_for_twitter, is_valid_for_linkedin, length = validate_post_length(post_content)
        
        if not is_valid_for_twitter:
            return jsonify({
                'success': False,
                'error': f'Post exceeds Twitter character limit ({length} characters)'
            })
            
        # Post to X/Twitter
        result = post_to_x(current_user.id, post_content)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Posted to X/Twitter successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

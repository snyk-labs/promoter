from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from flask_login import login_user, current_user
import requests
import json
import logging

from models import User
from extensions import db
from helpers.okta import (
    OKTA_CLIENT_ID, OKTA_CLIENT_SECRET, OKTA_ISSUER,
    OKTA_REDIRECT_URI, OKTA_SCOPES, OKTA_ENABLED,
    build_authorization_url, exchange_code_for_tokens,
    validate_id_token, get_user_profile, generate_secure_state_and_nonce
)

logger = logging.getLogger(__name__)
bp = Blueprint('okta_auth', __name__)

@bp.route('/login')
def login():
    """Redirect to Okta for authentication."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    # Check if Okta is enabled
    if not OKTA_ENABLED:
        flash('Okta SSO is not enabled', 'error')
        return redirect(url_for('auth.login'))
    
    # Store original destination for after login
    next_url = request.args.get('next', url_for('index'))
    
    # Generate a secure state parameter to prevent CSRF and nonce to prevent replay attacks
    state, nonce = generate_secure_state_and_nonce()
    session['okta_state'] = state
    session['next_url'] = next_url
    session['okta_nonce'] = nonce
    
    # Build and redirect to the Okta authorization URL
    auth_url = build_authorization_url(state, nonce)
    return redirect(auth_url)

@bp.route('/callback')
def callback():
    """Handle the callback from Okta after authentication."""
    # Check for error parameter
    if 'error' in request.args:
        error = request.args.get('error')
        error_description = request.args.get('error_description', 'Unknown error')
        logger.error(f"Okta authentication error: {error} - {error_description}")
        flash(f"Authentication error: {error_description}", 'error')
        return redirect(url_for('auth.login'))
    
    # Verify state to prevent CSRF
    state = request.args.get('state')
    if state != session.get('okta_state'):
        logger.error("Invalid state parameter in Okta callback")
        flash('Invalid state parameter, possible CSRF attack', 'error')
        return redirect(url_for('auth.login'))
    
    # Exchange code for tokens
    code = request.args.get('code')
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Error exchanging code for tokens: {str(e)}")
        flash(f"Error during authentication: {str(e)}", 'error')
        return redirect(url_for('auth.login'))
    
    # Validate the ID token
    id_token = tokens.get('id_token')
    nonce = session.get('okta_nonce')
    try:
        claims = validate_id_token(id_token, nonce)
    except Exception as e:
        logger.error(f"Error validating ID token: {str(e)}")
        flash(f"Error validating credentials: {str(e)}", 'error')
        return redirect(url_for('auth.login'))
    
    # Get user info using the access token
    access_token = tokens.get('access_token')
    try:
        user_info = get_user_profile(access_token)
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        flash(f"Error retrieving user profile: {str(e)}", 'error')
        return redirect(url_for('auth.login'))
        
    # Extract user details from ID token claims
    email = claims.get('email', '')
    first_name = claims.get('given_name', '')
    last_name = claims.get('family_name', '')
    # Combine first and last name
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = email.split('@')[0]  # Use part of email as fallback
    okta_id = claims.get('sub', '')
    
    # Look up or create user in database
    user = User.query.filter_by(email=email).first()
    
    if user:
        # Update existing user details if needed
        user.name = full_name
        user.okta_id = okta_id
    else:
        # Create new user
        user = User(
            email=email,
            name=full_name,
            okta_id=okta_id,
            auth_type='okta',
            password_hash=None  # No password for SSO users
        )
        db.session.add(user)
    
    # Save the changes
    db.session.commit()
    
    # Log the user in
    login_user(user)
    logger.info(f"User {email} logged in via Okta SSO")
    
    # Clean up session
    if 'okta_state' in session:
        del session['okta_state']
    if 'okta_nonce' in session:
        del session['okta_nonce']
    
    # Redirect to the originally requested page or default to home
    next_url = session.pop('next_url', url_for('index'))
    return redirect(next_url) 
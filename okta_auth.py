from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from flask_login import login_user, current_user
import requests
import json
import secrets
from jose import jwt
from urllib.parse import urlencode
import logging

from models import User
from extensions import db
from okta_config import (
    OKTA_CLIENT_ID, OKTA_CLIENT_SECRET, OKTA_ISSUER,
    OKTA_REDIRECT_URI, OKTA_SCOPES, OKTA_ENABLED
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
    
    # Generate a secure state parameter to prevent CSRF
    state = secrets.token_urlsafe(32)
    session['okta_state'] = state
    session['next_url'] = next_url
    
    # Generate a secure nonce to prevent replay attacks
    nonce = secrets.token_urlsafe(32)
    session['okta_nonce'] = nonce
    
    # Build the Okta authorization URL
    auth_params = {
        'client_id': OKTA_CLIENT_ID,
        'response_type': 'code',
        'scope': ' '.join(OKTA_SCOPES),
        'redirect_uri': OKTA_REDIRECT_URI,
        'state': state,
        'nonce': nonce
    }
    
    auth_url = f"{OKTA_ISSUER}/v1/authorize?{urlencode(auth_params)}"
    logger.info(f"Redirecting to Okta for authentication: {auth_url}")
    return redirect(auth_url)

@bp.route('/callback')
def callback():
    """Handle the Okta callback and authenticate the user."""
    # Verify error response
    if 'error' in request.args:
        flash(f"Login error: {request.args.get('error_description', 'Unknown error')}", 'error')
        return redirect(url_for('auth.login'))
    
    # Exchange the authorization code for tokens
    code = request.args.get('code')
    if not code:
        flash('No authorization code received', 'error')
        return redirect(url_for('auth.login'))
    
    # Verify the state parameter to prevent CSRF
    state = request.args.get('state')
    if state != session.get('okta_state'):
        flash('Invalid state parameter', 'error')
        logger.warning(f"State mismatch: received {state}, expected {session.get('okta_state')}")
        return redirect(url_for('auth.login'))
    
    # Get the next URL from the session
    next_url = session.get('next_url', url_for('index'))
    
    # Prepare token exchange request
    token_url = f"{OKTA_ISSUER}/v1/token"
    token_payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': OKTA_REDIRECT_URI,
        'client_id': OKTA_CLIENT_ID,
        'client_secret': OKTA_CLIENT_SECRET
    }
    
    try:
        # Exchange code for tokens
        token_response = requests.post(token_url, data=token_payload)
        token_response.raise_for_status()
        tokens = token_response.json()
        
        # Extract ID token to get user information
        id_token = tokens['id_token']
        id_token_claims = jwt.decode(
            id_token,
            '',  # Skip signature verification here for simplicity
            options={"verify_signature": False}
        )
        
        # Verify nonce to prevent replay attacks
        received_nonce = id_token_claims.get('nonce')
        if received_nonce != session.get('okta_nonce'):
            flash('Invalid token nonce', 'error')
            logger.warning(f"Nonce mismatch: received {received_nonce}, expected {session.get('okta_nonce')}")
            return redirect(url_for('auth.login'))
        
        # Extract user info from the token
        okta_id = id_token_claims['sub']
        email = id_token_claims.get('email', '')
        name = id_token_claims.get('name', email.split('@')[0] if email else 'Okta User')
        
        logger.info(f"User authenticated with Okta: {email} (ID: {okta_id})")
        
        # Find or create the user
        user = User.find_or_create_okta_user(okta_id, email, name)
        
        # Log in the user
        login_user(user)
        flash('Successfully authenticated with Okta', 'success')
        
        # Clean up session
        session.pop('okta_state', None)
        session.pop('okta_nonce', None)
        session.pop('next_url', None)
        
        # Store access token for potential API requests
        session['access_token'] = tokens.get('access_token')
        
        # Redirect to the original destination
        return redirect(next_url)
        
    except requests.exceptions.RequestException as e:
        flash(f'Error communicating with Okta: {str(e)}', 'error')
        logger.error(f"Okta token exchange error: {str(e)}")
        return redirect(url_for('auth.login'))
    except jwt.JWTError as e:
        flash(f'Error processing Okta token: {str(e)}', 'error')
        logger.error(f"JWT decoding error: {str(e)}")
        return redirect(url_for('auth.login'))
    except Exception as e:
        flash(f'Unexpected error: {str(e)}', 'error')
        logger.error(f"Unexpected error in Okta callback: {str(e)}", exc_info=True)
        return redirect(url_for('auth.login')) 
import os
from dotenv import load_dotenv
import logging

# Load environment variables if .env file exists
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Okta settings
OKTA_ENABLED = os.environ.get('OKTA_ENABLED', 'false').lower() == 'true'
OKTA_CLIENT_ID = os.environ.get('OKTA_CLIENT_ID', '')
OKTA_CLIENT_SECRET = os.environ.get('OKTA_CLIENT_SECRET', '')
OKTA_ISSUER = os.environ.get('OKTA_ISSUER', '')
OKTA_AUTH_SERVER_ID = os.environ.get('OKTA_AUTH_SERVER_ID', 'default')
OKTA_AUDIENCE = os.environ.get('OKTA_AUDIENCE', 'api://default')
OKTA_SCOPES = os.environ.get('OKTA_SCOPES', 'openid profile email').split(' ')
OKTA_REDIRECT_URI = os.environ.get('OKTA_REDIRECT_URI', 'http://localhost:5000/auth/okta/callback')

def validate_okta_config():
    """Validate that all required Okta configuration is provided when Okta is enabled."""
    if not OKTA_ENABLED:
        logger.info("Okta SSO integration is disabled")
        return True
        
    # Check for required Okta settings
    missing_settings = []
    if not OKTA_CLIENT_ID:
        missing_settings.append('OKTA_CLIENT_ID')
    if not OKTA_CLIENT_SECRET:
        missing_settings.append('OKTA_CLIENT_SECRET')
    if not OKTA_ISSUER:
        missing_settings.append('OKTA_ISSUER')
        
    if missing_settings:
        error_msg = f"Missing required Okta configuration: {', '.join(missing_settings)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Log successful validation
    logger.info("Okta configuration validated successfully")
    return True 
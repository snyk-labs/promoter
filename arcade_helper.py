import os
from arcadepy import Arcade
from flask import current_app

# Initialize Arcade client
client = Arcade()  # Automatically finds the `ARCADE_API_KEY` env variable
LINKEDIN_TOOL = "LinkedIn.CreateTextPost"
X_TOOL = "X.PostTweet"

def start_linkedin_auth(user):
    """Start LinkedIn authorization process through Arcade."""
    auth_response = client.tools.authorize(
        tool_name=LINKEDIN_TOOL,
        user_id=user.email,
    )
    
    if auth_response.status != "completed":
        return {
            'status': 'pending',
            'url': auth_response.url
        }
    else:
        user.linkedin_authorized = True
        return {
            'status': 'completed'
        }

def start_x_auth(user):
    """Start X (Twitter) authorization process through Arcade."""
    auth_response = client.tools.authorize(
        tool_name=X_TOOL,
        user_id=user.email,
    )
    
    if auth_response.status != "completed":
        return {
            'status': 'pending',
            'url': auth_response.url
        }
    else:
        user.x_authorized = True
        return {
            'status': 'completed'
        }

def check_auth_status(user, tool_name):
    """Check if authorization is complete for the specified tool."""
    try:
        auth_response = client.auth.get_status(
            tool_name=tool_name,
            user_id=user.email
        )
        return auth_response.status == "completed"
    except Exception:
        return False

def post_to_linkedin(user, content):
    """Post content to LinkedIn using Arcade."""
    if not user.linkedin_authorized:
        raise ValueError("LinkedIn not authorized")
        
    try:
        response = client.tools.execute(
            tool_name=LINKEDIN_TOOL,
            input={"text": content},
            user_id=user.email
        )
        return response
    except Exception as e:
        raise ValueError(f"Failed to post to LinkedIn: {str(e)}")

def post_to_x(user, content):
    """Post content to X (Twitter) using Arcade."""
    if not user.x_authorized:
        raise ValueError("X not authorized")
        
    try:
        response = client.tools.execute(
            tool_name=X_TOOL,
            input={"tweet_text": content},
            user_id=user.email
        )
        return response
    except Exception as e:
        raise ValueError(f"Failed to post to X: {str(e)}") 
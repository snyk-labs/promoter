from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from models import Episode, Post, Video
from helpers.openai import (
    generate_social_post, validate_post_length, 
    TWITTER_CHAR_LIMIT, LINKEDIN_CHAR_LIMIT, SocialPlatform
)

# Create a blueprint for API routes
bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/promote/podcast/<int:episode_id>', methods=['POST'])
@login_required
def promote_podcast(episode_id):
    """API endpoint for podcast promotion."""
    episode = Episode.query.get_or_404(episode_id)
    
    try:
        # Generate post with retry logic for character limit validation
        social_post = generate_social_post(episode, current_user, max_retries=3)
        
        # Validate length for different platforms
        is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
        
        # Prepare warnings if needed
        warnings = []
        # Improved bio check: Only warn if bio is None, empty string, or just whitespace
        if not current_user.bio or (isinstance(current_user.bio, str) and not current_user.bio.strip()):
            warnings.append('Adding information about yourself in your profile will help generate better posts!')
        
        if not is_valid_for_twitter:
            warnings.append(f'Post exceeds Twitter character limit ({total_length}/{TWITTER_CHAR_LIMIT} characters)')
        
        return jsonify({
            'success': True,
            'post': social_post,
            'character_count': total_length,
            'twitter_limit': TWITTER_CHAR_LIMIT,
            'linkedin_limit': LINKEDIN_CHAR_LIMIT,
            'warnings': warnings if warnings else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/promote/video/<int:video_id>', methods=['POST'])
@login_required
def promote_video(video_id):
    """API endpoint for video promotion."""
    video = Video.query.get_or_404(video_id)
    
    try:
        # Generate post with retry logic for character limit validation
        social_post = generate_social_post(video, current_user, max_retries=3)
        
        # Validate length for different platforms
        is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
        
        # Prepare warnings if needed
        warnings = []
        # Improved bio check: Only warn if bio is None, empty string, or just whitespace
        if not current_user.bio or (isinstance(current_user.bio, str) and not current_user.bio.strip()):
            warnings.append('Adding information about yourself in your profile will help generate better posts!')
        
        if not is_valid_for_twitter:
            warnings.append(f'Post exceeds Twitter character limit ({total_length}/{TWITTER_CHAR_LIMIT} characters)')
        
        return jsonify({
            'success': True,
            'post': social_post,
            'character_count': total_length,
            'twitter_limit': TWITTER_CHAR_LIMIT,
            'linkedin_limit': LINKEDIN_CHAR_LIMIT,
            'warnings': warnings if warnings else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/promote/blog/<int:post_id>', methods=['POST'])
@login_required
def promote_blog_post(post_id):
    """API endpoint for blog post promotion."""
    blog_post = Post.query.get_or_404(post_id)
    
    try:
        # Generate post with retry logic for character limit validation
        social_post = generate_social_post(blog_post, current_user, max_retries=3)
        
        # Validate length for different platforms
        is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
        
        # Prepare warnings if needed
        warnings = []
        # Improved bio check: Only warn if bio is None, empty string, or just whitespace
        if not current_user.bio or (isinstance(current_user.bio, str) and not current_user.bio.strip()):
            warnings.append('Adding information about yourself in your profile will help generate better posts!')
        
        if not is_valid_for_twitter:
            warnings.append(f'Post exceeds Twitter character limit ({total_length}/{TWITTER_CHAR_LIMIT} characters)')
        
        return jsonify({
            'success': True,
            'post': social_post,
            'character_count': total_length,
            'twitter_limit': TWITTER_CHAR_LIMIT,
            'linkedin_limit': LINKEDIN_CHAR_LIMIT,
            'warnings': warnings if warnings else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

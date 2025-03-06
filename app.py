from flask import Flask, render_template, jsonify
import os
from flask_login import login_required, current_user
from flask_migrate import Migrate
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from extensions import db, login_manager
from models import Episode, User, Post, Video
from cli import init_db, sync_podcast, sync_blog, sync_youtube
from auth import bp as auth_bp
from helpers.openai import (
    generate_social_post, validate_post_length, 
    TWITTER_CHAR_LIMIT, LINKEDIN_CHAR_LIMIT, SocialPlatform
)
from helpers.okta import OKTA_ENABLED, validate_okta_config
from okta_auth import bp as okta_auth_bp

def create_app():
    app = Flask(__name__)
    
    # Database Configuration
    # Use DATABASE_URL environment variable if available
    # Otherwise, fall back to default SQLite for development
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # If DATABASE_URL is provided, use it directly
        if database_url.startswith('postgres://'):
            # Handle potential 'postgres://' format that Heroku might provide
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            app.logger.info(f"Using PostgreSQL database from environment: {database_url.split('@')[0]}@...")
        elif database_url.startswith('sqlite:///'):
            # Handle SQLite URLs in DATABASE_URL
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            app.logger.info(f"Using custom SQLite database: {database_url}")
        else:
            # Handle other database types
            app.config['SQLALCHEMY_DATABASE_URI'] = database_url
            app.logger.info(f"Using database from environment: {database_url.split(':')[0]}")
    else:
        # Fall back to default SQLite for development
        basedir = os.path.abspath(os.path.dirname(__file__))
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'promoter.db')
        app.logger.info("Using default SQLite database for development")
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Set secret key for session management
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-please-change')
    
    # Add Okta configuration to app config
    app.config['OKTA_ENABLED'] = OKTA_ENABLED
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Initialize Flask-Migrate
    migrate = Migrate(app, db)
    
    # Validate Okta configuration
    with app.app_context():
        try:
            validate_okta_config()
        except ValueError as e:
            app.logger.warning(f"Okta configuration error: {str(e)}")
            app.config['OKTA_ENABLED'] = False

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(id):
        """Load user by ID."""
        return db.session.get(User, int(id))

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Register Okta blueprint if enabled
    if app.config['OKTA_ENABLED']:
        app.register_blueprint(okta_auth_bp, url_prefix='/auth/okta')
        app.logger.info("Okta SSO integration enabled")
    else:
        app.logger.info("Okta SSO integration disabled")

    # Register CLI commands
    app.cli.add_command(sync_podcast)
    app.cli.add_command(init_db)
    app.cli.add_command(sync_blog)
    app.cli.add_command(sync_youtube)

    @app.route('/')
    def index():
        # Get all episodes, posts, and videos ordered by publish date (most recent first)
        episodes = Episode.query.order_by(Episode.publish_date.desc()).all()
        posts = Post.query.order_by(Post.publish_date.desc()).all()
        videos = Video.query.order_by(Video.publish_date.desc()).all()
        
        # Combine all content into a single list
        content_items = []
        
        # Add episodes with a content_type indicator
        for episode in episodes:
            content_items.append({
                'item': episode,
                'content_type': 'podcast'
            })
            
        # Add posts with a content_type indicator
        for post in posts:
            content_items.append({
                'item': post,
                'content_type': 'blog'
            })
            
        # Add videos with a content_type indicator
        for video in videos:
            content_items.append({
                'item': video,
                'content_type': 'video'
            })
            
        # Sort all content by publish date (most recent first)
        content_items.sort(key=lambda x: x['item'].publish_date, reverse=True)
        
        return render_template('index.html', content_items=content_items)

    @app.route('/api/promote/podcast/<int:episode_id>', methods=['POST'])
    @login_required
    def promote_podcast(episode_id):
        """Standardized endpoint for podcast promotion"""
        episode = Episode.query.get_or_404(episode_id)
        
        try:
            # Generate post with retry logic for character limit validation
            social_post = generate_social_post(episode, current_user, max_retries=3)
            
            # Validate length for different platforms
            is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
            
            # Prepare warnings if needed
            warnings = []
            if not current_user.bio or not current_user.bio.strip():
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

    @app.route('/api/promote/video/<int:video_id>', methods=['POST'])
    @login_required
    def promote_video(video_id):
        video = Video.query.get_or_404(video_id)
        
        try:
            # Generate post with retry logic for character limit validation
            social_post = generate_social_post(video, current_user, max_retries=3)
            
            # Validate length for different platforms
            is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
            
            # Prepare warnings if needed
            warnings = []
            if not current_user.bio or not current_user.bio.strip():
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
    
    @app.route('/api/promote/blog/<int:post_id>', methods=['POST'])
    @login_required
    def promote_blog_post(post_id):
        blog_post = Post.query.get_or_404(post_id)
        
        try:
            # Generate post with retry logic for character limit validation
            social_post = generate_social_post(blog_post, current_user, max_retries=3)
            
            # Validate length for different platforms
            is_valid_for_twitter, is_valid_for_linkedin, total_length = validate_post_length(social_post)
            
            # Prepare warnings if needed
            warnings = []
            if not current_user.bio or not current_user.bio.strip():
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

    return app

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True) 
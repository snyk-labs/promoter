import click
import feedparser
from datetime import datetime
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError
import re
from bs4 import BeautifulSoup
import urllib.parse

from extensions import db
from models import Episode, User, Post, Video
from helpers.openai import generate_platform_specific_posts
from helpers.arcade import post_to_linkedin, post_to_x
from helpers.utils import clean_html, parse_date, normalize_url, extract_youtube_id, truncate_text

@click.command('init-db')
@with_appcontext
def init_db():
    """Initialize the database by dropping all tables and recreating them.
    
    This is a destructive operation and should only be used during initial setup
    or when you want to completely reset the database.
    
    For normal database migrations, use 'flask db migrate' and 'flask db upgrade'
    commands provided by Flask-Migrate.
    """
    click.echo('Dropping all tables...')
    db.drop_all()
    click.echo('Creating database tables...')
    db.create_all()
    click.echo('Database tables created successfully.')

def handle_autonomous_posting(content_item):
    """Automatically post about new content for users with autonomous mode enabled."""
    # Find all users with autonomous mode enabled who have at least one social account connected
    users = User.query.filter(
        User.autonomous_mode == True,
        (User.linkedin_authorized == True) | (User.x_authorized == True)
    ).all()
    
    if not users:
        click.echo("No users with autonomous mode enabled and social accounts connected.")
        return
        
    # Detect content type for log messages
    from models import Episode, Post, Video
    if isinstance(content_item, Episode):
        content_type = "podcast episode"
        content_title = f"Episode {content_item.episode_number}: {content_item.title}"
    elif isinstance(content_item, Video):
        content_type = "video"
        content_title = content_item.title
    elif isinstance(content_item, Post):
        content_type = "blog post"
        content_title = content_item.title
    else:
        content_type = "content"
        content_title = getattr(content_item, 'title', 'Unknown')
    
    click.echo(f"Processing autonomous posting for {len(users)} users...")
    
    for user in users:
        click.echo(f"\nProcessing for user: {user.email}")
        
        try:
            # Generate platform-specific posts
            platform_posts = generate_platform_specific_posts(content_item, user, max_retries=3)
            
            success = False
            
            # Post to LinkedIn if authorized and content was successfully generated
            if user.linkedin_authorized and 'linkedin' in platform_posts and platform_posts['linkedin']:
                try:
                    linkedin_content = platform_posts['linkedin']
                    click.echo(f"LinkedIn post ({len(linkedin_content)} characters):")
                    click.echo(f"> {linkedin_content}")
                    
                    post_to_linkedin(user, linkedin_content)
                    click.echo(f"✓ Posted to LinkedIn for {user.email}")
                    success = True
                except Exception as e:
                    click.echo(f"× Failed to post to LinkedIn for {user.email}: {str(e)}")
            elif user.linkedin_authorized:
                click.echo(f"× No LinkedIn content was generated for {user.email}")
            
            # Post to X if authorized and content was successfully generated
            if user.x_authorized and 'twitter' in platform_posts and platform_posts['twitter']:
                try:
                    twitter_content = platform_posts['twitter']
                    click.echo(f"Twitter post ({len(twitter_content)} characters):")
                    click.echo(f"> {twitter_content}")
                    
                    post_to_x(user, twitter_content)
                    click.echo(f"✓ Posted to X for {user.email}")
                    success = True
                except Exception as e:
                    click.echo(f"× Failed to post to X for {user.email}: {str(e)}")
            elif user.x_authorized:
                click.echo(f"× No Twitter content was generated for {user.email}")
            
            if success:
                click.echo(f"Successfully posted {content_type} for user {user.email}")
            else:
                click.echo(f"No successful posts for user {user.email}")
                
        except Exception as e:
            click.echo(f"Error processing autonomous posting for user {user.email}: {str(e)}")

@click.command('sync-podcast')
@click.argument('rss_url')
@with_appcontext
def sync_episodes(rss_url):
    """Sync podcast episodes from the RSS feed."""
    click.echo('Fetching podcast episodes from RSS feed...')
    
    feed = feedparser.parse(rss_url)
    
    if feed.bozo:  # Check if there was an error parsing the feed
        click.echo(f'Error parsing RSS feed: {feed.bozo_exception}')
        return
    
    new_episodes = 0
    total_episodes = len(feed.entries)
    newly_added_episodes = []
    
    # Get podcast image from feed if available (used as a fallback)
    podcast_image_url = None
    if hasattr(feed, 'feed') and hasattr(feed.feed, 'image') and hasattr(feed.feed.image, 'href'):
        podcast_image_url = feed.feed.image.href
    
    for index, entry in enumerate(feed.entries):
        # Use the episode number from the feed if available, otherwise use reverse index
        episode_number = total_episodes - index
        
        # Get the title
        title = entry.title
        
        # Get the description - clean up HTML if present
        description = entry.get('summary', '')
        if description:
            # Remove HTML tags if present
            soup = BeautifulSoup(description, 'html.parser')
            description = soup.get_text()
        
        # Convert published date to datetime
        try:
            publish_date = datetime(*entry.published_parsed[:6])
        except (AttributeError, TypeError):
            publish_date = datetime.utcnow()
        
        # Get the episode URL
        player_url = entry.get('link', '')
        
        # Get episode image URL - try multiple possible locations in RSS feed
        image_url = None
        
        # Check for itunes:image
        if 'image' in entry and hasattr(entry.image, 'href'):
            image_url = entry.image.href
        elif hasattr(entry, 'itunes_image') and hasattr(entry.itunes_image, 'href'):
            image_url = entry.itunes_image.href
        # Check for media:thumbnail
        elif 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
            image_url = entry.media_thumbnail[0].get('url', '')
        # Check for media:content
        elif 'media_content' in entry and len(entry.media_content) > 0:
            for content in entry.media_content:
                if content.get('type', '').startswith('image/'):
                    image_url = content.get('url', '')
                    break
        # Use podcast-level image as fallback
        elif podcast_image_url:
            image_url = podcast_image_url
            
        # Create episode object
        episode = Episode(
            episode_number=episode_number,
            title=title,
            description=description,
            player_url=player_url,
            image_url=image_url,
            publish_date=publish_date
        )
        
        # Check if episode already exists
        existing_episode = Episode.query.filter_by(
            title=title,  # Check by title instead of episode number
            publish_date=publish_date  # And publish date for uniqueness
        ).first()
        
        if existing_episode:
            continue
        
        try:
            db.session.add(episode)
            db.session.commit()
            new_episodes += 1
            newly_added_episodes.append(episode)
            click.echo(f'Added episode: {title}')
        except IntegrityError:
            db.session.rollback()
            click.echo(f'Error saving episode "{title}", skipping...')
    
    click.echo(f'Successfully added {new_episodes} new episodes to the database.')
    
    # Handle autonomous posting for each new episode
    if newly_added_episodes:
        click.echo("\nProcessing autonomous posting for new episodes...")
        for episode in newly_added_episodes:
            click.echo(f"Processing autonomous posting for episode: {episode.title}")
            handle_autonomous_posting(episode)

@click.command('sync-blog')
@click.argument('rss_url')
@with_appcontext
def sync_blog(rss_url):
    """Sync blog posts from the RSS feed."""
    click.echo('Fetching blog posts from RSS feed...')
    
    feed = feedparser.parse(rss_url)
    
    if feed.bozo:  # Check if there was an error parsing the feed
        click.echo(f'Error parsing RSS feed: {feed.bozo_exception}')
        return
    
    new_posts = 0
    total_posts = len(feed.entries)
    newly_added_posts = []
    
    # Get blog image from feed if available (used as a fallback)
    blog_image_url = None
    if hasattr(feed, 'feed') and hasattr(feed.feed, 'image') and hasattr(feed.feed.image, 'href'):
        blog_image_url = feed.feed.image.href
    
    for entry in feed.entries:
        # Get the title
        title = entry.title
        
        # Get the link/URL
        url = entry.get('link', '')
        
        # Get the content - clean up HTML if present
        content = ''
        content_html = ''
        if 'content' in entry:
            if isinstance(entry.content, list) and len(entry.content) > 0:
                content_html = entry.content[0].value
                content = entry.content[0].value
            else:
                content_html = entry.content
                content = entry.content
        elif 'summary' in entry:
            content_html = entry.summary
            content = entry.summary
        
        if content:
            # Strip HTML tags for plain text content but keep the html version for image extraction
            soup = BeautifulSoup(content, 'html.parser')
            content = soup.get_text()
        
        # Get the excerpt (shorter version of content)
        excerpt = content[:500] + '...' if len(content) > 500 else content
        
        # Get the author
        author = ''
        if 'author' in entry:
            author = entry.author
        elif 'author_detail' in entry and 'name' in entry.author_detail:
            author = entry.author_detail.name
        
        # Get blog post image URL - try multiple possible locations in RSS feed
        image_url = None
        
        # Check for itunes:image
        if 'image' in entry and hasattr(entry.image, 'href'):
            image_url = entry.image.href
            click.echo(f'  Found image (itunes:image): {image_url}')
        elif hasattr(entry, 'itunes_image') and hasattr(entry.itunes_image, 'href'):
            image_url = entry.itunes_image.href
            click.echo(f'  Found image (itunes_image): {image_url}')
        # Check for media:thumbnail
        elif 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
            image_url = entry.media_thumbnail[0].get('url', '')
            click.echo(f'  Found image (media:thumbnail): {image_url}')
        # Check for media:content
        elif 'media_content' in entry and len(entry.media_content) > 0:
            for content_item in entry.media_content:
                if content_item.get('type', '').startswith('image/'):
                    image_url = content_item.get('url', '')
                    click.echo(f'  Found image (media:content): {image_url}')
                    break
        # Try to extract first image from content HTML if available
        if not image_url and content_html:
            try:
                soup = BeautifulSoup(content_html, 'html.parser')
                img_tags = soup.find_all('img')
                
                # Try to find a suitable image (prefer larger images with absolute URLs)
                for img in img_tags:
                    if img.has_attr('src'):
                        # Prefer images that aren't icons or tiny thumbnails
                        src = img['src']
                        width = img.get('width')
                        height = img.get('height')
                        
                        # Skip tiny images
                        if (width and int(width) < 50) or (height and int(height) < 50):
                            continue
                            
                        # Skip icons and common tiny images
                        if 'icon' in src.lower() or 'avatar' in src.lower() or 'emoji' in src.lower():
                            continue
                            
                        # Make relative URLs absolute if possible
                        if src.startswith('/') and url:
                            try:
                                base_url = '/'.join(url.split('/')[:3])  # Get base domain
                                src = base_url + src
                            except Exception as e:
                                click.echo(f'  Error constructing absolute URL: {e}')
                        
                        image_url = src
                        click.echo(f'  Found image (content HTML, improved): {image_url}')
                        break
            except Exception as e:
                click.echo(f'  Error parsing content HTML: {e}')
                
        # Try to extract from summary if no image found yet
        if not image_url and 'summary' in entry:
            summary_html = entry.summary
            if summary_html:
                try:
                    soup = BeautifulSoup(summary_html, 'html.parser')
                    img_tag = soup.find('img')
                    if img_tag and img_tag.has_attr('src'):
                        image_url = img_tag['src']
                        click.echo(f'  Found image (summary HTML): {image_url}')
                except Exception as e:
                    click.echo(f'  Error parsing summary HTML: {e}')
        # Use blog-level image as fallback
        if not image_url and blog_image_url:
            image_url = blog_image_url
            click.echo(f'  Using blog-level fallback image: {image_url}')
            
        # Debug log the entry structure if no image found
        if not image_url:
            click.echo(f'  No image found for blog post: {title}')
            # Log entry keys to help debug
            click.echo(f'  Entry keys: {list(entry.keys())}')
            
            # Check for enclosures (another potential source of images)
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if hasattr(enclosure, 'type') and enclosure.type.startswith('image/'):
                        if hasattr(enclosure, 'href') or hasattr(enclosure, 'url'):
                            image_url = getattr(enclosure, 'href', None) or getattr(enclosure, 'url', None)
                            if image_url:
                                click.echo(f'  Found image (enclosure): {image_url}')
                                break
        
        # Final check if we found an image or not
        if image_url:
            click.echo(f'  Final image URL for "{title}": {image_url}')
        
        # Convert published date to datetime
        try:
            publish_date = datetime(*entry.published_parsed[:6])
        except (AttributeError, TypeError):
            publish_date = datetime.utcnow()
        
        # Get the source name from the feed title if available
        source = feed.feed.get('title', '')
        
        # Create post object
        post = Post(
            title=title,
            content=content,
            excerpt=excerpt,
            url=url,
            image_url=image_url,
            author=author,
            publish_date=publish_date,
            source=source
        )
        
        # Check if post already exists
        existing_post = Post.query.filter_by(
            title=title,
            url=url
        ).first()
        
        if existing_post:
            continue
        
        try:
            db.session.add(post)
            db.session.commit()
            new_posts += 1
            newly_added_posts.append(post)
            click.echo(f'Added blog post: {title}')
        except IntegrityError:
            db.session.rollback()
            click.echo(f'Error saving blog post "{title}", skipping...')
    
    click.echo(f'Successfully added {new_posts} new blog posts to the database.')
    
    # Handle autonomous posting for each new post
    if newly_added_posts and 'handle_autonomous_posting' in globals():
        click.echo("\nProcessing autonomous posting for new blog posts...")
        for post in newly_added_posts:
            click.echo(f"Processing autonomous posting for blog post: {post.title}")
            handle_autonomous_posting(post)

@click.command('sync-youtube')
@click.argument('rss_url')
@with_appcontext
def sync_youtube(rss_url):
    """Sync videos from a YouTube channel's RSS feed."""
    click.echo('Fetching videos from YouTube RSS feed...')
    
    feed = feedparser.parse(rss_url)
    
    if feed.bozo:  # Check if there was an error parsing the feed
        click.echo(f'Error parsing RSS feed: {feed.bozo_exception}')
        return
    
    new_videos = 0
    total_videos = len(feed.entries)
    newly_added_videos = []
    shorts_filtered = 0
    
    # Get channel info from feed if available
    channel_name = feed.feed.get('title', '').replace(' - YouTube', '')
    channel_id = ''
    
    for entry in feed.entries:
        # Get video ID from link or entry ID
        video_id = ''
        if 'link' in entry:
            # Extract video ID from URL
            parsed_url = urllib.parse.urlparse(entry.link)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            video_id = query_params.get('v', [''])[0]
            
            # Check if this is a YouTube Short (shorts format URL)
            is_short = "/shorts/" in entry.link
        
        if not video_id and 'yt_videoid' in entry:
            video_id = entry.yt_videoid
        
        if not video_id:
            # If still no video ID, try to extract from entry ID
            if 'id' in entry:
                match = re.search(r'video:([a-zA-Z0-9_-]+)', entry.id)
                if match:
                    video_id = match.group(1)
        
        if not video_id:
            click.echo(f'Could not extract video ID for entry: {entry.get("title", "Unknown")}')
            continue
            
        # Get the title
        title = entry.title
        
        # Get the description
        description = ''
        if 'summary' in entry:
            description = entry.summary
        elif 'media_description' in entry:
            description = entry.media_description
        
        if description:
            # Strip HTML tags if present
            soup = BeautifulSoup(description, 'html.parser')
            full_description = soup.get_text().strip()
            
            # Create a shorter version for display
            excerpt = full_description
            if len(excerpt) > 250:
                excerpt = excerpt[:250].strip() + '...'
        else:
            full_description = ''
            excerpt = ''
        
        # Get video URL
        url = entry.get('link', f'https://www.youtube.com/watch?v={video_id}')
        
        # Get thumbnail URL
        thumbnail_url = ''
        if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
            thumbnail_url = entry.media_thumbnail[0].get('url', '')
        
        # Get channel ID if not found earlier
        if not channel_id and 'author_detail' in entry and 'href' in entry.author_detail:
            channel_url = entry.author_detail.href
            channel_id_match = re.search(r'channel/([a-zA-Z0-9_-]+)', channel_url)
            if channel_id_match:
                channel_id = channel_id_match.group(1)
        
        # If still no channel name, try to get from author
        if not channel_name and 'author' in entry:
            channel_name = entry.author
        
        # Convert published date to datetime
        try:
            publish_date = datetime(*entry.published_parsed[:6])
        except (AttributeError, TypeError):
            publish_date = datetime.utcnow()
        
        # Get duration if available
        duration = ''
        if 'media_content' in entry and len(entry.media_content) > 0:
            duration = entry.media_content[0].get('duration', '')
            
        # Check for YouTube Shorts based on available criteria
        is_short = False
        
        # Primary method: Check if the URL explicitly contains "/shorts/"
        if "/shorts/" in url:
            is_short = True
            shorts_filtered += 1
            click.echo(f'Skipping YouTube Short (URL pattern detected): {title}')
            continue
            
        # Secondary method: Look for #shorts hashtag in title or description
        if "#shorts" in title.lower() or (full_description and "#shorts" in full_description.lower()):
            is_short = True
            shorts_filtered += 1
            click.echo(f'Skipping YouTube Short (hashtag detected): {title}')
            continue
            
        # Tertiary method: Check duration (if available) and title patterns
        # This is less reliable, so we add additional checks
        if duration and duration.isdigit() and int(duration) <= 60:
            # Common Short title patterns
            short_title_patterns = [
                "short", "#short", "#ytshort", "#ytshorts", 
                "vertical", "tiktok", "reel", "trending"
            ]
            
            if any(pattern in title.lower() for pattern in short_title_patterns):
                is_short = True
                shorts_filtered += 1
                click.echo(f'Skipping YouTube Short (duration + title pattern detected): {title}')
                continue
        
        # Create video object
        video = Video(
            video_id=video_id,
            title=title,
            description=full_description,  # Store full description
            excerpt=excerpt,  # Store shorter version for display
            thumbnail_url=thumbnail_url,
            url=url,
            channel_name=channel_name,
            channel_id=channel_id,
            publish_date=publish_date,
            duration=duration
        )
        
        # Check if video already exists
        existing_video = Video.query.filter_by(video_id=video_id).first()
        
        if existing_video:
            continue
        
        try:
            db.session.add(video)
            db.session.commit()
            new_videos += 1
            newly_added_videos.append(video)
            click.echo(f'Added video: {title}')
        except IntegrityError:
            db.session.rollback()
            click.echo(f'Error saving video "{title}", skipping...')
    
    click.echo(f'Successfully added {new_videos} new videos to the database.')
    if shorts_filtered > 0:
        click.echo(f'Filtered out {shorts_filtered} YouTube Shorts.')
    
    # Handle autonomous posting for each new video
    if newly_added_videos and 'handle_autonomous_posting' in globals():
        click.echo("\nProcessing autonomous posting for new videos...")
        for video in newly_added_videos:
            click.echo(f"Processing autonomous posting for video: {video.title}")
            handle_autonomous_posting(video) 
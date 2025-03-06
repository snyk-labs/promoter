import os
from openai import OpenAI
from contextlib import contextmanager
from datetime import datetime
import logging
from enum import Enum, auto

# Initialize the client once
client = OpenAI()

# Define character limits for different platforms
TWITTER_CHAR_LIMIT = 280
LINKEDIN_CHAR_LIMIT = 3000
URL_CHAR_APPROX = 30

# Define social platform types
class SocialPlatform(Enum):
    TWITTER = auto()
    LINKEDIN = auto()
    GENERIC = auto()  # For web UI when platform is unknown

# Define content types
class ContentType(Enum):
    PODCAST = auto()
    VIDEO = auto()
    BLOG = auto()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_platform_config(platform):
    """Get the configuration for a specific social platform."""
    if platform == SocialPlatform.TWITTER:
        return {
            "name": "Twitter/X",
            "char_limit": TWITTER_CHAR_LIMIT,
            "content_limit": TWITTER_CHAR_LIMIT - URL_CHAR_APPROX,
            "style": "concise, engaging, to the point"
        }
    elif platform == SocialPlatform.LINKEDIN:
        return {
            "name": "LinkedIn",
            "char_limit": LINKEDIN_CHAR_LIMIT,
            "content_limit": 1000,  # Although LinkedIn allows 3000, we want to keep it reasonably short
            "style": "professional, slightly more detailed, includes insights"
        }
    else:  # GENERIC - conservative approach for web UI
        return {
            "name": "Generic (Twitter-compatible)",
            "char_limit": TWITTER_CHAR_LIMIT,
            "content_limit": TWITTER_CHAR_LIMIT - URL_CHAR_APPROX,
            "style": "concise, engaging, works on all platforms"
        }

def detect_content_type(content_item):
    """Detect the type of content being promoted."""
    from models import Episode, Post, Video
    
    if isinstance(content_item, Episode):
        return ContentType.PODCAST
    elif isinstance(content_item, Video):
        return ContentType.VIDEO
    elif isinstance(content_item, Post):
        return ContentType.BLOG
    else:
        # Default to podcast if we can't determine
        return ContentType.PODCAST

def generate_social_post(content_item, user, platform=SocialPlatform.GENERIC, max_retries=3):
    """
    Generate a social media post for various content types.
    
    Args:
        content_item: The content object (Episode, Video, or Blog Post)
        user: The user object with profile info
        platform: The social platform to generate content for (determines character limits)
        max_retries: Maximum number of retries for content generation
        
    Returns:
        A string containing the generated social post
        
    Raises:
        Exception: If post generation fails after max_retries
    """
    
    # Get platform-specific configuration
    platform_config = get_platform_config(platform)
    
    # Detect content type
    content_type = detect_content_type(content_item)
    
    # Calculate how long ago the content was published
    now = datetime.utcnow()
    time_diff = now - content_item.publish_date
    days_ago = time_diff.days
    
    # Create a human-readable time description
    if days_ago == 0:
        time_context = "just released today"
    elif days_ago == 1:
        time_context = "released yesterday"
    elif days_ago < 7:
        time_context = f"released {days_ago} days ago"
    elif days_ago < 14:
        time_context = "released last week"
    elif days_ago < 30:
        time_context = "released a few weeks ago"
    elif days_ago < 60:
        time_context = "released last month"
    else:
        time_context = f"from {content_item.publish_date.strftime('%B %Y')}"
    
    # Track retries
    attempts = 0
    post = None
    last_error = None
    last_length = 0
    
    # Set content-specific variables
    if content_type == ContentType.PODCAST:
        content_type_name = "podcast episode"
        url_field = content_item.player_url
        content_description = f"Episode {content_item.episode_number}: {content_item.title}"
    elif content_type == ContentType.VIDEO:
        content_type_name = "YouTube video"
        url_field = content_item.url
        content_description = content_item.title
    elif content_type == ContentType.BLOG:
        content_type_name = "blog post"
        url_field = content_item.url
        content_description = content_item.title
    
    # Base system message with platform-specific and content-type-specific details
    system_message = f"""You are an expert social media manager who creates engaging, professional posts about {content_type_name}s for {platform_config['name']}.
Your goal is to maximize engagement while being informative. Focus on the value and insights that would interest security professionals and developers.

CRITICAL LENGTH REQUIREMENT:
The TOTAL post length (including the URL that will be added at the end) MUST be {platform_config['char_limit']} characters or less.
The URL will take up approximately {URL_CHAR_APPROX} characters, so your generated text must be {platform_config['content_limit']} characters or less to leave room for the URL.

Post Style: {platform_config['style']}
"""

    # Add content-type specific messaging
    if content_type == ContentType.PODCAST:
        system_message += """
Podcast Promotion Style:
- Focus on valuable insights and key points covered in the episode
- Mention key takeaways that would make someone want to listen
- Use an authoritative but friendly tone
- Avoid overly salesy language, focus on educational value"""
    elif content_type == ContentType.VIDEO:
        system_message += """
Video Promotion Style:
- Be more casual and visually descriptive
- Emphasize the visual/demo aspects of the video 
- Use action-oriented language that creates curiosity
- Make it sound exciting and worth watching
- If appropriate, use emoji sparingly for visual appeal
- Mention what viewers will learn or see demonstrated"""
    elif content_type == ContentType.BLOG:
        system_message += """
Blog Post Promotion Style:
- Focus on the educational aspects and key insights
- Emphasize any statistics, research findings, or actionable tips
- Use a more thoughtful, analytical tone
- Highlight the expertise demonstrated in the article
- For technical posts, mention technologies or techniques covered"""

        # Add author guidance to system message for blog posts
        if hasattr(content_item, 'author') and content_item.author:
            system_message += f"""
- The blog post was written by {content_item.author} - you may mention the author if it adds value"""
        else:
            system_message += """
- DO NOT mention or refer to any blog author as this information is not available"""

    system_message += f"""
Critical requirements for every post:
1. Keep total length under {platform_config['char_limit']} characters INCLUDING the URL
2. Keep the tone authentic, not overly marketing-focused
3. Focus on the key insights or value proposition
4. Make every word count"""
    
    # Base user message template, adjusted for platform and content type
    user_message_template = f"""Create an engaging {platform_config['name']} post about this {content_type_name}. 
The TOTAL post (including the URL) MUST be {platform_config['char_limit']} characters or less.

Content Details:
- Title: {{title}}
- Description: {{description}}
- URL: {{url}}
- Timing: {{timing}}

Person authoring this social post: {{name}}
Background: {{bio}}

Key Requirements:
1. STRICT LIMIT: Your text must be {platform_config['content_limit']} characters or less to leave room for the URL
2. Must end with: {{url}}
3. Use timing ("{{timing}}") if it adds value
4. Focus on the key insights or value proposition
5. If the promoter's expertise relates to the topic, incorporate it naturally"""

    # Add content-type specific guidance
    if content_type == ContentType.PODCAST:
        user_message_template += """
6. NEVER mention the episode number
7. Communicate what listeners will learn"""
    elif content_type == ContentType.VIDEO:
        user_message_template += """
6. Create curiosity about what's shown in the video
7. Use more visual and action-oriented language"""
    elif content_type == ContentType.BLOG:
        user_message_template += """
6. Emphasize the educational value or key insights
7. Highlight any unique perspectives or research findings"""
        
        # Add blog-specific author handling
        if hasattr(content_item, 'author') and content_item.author:
            user_message_template += """
8. You can mention the blog author: "{blog_author}" if it adds value to the post"""
        else:
            user_message_template += """
8. DO NOT refer to or mention any blog author since that information is not available"""

    user_message_template += f"""

For LinkedIn: If generating LinkedIn content, you can include more detail and professional insights.
For Twitter: If generating Twitter content, be extremely concise and engaging.

Remember: The URL counts toward the {platform_config['char_limit']} character limit! Keep your content appropriate for the platform."""
    
    while attempts < max_retries:
        attempts += 1
        
        # If this is a retry, strengthen the message about length constraints
        if attempts > 1:
            system_message += f"""

PREVIOUS ATTEMPT FAILED: The content was too long ({last_length} characters).
YOU MUST KEEP THE CONTENT UNDER {platform_config['content_limit']} CHARACTERS EXCLUDING THE URL, which is {URL_CHAR_APPROX} characters.
The total MUST be less than {platform_config['char_limit']} characters. Be extremely concise!"""
        
        try:
            description = getattr(content_item, 'description', '')
            # For videos and blog posts that have excerpts, use that instead when available
            if content_type in [ContentType.VIDEO, ContentType.BLOG] and hasattr(content_item, 'excerpt') and content_item.excerpt:
                description = content_item.excerpt
            
            # Create formatting parameters
            format_params = {
                'title': content_item.title,
                'description': description,
                'url': url_field,
                'timing': time_context,
                'name': user.name,
                'bio': user.bio or 'No background information provided'
            }
            
            # Add blog author if available (for blog posts only)
            if content_type == ContentType.BLOG and hasattr(content_item, 'author') and content_item.author:
                format_params['blog_author'] = content_item.author
            
            user_message = user_message_template.format(**format_params)
            
            completion = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Get the generated content
            post = completion.choices[0].message.content.strip()
            
            # Validate the post length is within platform's character limit
            # First, check if the URL is already in the post
            if url_field in post:
                total_length = len(post)
            else:
                # If not, we'll need to add it
                total_length = len(post) + len(url_field) + 1  # +1 for a space
            
            # Log the post details
            logger.info(f"Generated {platform_config['name']} post (attempt {attempts}): {total_length} characters")
            
            # If within limits, return the post
            if total_length <= platform_config['char_limit']:
                # Make sure the URL is at the end if not already included
                if url_field not in post:
                    post = f"{post} {url_field}"
                return post
            
            # If we get here, the post is too long
            last_length = total_length
            logger.warning(f"Generated {platform_config['name']} post too long: {total_length} characters (max: {platform_config['char_limit']})")
            
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error generating {platform_config['name']} post (attempt {attempts}): {last_error}")
    
    # If we've reached max retries, provide a minimal fallback post or raise an exception
    if post and last_length > platform_config['char_limit']:
        # Attempt to truncate the post as a last resort
        truncation_limit = platform_config['content_limit'] - 3  # -3 for the ellipsis
        truncated_text = post[:truncation_limit].strip() + "..."
        fallback_post = f"{truncated_text} {url_field}"
        logger.warning(f"Used truncated fallback {platform_config['name']} post: {len(fallback_post)} characters")
        return fallback_post
    
    # If we have no post at all, create a minimal fallback
    if not post:
        fallback_post = f"Check out this {content_type_name} {time_context}: {url_field}"
        logger.warning(f"Used minimal fallback {platform_config['name']} post: {len(fallback_post)} characters")
        return fallback_post
        
    # This shouldn't happen with the fallbacks above, but just in case
    raise Exception(f"Failed to generate valid {platform_config['name']} post after {max_retries} attempts: {last_error}")

def generate_platform_specific_posts(content_item, user, max_retries=3):
    """
    Generate platform-specific social media posts for content items.
    
    Args:
        content_item: The content object (Episode, Video, or Blog Post)
        user: The user object with profile info
        max_retries: Maximum number of retries for content generation
        
    Returns:
        A dictionary containing posts for each platform
    """
    posts = {}
    
    # Generate Twitter post
    if user.x_authorized:
        try:
            posts['twitter'] = generate_social_post(
                content_item, 
                user, 
                platform=SocialPlatform.TWITTER, 
                max_retries=max_retries
            )
        except Exception as e:
            logger.error(f"Failed to generate Twitter post: {str(e)}")
            posts['twitter'] = None
    
    # Generate LinkedIn post
    if user.linkedin_authorized:
        try:
            posts['linkedin'] = generate_social_post(
                content_item, 
                user, 
                platform=SocialPlatform.LINKEDIN, 
                max_retries=max_retries
            )
        except Exception as e:
            logger.error(f"Failed to generate LinkedIn post: {str(e)}")
            posts['linkedin'] = None
    
    return posts

def validate_post_length(post, platform=SocialPlatform.GENERIC, url=None):
    """
    Validate if a post is within platform character limits.
    
    Args:
        post: The post content
        platform: The social platform to validate against
        url: Optional URL to be added to the post if not already included
        
    Returns:
        Tuple of (is_valid_for_twitter, is_valid_for_linkedin, total_length)
    """
    total_length = len(post)
    
    # If URL needs to be added and isn't already in the post
    if url and url not in post:
        total_length += len(url) + 1  # +1 for space
    
    twitter_config = get_platform_config(SocialPlatform.TWITTER)
    linkedin_config = get_platform_config(SocialPlatform.LINKEDIN)
    
    is_valid_for_twitter = total_length <= twitter_config['char_limit']
    is_valid_for_linkedin = total_length <= linkedin_config['char_limit']
    
    return is_valid_for_twitter, is_valid_for_linkedin, total_length 
# Promoter

A Flask web application designed to help automate social media promotion for your content. This tool automatically syncs with podcast, blog, and YouTube RSS feeds, providing an interface for company employees to easily share new content on social media.

## Features

- Automatic content syncing from RSS feeds (podcasts, blogs, and YouTube videos)
- Clean, modern web interface for viewing content
- Items displayed with title, description, and publication date
- Direct links to original content
- Social media promotion capabilities (coming soon)

## Prerequisites

- Python 3.12 or newer
- pip (Python package installer)
- Virtual environment tool (venv)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Create a virtual environment:
```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
# First, set the Flask application
export FLASK_APP=app.py  # On Windows: set FLASK_APP=app.py

# Then create the database tables
flask init-db
```

## Usage

### Running the Web Application

1. Start the Flask development server:
```bash
python app.py
```

2. Open your browser and visit: http://localhost:5000

### Syncing Content from RSS Feeds

The application includes CLI commands to sync content from RSS feeds. You can run these manually or set them up as scheduled tasks.

#### Syncing Podcast Episodes

To sync podcast episodes manually:

```bash
# First, ensure you're in your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Set the Flask application
export FLASK_APP=app.py  # On Windows: set FLASK_APP=app.py

# Run the sync command with your podcast's RSS feed URL
flask sync-podcast "YOUR_PODCAST_RSS_URL"

# For example, for The Secure Developer podcast:
flask sync-podcast "https://feeds.simplecast.com/47yfLpm0"
```

#### Syncing Blog Posts

To sync blog posts manually:

```bash
# First, ensure you're in your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Set the Flask application
export FLASK_APP=app.py  # On Windows: set FLASK_APP=app.py

# Run the sync command with your blog's RSS feed URL
flask sync-blog "YOUR_BLOG_RSS_URL"

# For example, for the Snyk blog:
flask sync-blog "https://snyk.io/blog/feed.xml"
```

#### Syncing YouTube Videos

To sync YouTube videos manually:

```bash
# First, ensure you're in your virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Set the Flask application
export FLASK_APP=app.py  # On Windows: set FLASK_APP=app.py

# Run the sync command with your YouTube channel's RSS feed URL
flask sync-youtube "YOUR_YOUTUBE_CHANNEL_RSS_URL"

# For example:
flask sync-youtube "https://www.youtube.com/feeds/videos.xml?channel_id=UCh4dJzctb0NhSibjU-e2P6w"
```

### Automating Content Updates

To automatically sync new episodes, you can set up a cron job (on Unix-based systems) or a scheduled task (on Windows).

#### Unix/Linux Cron Job

1. Create a shell script named `sync_episodes.sh`:
```bash
#!/bin/bash
cd /path/to/your/promoter
source venv/bin/activate
export FLASK_APP=app.py
flask sync-podcast "YOUR_PODCAST_RSS_URL"
```

2. Make it executable:
```bash
chmod +x sync_episodes.sh
```

3. Add to crontab (runs every hour):
```bash
0 * * * * /path/to/your/sync_episodes.sh
```

#### Windows Scheduled Task

1. Create a batch file named `sync_episodes.bat`:
```batch
cd C:\path\to\your\promoter
call venv\Scripts\activate
set FLASK_APP=app.py
flask sync-podcast "YOUR_PODCAST_RSS_URL"
```

2. Use Windows Task Scheduler to run this batch file on your desired schedule.

## Database

The application supports both SQLite (default for development) and PostgreSQL (recommended for production) databases.

### Database Configuration

By default, SQLite is used in development mode with the database file stored at `promoter.db`. 

You can customize the database configuration using the `DATABASE_URL` environment variable:

```bash
# PostgreSQL configuration (recommended for production)
export DATABASE_URL="postgresql://username:password@localhost:5432/promoter"

# Custom SQLite database path
export DATABASE_URL="sqlite:///path/to/your/custom.db"
```

### Database Initialization

To initialize the database for the first time:

```bash
# Set the Flask application
export FLASK_APP=app.py  # On Windows: set FLASK_APP=app.py

# Create the database tables
flask init-db
```

For PostgreSQL, make sure the database exists before running `init-db`.

### Database Migrations

When you make changes to database models, you'll need to create and apply migrations:

```bash
# Create a migration after changing models
flask db migrate -m "Description of your changes"

# Apply pending migrations
flask db upgrade
```

### Migration Management

Other useful migration commands:

```bash
# Show current migration status
flask db current

# Roll back the last migration
flask db downgrade

# Show migration history
flask db history
```

## Deployment

This section provides instructions for deploying the application to Heroku, a popular cloud platform.

### Deploying to Heroku

#### Prerequisites

- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
- [Git](https://git-scm.com/) installed
- Heroku account

#### Setup Steps

1. **Login to Heroku**

   ```bash
   heroku login
   ```

2. **Create a new Heroku application**

   ```bash
   heroku create your-app-name
   ```

3. **Add Heroku PostgreSQL add-on**

   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

   This will provision a PostgreSQL database and set the `DATABASE_URL` environment variable automatically.

4. **Set required environment variables**

   ```bash
   # Set a secure random secret key
   heroku config:set SECRET_KEY=$(openssl rand -hex 32)
   
   # Set OpenAI API key
   heroku config:set OPENAI_API_KEY=your-openai-api-key
   
   # Set Arcade API key if using social media posting
   heroku config:set ARCADE_API_KEY=your-arcade-api-key
   ```

5. **Create a Procfile**

   Create a file named `Procfile` (no extension) in the root directory with the following content:

   ```
   web: gunicorn "app:create_app()"
   release: FLASK_APP=app.py flask db upgrade
   ```

   This tells Heroku how to run your application and to run database migrations automatically on each deploy.

6. **Add Gunicorn to requirements.txt**

   Ensure `gunicorn` is in your requirements.txt file:

   ```
   gunicorn>=21.2.0
   ```

7. **Deploy to Heroku**

   ```bash
   git add .
   git commit -m "Prepare for Heroku deployment"
   git push heroku main
   ```

8. **Initialize the database (first deployment only)**

   After the first deployment, you may need to initialize the database manually:

   ```bash
   heroku run "FLASK_APP=app.py flask db upgrade"
   ```

9. **Set up scheduled content syncing**

   To schedule regular content updates, use the Heroku Scheduler add-on:

   ```bash
   heroku addons:create scheduler:standard
   ```

   Then open the scheduler dashboard:

   ```bash
   heroku addons:open scheduler
   ```

   Add the following jobs:

   - For podcast syncing: `FLASK_APP=app.py flask sync-podcast "YOUR_PODCAST_RSS_URL"`
   - For blog syncing: `FLASK_APP=app.py flask sync-blog "YOUR_BLOG_RSS_URL"`
   - For YouTube syncing: `FLASK_APP=app.py flask sync-youtube "YOUR_YOUTUBE_CHANNEL_ID"`

10. **Open your application**

    ```bash
    heroku open
    ```

### Setting Up Okta SSO with Heroku

#### Creating an Okta Application

1. **Sign in to your Okta Developer Console**

   Go to https://developer.okta.com/ and sign in to your account.

2. **Create a new application**

   - Click on "Applications" in the top menu
   - Click "Create App Integration"
   - Select "OIDC - OpenID Connect" as the sign-in method
   - Select "Web Application" as the application type
   - Click "Next"

3. **Configure the application**

   - Name: Enter a name for your application (e.g., "Promoter")
   - Logo (optional): Upload your application logo
   - Sign-in redirect URIs: `https://your-app-name.herokuapp.com/auth/okta/callback`
   - Sign-out redirect URIs: `https://your-app-name.herokuapp.com`
   - Assignments:
     - Select "Allow everyone in your organization to access" for all employees, or
     - Select "Limit access to selected groups" to restrict access

4. **Save the application**

   After saving, Okta will provide you with:
   - Client ID
   - Client Secret
   - Okta Domain
   
   Save these for the next step.

#### Configuring Okta with Heroku

1. **Set Okta environment variables**

   ```bash
   # Enable Okta SSO
   heroku config:set OKTA_ENABLED=true
   
   # Okta application credentials
   heroku config:set OKTA_CLIENT_ID=your-client-id
   heroku config:set OKTA_CLIENT_SECRET=your-client-secret
   
   # Okta domain with authorization server path
   # Format: https://your-okta-domain.okta.com/oauth2/default
   heroku config:set OKTA_ISSUER=https://your-okta-domain.okta.com/oauth2/default
   
   # Redirect URI (must match what you set in Okta)
   heroku config:set OKTA_REDIRECT_URI=https://your-app-name.herokuapp.com/auth/okta/callback
   ```

2. **Deploy the changes**

   ```bash
   git push heroku main
   ```

3. **Test Okta SSO**

   Visit your application and click on the "Sign in with Company SSO" button to test the Okta integration.

#### Troubleshooting Okta SSO

If you encounter issues with Okta SSO:

1. **Check environment variables**

   Ensure all Okta environment variables are set correctly:
   
   ```bash
   heroku config:get OKTA_CLIENT_ID
   heroku config:get OKTA_ISSUER
   heroku config:get OKTA_REDIRECT_URI
   ```

2. **Check Okta application settings**

   - Verify that the redirect URIs match exactly
   - Ensure the application is assigned to the appropriate users or groups
   - Check if the authorization server in the issuer URL is correct

3. **Check Heroku logs**

   ```bash
   heroku logs --tail
   ```

4. **Update callback URL in Okta**

   If your Heroku app URL changes, remember to update the callback URL in your Okta application settings.

## Development

- The main application logic is in `app.py`
- Database models are defined in `models.py`
- CLI commands are in `cli.py`
- HTML templates are in the `templates` directory

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 
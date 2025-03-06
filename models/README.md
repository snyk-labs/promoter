# Models Package

This package contains all database models for the application, organized into separate files for better maintainability.

## Package Structure

- `__init__.py` - Package initialization that imports and exports all models
- `user.py` - User model for authentication and profile data
- `episode.py` - Podcast episode model
- `post.py` - Blog post model
- `video.py` - YouTube video model

## Usage

Models can be imported directly from the package:

```python
from models import User, Episode, Post, Video

# Or import specific models
from models.user import User
```

## Model Relationships

Currently, the models are independent and don't have direct database relationships.

## Adding New Models

To add a new model:

1. Create a new file in the `models` directory (e.g., `models/new_model.py`)
2. Define your model class in that file
3. Import the model in `__init__.py` and add it to the `__all__` list
4. Run database migrations to create the new table 
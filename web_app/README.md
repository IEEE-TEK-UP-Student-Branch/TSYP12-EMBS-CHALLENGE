# Mental Health AI Web Application

A modern web application for mental health support powered by AI.

## Features

- User authentication and authorization
- Personal dashboard
- Chat interface with AI
- User onboarding
- Modern, responsive UI using HTMX and TailwindCSS

## Tech Stack

- Backend: Django 5.0
- Frontend: HTMX + TailwindCSS
- Database: SQLite (development) / PostgreSQL (production)
- Authentication: Django built-in auth with Argon2 password hashing

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Start the development server:
```bash
python manage.py runserver
```

## Development

- The project uses HTMX for dynamic interactions
- TailwindCSS for styling
- Django templates for server-side rendering

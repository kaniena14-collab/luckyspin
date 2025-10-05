# Overview

The Lucky Spin Wheel is a web-based prize wheel application built with Flask. Users enter voucher codes to spin a customizable wheel and win prizes. The system includes an admin panel for managing prizes, vouchers, and wheel appearance settings. The application features real-time wheel animations, file upload capabilities for prize icons and branding, and a complete voucher-based access control system.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with Bootstrap 5 dark theme for responsive UI
- **JavaScript Components**: Custom SpinWheel class for canvas-based wheel rendering and animations
- **Styling**: Bootstrap CSS framework with custom CSS for wheel animations and glow effects
- **File Structure**: Modular template inheritance with base template and specialized admin templates

## Backend Architecture
- **Framework**: Flask web framework with SQLAlchemy ORM
- **Application Structure**: 
  - `app.py`: Application factory and configuration
  - `main.py`: Entry point and application runner
  - `routes.py`: Request handlers and API endpoints
  - `models.py`: Database models and business logic
- **Authentication**: Session-based admin authentication with password hashing
- **File Handling**: Image upload processing with PIL for resizing and optimization

## Database Design
- **ORM**: SQLAlchemy with declarative base model
- **Models**:
  - `Admin`: User authentication and management
  - `Prize`: Prize definitions with probability weights and icon storage
  - `Voucher`: Access control with unique codes and usage tracking
  - `WheelSettings`: Customization settings for appearance
  - `SpinResult`: Audit trail of spin outcomes
- **Database Support**: Configurable between SQLite (default) and PostgreSQL via environment variables

## File Management
- **Upload System**: Secure file upload with extension validation and size limits (16MB)
- **Image Processing**: Automatic resizing using PIL with thumbnail generation
- **Storage**: Local filesystem storage in uploads directory with secure filename handling

## Security Features
- **Admin Authentication**: Password hashing using Werkzeug security utilities
- **Session Management**: Flask sessions with configurable secret keys
- **File Upload Security**: Filename sanitization and extension validation
- **CSRF Protection**: Built into form handling patterns

# External Dependencies

## Core Framework Dependencies
- **Flask**: Web framework and routing
- **SQLAlchemy**: Database ORM and migrations
- **Werkzeug**: WSGI utilities, security, and file handling
- **Jinja2**: Template rendering (included with Flask)

## Frontend Libraries
- **Bootstrap 5**: CSS framework loaded from CDN (Replit Agent dark theme)
- **Font Awesome 6.4.0**: Icon library loaded from CDN
- **Custom JavaScript**: Canvas-based wheel animation system

## Image Processing
- **Pillow (PIL)**: Image manipulation, resizing, and format conversion

## Production Considerations
- **ProxyFix Middleware**: Configured for deployment behind reverse proxies
- **Database Pooling**: Connection pool settings for production databases
- **Environment Configuration**: Database URLs and secret keys via environment variables

## Optional Integrations
- **PostgreSQL**: Production database option (configured via DATABASE_URL)
- **Static File Serving**: Currently handled by Flask, can be moved to nginx/Apache in production
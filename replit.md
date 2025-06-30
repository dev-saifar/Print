# Print Management Software Platform

## Overview

This is a full-stack Print Management Software platform (similar to MyQ X or PaperCut) built with Python Flask and SQLite. The system provides secure print management, user authentication, job tracking, and cost control features through a responsive Bootstrap UI.

## System Architecture

### Backend Architecture
- **Framework**: Python Flask web framework
- **Database**: SQLite with SQLAlchemy ORM for data persistence
- **Authentication**: Flask-Login with password hashing via Werkzeug
- **File Processing**: PyPDF2 for PDF page counting, PIL for image processing
- **Job Scheduling**: APScheduler for background print job processing
- **Session Management**: Flask sessions with configurable secret keys

### Frontend Architecture
- **UI Framework**: Bootstrap 5 with dark theme support
- **Icons**: Bootstrap Icons for consistent iconography
- **Charts**: Chart.js for analytics and reporting visualizations
- **Responsive Design**: Mobile-first responsive layout
- **JavaScript**: Vanilla JS for form validation and dynamic interactions

### Database Schema
- **Users**: Authentication, roles (user/admin), quotas, balances, department associations
- **Print Jobs**: File metadata, print settings, status tracking, cost calculations
- **Departments**: Organizational structure with cost centers
- **System Settings**: Configurable application parameters

## Key Components

### Authentication & Access Control
- Secure user registration and login system
- Role-based access control (user/admin)
- Session management with Flask-Login
- User quotas and balance tracking
- Department-based user organization

### Print Job Management
- File upload with validation (PDF, DOC, images, TXT)
- Print settings: copies, color mode, paper size, duplex options
- Cost calculation based on pages and settings
- Job status tracking (pending, printing, completed, failed, cancelled)
- Background job processing with APScheduler

### File Processing
- Multi-format document support
- Automatic page counting for cost estimation
- File size validation (16MB limit)
- Secure file storage in uploads directory

### User Interface
- Dashboard with usage statistics and quick actions
- Job history and status tracking
- Admin panel for user and system management
- Responsive design for desktop and mobile access
- Real-time status updates for active jobs

## Data Flow

1. **User Registration/Login**: Users create accounts or authenticate through the login system
2. **File Upload**: Users upload documents through the web interface with print settings
3. **Job Processing**: System validates files, calculates costs, and creates print jobs
4. **Background Processing**: APScheduler handles job status updates and simulated printing
5. **Status Updates**: Users can monitor job progress through the dashboard and jobs page
6. **Reporting**: System tracks usage statistics and generates reports for users and admins

## External Dependencies

### Python Packages
- Flask: Web framework
- Flask-SQLAlchemy: Database ORM
- Flask-Login: User session management
- Werkzeug: Security utilities and file handling
- PyPDF2: PDF processing
- Pillow (PIL): Image processing
- APScheduler: Background job scheduling

### Frontend Libraries
- Bootstrap 5: UI framework and components
- Bootstrap Icons: Icon library
- Chart.js: Data visualization for reports
- Custom CSS: Additional styling and theming

### File System
- SQLite database file (printmanager.db)
- Uploads directory for document storage
- Static assets (CSS, JavaScript)
- HTML templates with Jinja2 templating

## Deployment Strategy

### Development Environment
- Flask development server with debug mode
- SQLite database for development
- Local file storage for uploads
- Hot reloading for template and code changes

### Production Considerations
- WSGI server deployment (Gunicorn, uWSGI)
- Reverse proxy setup (Nginx, Apache)
- Secure session secret configuration
- File upload security measures
- Database connection pooling
- Background job worker processes

### Configuration
- Environment-based configuration for secrets
- Configurable upload limits and allowed file types
- Database connection settings with pooling options
- Proxy configuration for deployment behind load balancers

## Changelog
- June 30, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.
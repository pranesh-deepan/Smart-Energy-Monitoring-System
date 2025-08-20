# Electricity Management - Track Real-time Data

A web application to monitor and manage electricity usage in real-time, track device consumption, and generate electricity bills. Provides dashboards for users to visualize usage, manage devices, and receive billing notifications.

## Features
- Real-time electricity usage monitoring
- Device management (add, edit, remove devices)
- Electricity bill calculation and tracking
- Usage dashboards and analytics
- Email notifications for bills
- User authentication and profiles

## Setup
1. Create a virtual environment
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables
   - Copy `.env.example` to `.env` (if available) or create `.env`
   - Set `SECRET_KEY` and other relevant variables
4. Initialize the database (if using Flask-Migrate)
   ```bash
   flask db upgrade
   ```
5. Run the application
   ```bash
   python run.py
   ```
   or
   ```bash
   flask run
   ```
   > **Note:** For this project, running `python run.py` is recommended. If you use `flask run`, ensure your environment variable `FLASK_APP` is set to `run.py`.

The app will be available at http://localhost:5000

## Usage
- Access the dashboard to view real-time electricity usage and analytics
- Manage devices via the Devices page
- View and pay electricity bills from the Bills page
- Receive notifications via email for new bills

## Customization
- Update `models.py` to change device or bill fields
- Edit templates in the `templates/` directory for UI changes
- Modify logic in `routes.py` for new features

## Security
- Passwords are securely hashed (bcrypt)
- CSRF protection enabled
- User sessions are managed securely
- Sensitive data is stored in environment variables

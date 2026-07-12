# AI-Based School Portal System

A secure, scalable school management platform built with Django to bring student, teacher, and administrative data into one centralized system — enhanced with an AI-powered Smart Result Analysis module that turns raw academic data into actionable insight.



**Overview**

Traditional school record-keeping is often scattered across paper files and disconnected spreadsheets. This project replaces that with a single, secure, role-based web platform where administrators, teachers, and students each get a view tailored to their needs — and where student performance data is actively analyzed rather than just stored.

##  Features

- **Role-Based Access Control (RBAC)** — Separate, permission-scoped views for admins, teachers, Parent and students so each user only sees what's relevant to them.
- **Student, Teacher, Parent & Admin Management** — Centralized handling of academic and administrative records.
- **Smart Result Analysis (AI-Powered)** — Analyzes student performance data and generates personalized academic suggestions, helping teachers and parents identify at-risk students early.
- **Responsive UI** — Built with HTML, CSS, JavaScript, and Bootstrap for a clean experience across devices.
- **Secure & Scalable Backend** — Powered by Django, designed to handle growing volumes of student and academic data reliably.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django (Python) |
| Frontend | HTML, CSS, JavaScript, Bootstrap |
| Database | SQLite3 |
| AI/Analytics | Python-based ML pipeline for result analysis |

##  Getting Started

### Prerequisites
- Python 3.9+
- pip


### Installation

```bash
# Clone the repository
git clone https://github.com/somtharu181-coder/ai-school-portal-system.git
cd ai-school-portal-system

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your database in settings.py, then run migrations
python manage.py migrate

# Create a superuser (admin account)
python manage.py createsuperuser

# Run the development server
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` in your browser to access the portal.

##  Usage

1. Log in with the appropriate role (Admin, Teacher, or Student).
2. Admins manage school-wide records and user accounts.
3. Teachers view and update their students' academic data.
4. Students view their own performance and recommendations.
5. The Smart Result Analysis module automatically processes performance data and surfaces personalized suggestions on the relevant dashboards.

##  Smart Result Analysis

Instead of only displaying grades, this module interprets performance data to:
- Highlight patterns in individual student performance
- Flag students who may need additional academic support
- Generate personalized, actionable suggestions for teachers and parents

This shifts the platform from a passive record-keeping tool into a proactive academic support system.

##  Project Structure

ai-school-portal-system/
├── manage.py
├── requirements.txt
├── scholaro/               # Project settings (core Django project)
├── account/                # Authentication & role-based access
├── student/                # Student records & dashboards
├── staff/                  # Staff/teacher records & dashboards
├── parent/                 # Parent portal & dashboards
├── academic/               # Classes, subjects, curriculum management
├── assignment/             # Assignment creation, submission & tracking
├── attendance/             # Attendance tracking & records
├── quiz/                   # Quiz creation & assessment
├── analytics/              # Smart Result Analysis (AI/ML) module
├── reporting_system/       # Report generation & export
├── notification/           # Alerts & notifications
├── audit_log/              # System activity & audit tracking
├── static/                 # CSS, JS, images
└── templates/              # HTML templates

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to open an issue or submit a pull request.

##  License

This project is licensed under the MIT License.

##  Contact

**Som Narayan Tharu**
- Email: somtharu181@gmail.com
- GitHub: [somtharu181-coder](https://github.com/somtharu181-coder)
- LinkedIn: [som-narayan-tharu](https://linkedin.com/in/som-narayan-tharu-58420b320)

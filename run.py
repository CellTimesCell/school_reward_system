from app import create_app, db
from app.models import User, PointTransaction, School
import os
from werkzeug.security import generate_password_hash
from datetime import datetime
from flask import render_template, redirect, url_for
from flask_login import current_user

app = create_app()


def init_db():
    """Creates tables and adds test data"""
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

        # Check if data already exists
        if User.query.count() == 0:
            print("Creating test data...")

            # Create school
            school = School.query.first()
            if school is None:
                school = School(
                    name='Hill PK-8',
                    logo_url='/static/img/logo.png'
                )
                db.session.add(school)

            # Create admin
            admin = User.query.filter_by(username='admin').first()
            if admin is None:
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    first_name='Admin',
                    last_name='User',
                    role='admin'
                )
                admin.set_password('admin123')
                db.session.add(admin)

            # Create teachers
            teacher1 = User.query.filter_by(username='teacher1').first()
            if teacher1 is None:
                teacher1 = User(
                    username='teacher1',
                    email='teacher1@example.com',
                    first_name='Ivan',
                    last_name='Gonzales',
                    role='teacher'
                )
                teacher1.set_password('teacher123')
                db.session.add(teacher1)

            teacher2 = User.query.filter_by(username='teacher2').first()
            if teacher2 is None:
                teacher2 = User(
                    username='teacher2',
                    email='teacher2@example.com',
                    first_name='Maria',
                    last_name='Martinez',
                    role='teacher'
                )
                teacher2.set_password('teacher123')
                db.session.add(teacher2)

            # Create students
            student1 = User.query.filter_by(username='student1').first()
            if student1 is None:
                student1 = User(
                    username='student1',
                    email='student1@example.com',
                    first_name='Brad',
                    last_name='Blackwood',
                    role='student'
                )
                student1.set_password('student123')
                db.session.add(student1)

            student2 = User.query.filter_by(username='student2').first()
            if student2 is None:
                student2 = User(
                    username='student2',
                    email='student2@example.com',
                    first_name='Anna',
                    last_name='Smith',
                    role='student'
                )
                student2.set_password('student123')
                db.session.add(student2)

            db.session.commit()

            # Now create transactions after commit to have user IDs
            teacher1 = User.query.filter_by(username='teacher1').first()
            teacher2 = User.query.filter_by(username='teacher2').first()
            student1 = User.query.filter_by(username='student1').first()
            student2 = User.query.filter_by(username='student2').first()

            if PointTransaction.query.count() == 0 and teacher1 and teacher2 and student1 and student2:
                # Create test transactions
                transactions = [
                    PointTransaction(
                        student_id=student1.id,
                        teacher_id=teacher1.id,
                        points=10,
                        description='For excellent homework completion'
                    ),
                    PointTransaction(
                        student_id=student1.id,
                        teacher_id=teacher2.id,
                        points=5,
                        description='For active participation in class'
                    ),
                    PointTransaction(
                        student_id=student2.id,
                        teacher_id=teacher1.id,
                        points=15,
                        description='For winning the school olympiad'
                    )
                ]

                for transaction in transactions:
                    db.session.add(transaction)

                db.session.commit()

            print("Test data created successfully!")


# Create directory for error templates if it doesn't exist
def ensure_error_templates():
    templates_dir = os.path.join('app', 'templates', 'errors')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir, exist_ok=True)

        # Create basic templates for errors
        for error_code in [404, 500, 429]:
            template_path = os.path.join(templates_dir, f'{error_code}.html')
            if not os.path.exists(template_path):
                with open(template_path, 'w') as f:
                    template_content = '''{% extends "base.html" %}

{% block full_content %}
<div class="row justify-content-center">
    <div class="col-md-8 col-lg-6">
        <div class="card mt-5">
            <div class="card-body text-center py-5">
                <h1 class="display-1 text-muted">{}</h1>
                <i class="fas fa-exclamation-triangle fa-5x text-danger mb-4"></i>
                <h2 class="mb-4">Error</h2>
                <p class="lead">An error occurred while processing your request.</p>
                <a href="{{ url_for('auth.index') }}" class="btn btn-primary mt-3">
                    <i class="fas fa-home me-2"></i> Return to home page
                </a>
            </div>
        </div>
    </div>
</div>
{% endblock %}'''
                    f.write(template_content.format(error_code))

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'PointTransaction': PointTransaction,
        'School': School
    }


@app.route('/')
def home():
    # Если пользователь уже авторизован, перенаправляем на соответствующую панель
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))

    # Иначе показываем приветственную страницу
    return render_template('home.html', title='Welcome to School Points System')

# If run directly through PyCharm
if __name__ == '__main__':
    # Create necessary directories for templates
    ensure_error_templates()

    # Initialize the database
    init_db()

    # Run the application
    app.run(debug=True)
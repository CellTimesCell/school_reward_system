from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, PointTransaction, School
from app.forms import LoginForm, RegistrationForm, AddTeacherForm, PointsForm, ProfileEditForm, AddStudentForm
from urllib.parse import urlparse as url_parse
from functools import wraps

# Creating blueprints for different sections of the application
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
student_bp = Blueprint('student', __name__, url_prefix='/student')
teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# Decorators for role verification
def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('This page is accessible only to students.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('This page is accessible only to teachers.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('This page is accessible only to administrators.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


# Authentication routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))

        login_user(user)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            if user.role == 'student':
                next_page = url_for('student.dashboard')
            elif user.role == 'teacher':
                next_page = url_for('teacher.dashboard')
            elif user.role == 'admin':
                next_page = url_for('admin.dashboard')

        return redirect(next_page)

    school = School.query.first()
    return render_template('auth/login.html', title='Login', form=form, school=school)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='student'
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations! You have successfully registered.')
        return redirect(url_for('auth.login'))

    school = School.query.first()
    return render_template('auth/register_student.html', title='Registration', form=form, school=school)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


# Student routes
@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    # Get total points
    total_points = current_user.get_total_points()

    # Get transaction history
    transactions = PointTransaction.query.filter_by(student_id=current_user.id).order_by(
        PointTransaction.created_at.desc()).limit(10).all()

    return render_template('student/dashboard.html', title='Student Dashboard',
                           total_points=total_points, transactions=transactions)


@student_bp.route('/qr_code')
@login_required
@student_required
def qr_code():
    qr_code_img = current_user.generate_qr_code()
    return render_template('student/qr_code.html', title='QR Code', qr_code_img=qr_code_img)


@student_bp.route('/leaderboard')
@login_required
@student_required
def leaderboard():
    # Get all students sorted by points
    students = User.query.filter_by(role='student').all()

    # Sort manually since total points are calculated dynamically
    student_points = [(student, student.get_total_points()) for student in students]
    student_points.sort(key=lambda x: x[1], reverse=True)

    return render_template('student/leaderboard.html', title='Leaderboard',
                           student_points=student_points)


@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@student_required
def profile():
    form = ProfileEditForm(original_email=current_user.email)

    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('student.profile'))
    elif request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email

    return render_template('student/profile.html', title='Profile', form=form)


# Teacher routes
@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    # Get total points given
    total_points_given = current_user.get_points_given()

    # Get transaction history
    transactions = PointTransaction.query.filter_by(teacher_id=current_user.id).order_by(
        PointTransaction.created_at.desc()).limit(10).all()

    return render_template('teacher/dashboard.html', title='Teacher Dashboard',
                           total_points_given=total_points_given, transactions=transactions)


@teacher_bp.route('/scan_qr')
@login_required
@teacher_required
def scan_qr():
    return render_template('teacher/scan_qr.html', title='Scan QR Code')


@teacher_bp.route('/add_points/<student_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_points(student_id):
    student = User.query.filter_by(unique_id=student_id, role='student').first_or_404()

    form = PointsForm()
    if form.validate_on_submit():
        transaction = PointTransaction(
            student_id=student.id,
            teacher_id=current_user.id,
            points=form.points.data,
            description=form.description.data
        )
        db.session.add(transaction)
        db.session.commit()
        flash(f'Points successfully added for {student.first_name} {student.last_name}.')
        return redirect(url_for('teacher.teacher_board'))

    return render_template('teacher/add_points.html', title='Add Points',
                           student=student, form=form)


@teacher_bp.route('/teacher_board')
@login_required
@teacher_required
def teacher_board():
    # Get all teachers and their points
    teachers = User.query.filter_by(role='teacher').all()
    teacher_points = [(teacher, teacher.get_points_given()) for teacher in teachers]
    teacher_points.sort(key=lambda x: x[1], reverse=True)

    # Get current teacher's transactions
    transactions = PointTransaction.query.filter_by(teacher_id=current_user.id).order_by(
        PointTransaction.created_at.desc()).all()

    return render_template('teacher/teacher_board.html', title='Teacher Board',
                           teacher_points=teacher_points, transactions=transactions)


@teacher_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@teacher_required
def profile():
    form = ProfileEditForm(original_email=current_user.email)

    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your profile has been updated.')
        return redirect(url_for('teacher.profile'))
    elif request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email

    return render_template('teacher/profile.html', title='Profile', form=form)


# API for processing scanned QR code
@teacher_bp.route('/api/process_qr', methods=['POST'])
@login_required
@teacher_required
def process_qr():
    data = request.json
    if not data or 'qr_data' not in data:
        return jsonify({'success': False, 'error': 'QR code data is missing'}), 400

    qr_data = data['qr_data']
    student = User.query.filter_by(unique_id=qr_data, role='student').first()

    if not student:
        return jsonify({'success': False, 'error': 'Invalid QR code or student not found'}), 404

    # Return success and student ID for redirecting to the add points page
    return jsonify({
        'success': True,
        'student_id': student.unique_id,
        'student_name': f'{student.first_name} {student.last_name}'
    })


# Administrator routes
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    student_count = User.query.filter_by(role='student').count()
    teacher_count = User.query.filter_by(role='teacher').count()
    transaction_count = PointTransaction.query.count()

    # Recent transactions
    recent_transactions = PointTransaction.query.order_by(PointTransaction.created_at.desc()).limit(10).all()

    return render_template('admin/dashboard.html', title='Administrator Dashboard',
                           student_count=student_count, teacher_count=teacher_count,
                           transaction_count=transaction_count, recent_transactions=recent_transactions)


@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)


    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'danger')
        return redirect(url_for('admin.dashboard'))

    username = user.username
    role = user.role


    if role == 'student':
        PointTransaction.query.filter_by(student_id=user.id).delete()
    elif role == 'teacher':
        PointTransaction.query.filter_by(teacher_id=user.id).delete()


    db.session.delete(user)
    db.session.commit()

    flash(f'User {username} has been successfully deleted!', 'success')
    return redirect(url_for('admin.students_list' if role == 'student' else 'admin.teachers_list'))


@admin_bp.route('/add_student', methods=['GET', 'POST'])
@login_required
@admin_required
def add_student():
    form = AddStudentForm()
    if form.validate_on_submit():
        student = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='student'
        )
        student.set_password(form.password.data)
        db.session.add(student)
        db.session.commit()
        flash('Student has been successfully added!', 'success')
        return redirect(url_for('admin.students_list'))

    return render_template('admin/add_student.html', title='Add Student', form=form)

@admin_bp.route('/add_teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    form = AddTeacherForm()
    if form.validate_on_submit():
        teacher = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role='teacher'
        )
        teacher.set_password(form.password.data)
        db.session.add(teacher)
        db.session.commit()
        flash('Teacher successfully added!')
        return redirect(url_for('admin.teachers_list'))

    return render_template('admin/add_teacher.html', title='Add Teacher', form=form)


@admin_bp.route('/teachers')
@login_required
@admin_required
def teachers_list():
    teachers = User.query.filter_by(role='teacher').all()
    return render_template('admin/teachers_list.html', title='Teachers List', teachers=teachers)


@admin_bp.route('/students')
@login_required
@admin_required
def students_list():
    students = User.query.filter_by(role='student').all()
    return render_template('admin/students_list.html', title='Students List', students=students)


@admin_bp.route('/transactions')
@login_required
@admin_required
def transactions_list():
    transactions = PointTransaction.query.order_by(PointTransaction.created_at.desc()).all()
    return render_template('admin/transactions_list.html', title='Transactions Log', transactions=transactions)


# Root route redirects to login
@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'student':
            return redirect(url_for('student.dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
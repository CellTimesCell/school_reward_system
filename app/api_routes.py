from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, PointTransaction
from functools import wraps
import jwt
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


# Function to create JWT token
def create_token(user_id):
    payload = {
        'exp': datetime.utcnow() + timedelta(days=30),
        'iat': datetime.utcnow(),
        'sub': user_id
    }
    return jwt.encode(
        payload,
        current_app.config.get('SECRET_KEY'),
        algorithm='HS256'
    )


# Decorator for JWT token verification
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Token is missing!'}), 401

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, current_app.config.get('SECRET_KEY'), algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['sub']).first()
            if not current_user:
                return jsonify({'message': 'User not found!'}), 401
        except:
            return jsonify({'message': 'Invalid token!'}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# Authorization to get token
@api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required!'}), 400

    user = User.query.filter_by(username=data.get('username')).first()

    if not user or not user.check_password(data.get('password')):
        return jsonify({'message': 'Invalid username or password!'}), 401

    # Check that this is a teacher
    if user.role != 'teacher':
        return jsonify({'message': 'Access for teachers only!'}), 403

    token = create_token(user.id)

    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role
        }
    })


# Scanning student QR code
@api_bp.route('/scan-qr', methods=['POST'])
@token_required
def scan_qr(current_user):
    if current_user.role != 'teacher':
        return jsonify({'message': 'Access for teachers only!'}), 403

    data = request.get_json()
    if not data or not data.get('qr_data'):
        return jsonify({'message': 'QR code data is missing!'}), 400

    qr_data = data.get('qr_data')
    student = User.query.filter_by(unique_id=qr_data, role='student').first()

    if not student:
        return jsonify({'message': 'Invalid QR code or student not found!'}), 404

    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'unique_id': student.unique_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'current_points': student.get_total_points()
        }
    })


# Adding points to student
@api_bp.route('/add-points', methods=['POST'])
@token_required
def add_points(current_user):
    if current_user.role != 'teacher':
        return jsonify({'message': 'Access for teachers only!'}), 403

    data = request.get_json()
    if not data or not data.get('student_id') or not data.get('points') or not data.get('description'):
        return jsonify({'message': 'Incomplete data for adding points!'}), 400

    # Check points validity
    try:
        points = int(data.get('points'))
        if points <= 0:
            return jsonify({'message': 'Points must be a positive number!'}), 400
    except ValueError:
        return jsonify({'message': 'Invalid number of points!'}), 400

    student = User.query.filter_by(unique_id=data.get('student_id'), role='student').first()
    if not student:
        return jsonify({'message': 'Student not found!'}), 404

    # Create transaction
    transaction = PointTransaction(
        student_id=student.id,
        teacher_id=current_user.id,
        points=points,
        description=data.get('description')
    )

    # Add to database
    try:
        db.session.add(transaction)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error while saving: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'transaction': {
            'id': transaction.id,
            'points': transaction.points,
            'description': transaction.description,
            'created_at': transaction.created_at.isoformat(),
            'student_name': f"{student.first_name} {student.last_name}",
            'student_new_total': student.get_total_points()
        }
    })


# Getting teacher's transaction history
@api_bp.route('/transactions', methods=['GET'])
@token_required
def get_transactions(current_user):
    if current_user.role != 'teacher':
        return jsonify({'message': 'Access for teachers only!'}), 403

    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Get transactions with pagination
    transactions_query = PointTransaction.query.filter_by(teacher_id=current_user.id)
    transactions_paginated = transactions_query.order_by(PointTransaction.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    transactions = []
    for transaction in transactions_paginated.items:
        student = User.query.get(transaction.student_id)
        transactions.append({
            'id': transaction.id,
            'points': transaction.points,
            'description': transaction.description,
            'created_at': transaction.created_at.isoformat(),
            'student': {
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}"
            }
        })

    return jsonify({
        'transactions': transactions,
        'total': transactions_paginated.total,
        'pages': transactions_paginated.pages,
        'current_page': page
    })
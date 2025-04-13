# app/utils.py
import os
import secrets
from PIL import Image
from flask import current_app
import qrcode
from io import BytesIO
import base64


def save_picture(form_picture, output_size=(150, 150)):
    """Save uploaded picture with resizing"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static', 'profile_pics', picture_fn)

    # Resize image
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


def generate_qr_code(data, size=10):
    """Generate QR code for student ID"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)

    # Converting to base64 for embedding in HTML
    img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f'data:image/png;base64,{img_str}'


def get_user_stats(user_id, role):
    """Get statistics for a user (student or teacher)"""
    from app.models import PointTransaction

    if role == 'student':
        # Get total points and transaction history for a student
        transactions = PointTransaction.query.filter_by(student_id=user_id).order_by(
            PointTransaction.created_at.desc()).all()
        total_points = sum([t.points for t in transactions])
        return {
            'total_points': total_points,
            'transactions': transactions,
            'transaction_count': len(transactions)
        }
    elif role == 'teacher':
        # Get points given and transaction history for a teacher
        transactions = PointTransaction.query.filter_by(teacher_id=user_id).order_by(
            PointTransaction.created_at.desc()).all()
        total_points_given = sum([t.points for t in transactions])
        return {
            'total_points_given': total_points_given,
            'transactions': transactions,
            'transaction_count': len(transactions),
            'student_count': len(set([t.student_id for t in transactions]))
        }

    return {}
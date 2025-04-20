from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy import func, Index
import uuid
import qrcode
import io
import base64

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(255))  # Increased length for MySQL compatibility
    role = db.Column(db.String(20))  # 'student', 'teacher', 'admin'
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    unique_id = db.Column(db.String(36), unique=True, index=True)  # Default value handled in __init__

    # Cached aggregated values
    _total_points = db.Column(db.Integer, default=0)  # Cached points sum for student
    _points_given = db.Column(db.Integer, default=0)  # Cached points given sum for teacher

    # Relationships
    points_received = db.relationship('PointTransaction', foreign_keys='PointTransaction.student_id', backref='student',
                                      lazy='dynamic')
    points_given = db.relationship('PointTransaction', foreign_keys='PointTransaction.teacher_id', backref='teacher',
                                   lazy='dynamic')

    # Composite indexes for query optimization - shortened for MySQL compatibility
    __table_args__ = (
        Index('idx_user_role_uid', 'role', 'unique_id'),
    )

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # Ensure unique_id is set
        if not kwargs.get('unique_id'):
            self.unique_id = str(uuid.uuid4())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_total_points(self):
        """Returns the total points for a student (from cache if available)"""
        if self.role != 'student':
            return 0

        if self._total_points is not None:
            return self._total_points

        total = db.session.query(func.sum(PointTransaction.points)).filter(
            PointTransaction.student_id == self.id
        ).scalar() or 0

        self._total_points = total
        db.session.commit()
        return total

    def update_points_cache(self):
        """Update cached points value"""
        if self.role == 'student':
            total = db.session.query(func.sum(PointTransaction.points)).filter(
                PointTransaction.student_id == self.id
            ).scalar() or 0
            self._total_points = total
        elif self.role == 'teacher':
            total = db.session.query(func.sum(PointTransaction.points)).filter(
                PointTransaction.teacher_id == self.id
            ).scalar() or 0
            self._points_given = total
        db.session.commit()

    def get_points_given(self):
        """Returns the total points given by a teacher (from cache if available)"""
        if self.role != 'teacher':
            return 0

        if self._points_given is not None:
            return self._points_given

        total = db.session.query(func.sum(PointTransaction.points)).filter(
            PointTransaction.teacher_id == self.id
        ).scalar() or 0

        self._points_given = total
        db.session.commit()
        return total

    def generate_qr_code(self):
        """Generate QR code for student ID"""
        if self.role != 'student':
            return None

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.unique_id)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)

        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{img_str}'

    def __repr__(self):
        return f'<User {self.username}, Role: {self.role}>'

class PointTransaction(db.Model):
    __tablename__ = 'point_transactions'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    points = db.Column(db.Integer)
    description = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Shortened index names for MySQL compatibility
    __table_args__ = (
        Index('idx_trans_stu_tea', 'student_id', 'teacher_id'),
        Index('idx_trans_tea_date', 'teacher_id', 'created_at'),
    )

    def __repr__(self):
        return f'<PointTransaction: {self.points} points to Student:{self.student_id} from Teacher:{self.teacher_id}>'

    @classmethod
    def after_insert(cls, mapper, connection, target):
        """Update cached points values after transaction insertion"""
        from sqlalchemy.orm import Session
        session = Session(bind=connection)

        # Update student cache
        student = session.query(User).filter_by(id=target.student_id).first()
        if student:
            student._total_points = (student._total_points or 0) + target.points

        # Update teacher cache
        teacher = session.query(User).filter_by(id=target.teacher_id).first()
        if teacher:
            teacher._points_given = (teacher._points_given or 0) + target.points

class School(db.Model):
    __tablename__ = 'schools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    logo_url = db.Column(db.String(256))

    def __repr__(self):
        return f'<School {self.name}>'

# Register events
from sqlalchemy import event
event.listen(PointTransaction, 'after_insert', PointTransaction.after_insert)

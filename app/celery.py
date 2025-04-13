from flask import Flask
from celery import Celery
from celery.schedules import crontab
from app.models import User, PointTransaction
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta

celery = Celery(__name__)


def init_celery(app: Flask) -> None:
    """Initialize Celery with Flask app settings"""
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Configure task schedules
    celery.conf.beat_schedule = {
        'update-point-caches-hourly': {
            'task': 'app.celery.update_point_caches',
            'schedule': 3600.0,  # Every hour
        },
        'generate-daily-statistics': {
            'task': 'app.celery.generate_daily_statistics',
            'schedule': crontab(hour=0, minute=5),  # Daily at 00:05
        },
        'send-inactivity-notifications': {
            'task': 'app.celery.send_inactivity_notifications',
            'schedule': crontab(day_of_week=1, hour=9, minute=0),  # Every Monday at 9:00
        },
    }


@celery.task
def update_point_caches():
    """Update cached point values for all users"""
    # Update for students
    students = User.query.filter_by(role='student').all()
    for student in students:
        total = db.session.query(func.sum(PointTransaction.points)).filter(
            PointTransaction.student_id == student.id
        ).scalar() or 0
        student._total_points = total

    # Update for teachers
    teachers = User.query.filter_by(role='teacher').all()
    for teacher in teachers:
        total = db.session.query(func.sum(PointTransaction.points)).filter(
            PointTransaction.teacher_id == teacher.id
        ).scalar() or 0
        teacher._points_given = total

    db.session.commit()
    return {'success': True, 'timestamp': datetime.utcnow().isoformat()}


@celery.task
def generate_daily_statistics():
    """Generate daily statistics"""
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    # Statistics for yesterday
    daily_stats = {
        'timestamp': now.isoformat(),
        'date': yesterday.date().isoformat(),
        'transactions_count': PointTransaction.query.filter(
            PointTransaction.created_at >= yesterday,
            PointTransaction.created_at < now
        ).count(),
        'total_points': db.session.query(func.sum(PointTransaction.points)).filter(
            PointTransaction.created_at >= yesterday,
            PointTransaction.created_at < now
        ).scalar() or 0,
        'active_teachers': db.session.query(func.count(func.distinct(PointTransaction.teacher_id))).filter(
            PointTransaction.created_at >= yesterday,
            PointTransaction.created_at < now
        ).scalar() or 0,
        'active_students': db.session.query(func.count(func.distinct(PointTransaction.student_id))).filter(
            PointTransaction.created_at >= yesterday,
            PointTransaction.created_at < now
        ).scalar() or 0,
    }

    return daily_stats


@celery.task
def send_inactivity_notifications():
    """Send notifications to inactive teachers"""
    threshold = datetime.utcnow() - timedelta(days=7)  # Inactive for more than a week

    teachers = User.query.filter_by(role='teacher').all()
    inactive_teachers = []

    for teacher in teachers:
        last_transaction = PointTransaction.query.filter_by(teacher_id=teacher.id).order_by(
            PointTransaction.created_at.desc()
        ).first()

        if last_transaction is None or last_transaction.created_at < threshold:
            inactive_teachers.append({
                'id': teacher.id,
                'name': f"{teacher.first_name} {teacher.last_name}",
                'email': teacher.email,
                'last_activity': last_transaction.created_at.isoformat() if last_transaction else None
            })

    return {'inactive_teacher_count': len(inactive_teachers), 'teachers': inactive_teachers}
from flask import Flask
import logging
from datetime import datetime, timedelta

# Try to import Celery, create fallback if not available
try:
    from celery import Celery
    from celery.schedules import crontab
    celery = Celery(__name__)
    CELERY_AVAILABLE = True
except ImportError:
    # Create dummy implementations for when Celery isn't available
    logging.warning("Celery not available. Tasks will run synchronously if manually triggered.")
    
    # Mock crontab for compatibility
    def crontab(minute=0, hour=0, day_of_week='*', day_of_month='*', month_of_year='*'):
        return {'minute': minute, 'hour': hour, 'day_of_week': day_of_week, 
                'day_of_month': day_of_month, 'month_of_year': month_of_year}
    
    # Dummy Task class
    class DummyTask:
        def __call__(self, *args, **kwargs):
            return self.run(*args, **kwargs)
        
        def apply_async(self, *args, **kwargs):
            return self.run(*args, **kwargs)
            
        def delay(self, *args, **kwargs):
            return self.run(*args, **kwargs)
    
    # Dummy Celery class
    class DummyCelery:
        Task = DummyTask
        conf = {'beat_schedule': {}}
        
        def task(self, *args, **kwargs):
            def decorator(f):
                # Make task callable directly
                f.delay = lambda *args, **kwargs: f(*args, **kwargs)
                f.apply_async = lambda *args, **kwargs: f(*args, **kwargs)
                return f
            return decorator if not args else decorator(args[0])
    
    celery = DummyCelery()
    CELERY_AVAILABLE = False


def init_celery(app: Flask) -> None:
    """Initialize Celery with Flask app settings"""
    if not CELERY_AVAILABLE:
        app.logger.warning("Celery not available. Background tasks will run synchronously if manually triggered.")
        return
        
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
    # Import here to avoid circular imports
    from app import db
    from app.models import User, PointTransaction
    from sqlalchemy import func
    
    try:
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
    except Exception as e:
        if CELERY_AVAILABLE:
            logging.error(f"Error updating point caches: {str(e)}")
        else:
            logging.error(f"Error updating point caches (running synchronously): {str(e)}")
        return {'success': False, 'error': str(e)}


@celery.task
def generate_daily_statistics():
    """Generate daily statistics"""
    # Import here to avoid circular imports
    from app import db
    from app.models import PointTransaction
    from sqlalchemy import func
    
    try:
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
    except Exception as e:
        logging.error(f"Error generating daily statistics: {str(e)}")
        return {'success': False, 'error': str(e)}


@celery.task
def send_inactivity_notifications():
    """Send notifications to inactive teachers"""
    # Import here to avoid circular imports
    from app.models import User, PointTransaction
    
    try:
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
    except Exception as e:
        logging.error(f"Error sending inactivity notifications: {str(e)}")
        return {'success': False, 'error': str(e)}

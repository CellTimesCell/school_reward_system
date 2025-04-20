import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_jwt_extended import JWTManager
import logging
from logging.handlers import RotatingFileHandler

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
jwt = JWTManager()


def create_app(config_name=None):
    app = Flask(__name__)

    # Application configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    from config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app) if hasattr(config[config_name], 'init_app') else None

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)

    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Initialize cache with simple in-memory cache
    from app.cache import init_cache
    cache = init_cache(app)

    # Initialize Celery if available, otherwise use fallback
    try:
        from app.celery import init_celery
        init_celery(app)
        app.logger.info("Celery initialized successfully")
    except Exception as e:
        app.logger.warning(f"Celery initialization failed: {str(e)}. Background tasks will run synchronously or not at all.")

    # Configure logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('School Rewards App startup')

    # Register blueprints
    from app.routes import auth_bp, student_bp, teacher_bp, admin_bp
    from app.api_routes import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Configure Prometheus monitoring only if enabled and available
    if app.config.get('PROMETHEUS_METRICS', False):
        try:
            from prometheus_client import make_wsgi_app
            from werkzeug.middleware.dispatcher import DispatcherMiddleware

            # Add Prometheus metrics
            app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
                '/metrics': make_wsgi_app()
            })
            app.logger.info("Prometheus metrics enabled")
        except ImportError:
            app.logger.warning("Prometheus client not available - metrics disabled")

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429

    # Context processors
    @app.context_processor
    def inject_school():
        from app.models import School
        return dict(school=School.query.first())

    return app

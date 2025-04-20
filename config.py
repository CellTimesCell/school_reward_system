import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Basic settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'

    # database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                        'mysql://celltimescell:zeusomerta@celltimescell.mysql.pythonanywhere-services.com/celltimescell$default'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_recycle': 280  # Prevent "MySQL server has gone away" errors
}

    # Redis cache settings
    # REDIS_HOST = os.environ.get('REDIS_HOST') or 'localhost'
    # REDIS_PORT = int(os.environ.get('REDIS_PORT') or 6379)
    # REDIS_DB = int(os.environ.get('REDIS_DB') or 0)

    # File upload settings
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    # App settings
    APP_NAME = 'School Points System'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'

    # JWT settings for API
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 30  # 30 days

    # Celery settings for async tasks
    # CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/1'
    # CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/1'

    # Monitoring settings
    PROMETHEUS_METRICS = os.environ.get('PROMETHEUS_METRICS', 'False').lower() == 'true'

    # Pagination settings
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    @classmethod
    def init_app(cls, app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

    # Production security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

    # SSL settings
    SSL_REDIRECT = os.environ.get('SSL_REDIRECT', 'False').lower() == 'true'

    @classmethod
    def init_app(cls, app):
        super(ProductionConfig, cls).init_app(app)

        import logging
        from logging.handlers import RotatingFileHandler

        file_handler = RotatingFileHandler('logs/app.log',
                                           maxBytes=10 * 1024 * 1024,
                                           backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('School Rewards App startup')

        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

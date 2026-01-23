# Superset Configuration
# See https://superset.apache.org/docs/installation/configuring-superset

import os
from celery.schedules import crontab

# Flask App Builder configuration
# Your App secret key
SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY')

# The SQLAlchemy connection string
SQLALCHEMY_DATABASE_URI = os.environ.get('SUPERSET_DATABASE_URI')

# Flask-WTF flag for CSRF
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None

# Set this API key to enable Mapbox visualizations
MAPBOX_API_KEY = os.environ.get('MAPBOX_API_KEY', '')

# Cache configuration
# Using Valkey (Redis alternative) for caching
CACHE_CONFIG = {
    'CACHE_TYPE': 'redis',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': os.environ.get('REDIS_HOST', 'valkey'),
    'CACHE_REDIS_PORT': int(os.environ.get('REDIS_PORT', 6379)),
    'CACHE_REDIS_PASSWORD': os.environ.get('REDIS_PASSWORD', ''),
    'CACHE_REDIS_DB': 1,
}

# Celery configuration
class CeleryConfig:
    BROKER_URL = f"redis://:{os.environ.get('REDIS_PASSWORD', '')}@{os.environ.get('REDIS_HOST', 'valkey')}:{os.environ.get('REDIS_PORT', 6379)}/0"
    CELERY_IMPORTS = ('superset.sql_lab', 'superset.tasks')
    CELERY_RESULT_BACKEND = f"redis://:{os.environ.get('REDIS_PASSWORD', '')}@{os.environ.get('REDIS_HOST', 'valkey')}:{os.environ.get('REDIS_PORT', 6379)}/0"
    CELERYD_LOG_LEVEL = 'INFO'
    CELERYD_PREFETCH_MULTIPLIER = 10
    CELERY_ACKS_LATE = True
    CELERY_ANNOTATIONS = {
        'sql_lab.get_sql_results': {
            'rate_limit': '100/s',
        },
        'email_reports.send': {
            'rate_limit': '1/s',
            'time_limit': 120,
            'soft_time_limit': 150,
            'ignore_result': True,
        },
    }
    CELERYBEAT_SCHEDULE = {
        'email_reports.schedule_hourly': {
            'task': 'email_reports.schedule_hourly',
            'schedule': crontab(minute=1, hour='*'),
        },
    }

CELERY_CONFIG = CeleryConfig

# Results backend configuration
RESULTS_BACKEND = {
    'CACHE_TYPE': 'redis',
    'CACHE_DEFAULT_TIMEOUT': 86400,
    'CACHE_KEY_PREFIX': 'superset_results_',
    'CACHE_REDIS_HOST': os.environ.get('REDIS_HOST', 'valkey'),
    'CACHE_REDIS_PORT': int(os.environ.get('REDIS_PORT', 6379)),
    'CACHE_REDIS_PASSWORD': os.environ.get('REDIS_PASSWORD', ''),
    'CACHE_REDIS_DB': 2,
}

# Feature flags
FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
    'DASHBOARD_NATIVE_FILTERS': True,
    'DASHBOARD_CROSS_FILTERS': True,
    'DASHBOARD_NATIVE_FILTERS_SET': True,
    'EMBEDDABLE_CHARTS': True,
    'SCHEDULED_QUERIES': True,
    'ESTIMATE_QUERY_COST': False,
    'ENABLE_JAVASCRIPT_CONTROLS': False,
    'ALERT_REPORTS': True,
}

# SQL Lab configuration
SQLLAB_ASYNC_TIME_LIMIT_SEC = 300
SQLLAB_TIMEOUT = 300
SUPERSET_WEBSERVER_TIMEOUT = 300

# Prevent SQL Lab from querying more than specified limit
SQL_MAX_ROW = 100000

# Allow queries with higher row limit
SQLLAB_ROW_LIMIT = 100000

# Default row limit for SQL Lab queries
DEFAULT_SQLLAB_LIMIT = 10000

# Enable CSV upload
CSV_TO_HIVE_UPLOAD_S3_BUCKET = ''

# List of data engines to show in the dropdown for SQL Lab queries
ADDITIONAL_MODULE_DS_MAP = {}

# Security configuration
# Force all requests to HTTPS
ENABLE_PROXY_FIX = True
TALISMAN_ENABLED = False

# Session cookie configuration
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'

# CORS configuration
ENABLE_CORS = True
CORS_OPTIONS = {
    'supports_credentials': True,
    'allow_headers': ['*'],
    'resources': ['*'],
    'origins': ['*']
}

# Webserver configuration
SUPERSET_WEBSERVER_PROTOCOL = 'http'
SUPERSET_WEBSERVER_ADDRESS = '0.0.0.0'
SUPERSET_WEBSERVER_PORT = 8088

# Thumbnail configuration
THUMBNAIL_CACHE_CONFIG = {
    'CACHE_TYPE': 'redis',
    'CACHE_DEFAULT_TIMEOUT': 86400,
    'CACHE_KEY_PREFIX': 'superset_thumbnails_',
    'CACHE_REDIS_HOST': os.environ.get('REDIS_HOST', 'valkey'),
    'CACHE_REDIS_PORT': int(os.environ.get('REDIS_PORT', 6379)),
    'CACHE_REDIS_PASSWORD': os.environ.get('REDIS_PASSWORD', ''),
    'CACHE_REDIS_DB': 3,
}

# Alert and report configuration
ALERT_REPORTS_NOTIFICATION_DRY_RUN = False
WEBDRIVER_BASEURL = f"{SUPERSET_WEBSERVER_PROTOCOL}://localhost:{SUPERSET_WEBSERVER_PORT}/"
WEBDRIVER_BASEURL_USER_FRIENDLY = WEBDRIVER_BASEURL

# Filter configuration
DASHBOARD_NATIVE_FILTERS_SET = True

# DEV.to Analytics specific configuration
APP_NAME = "DEV.to Analytics"
APP_ICON = "/static/assets/images/superset-logo-horiz.png"
APP_ICON_WIDTH = 126

# Custom CSS
EXTRA_CATEGORICAL_COLOR_SCHEMES = [
    {
        "id": "devto",
        "description": "DEV.to Colors",
        "label": "DEV.to",
        "colors": ["#3B49DF", "#0A0A0A", "#898989", "#D2D2D2", "#F5F5F5"]
    }
]

# Time grain configurations
TIME_GRAIN_ADDONS = {}
TIME_GRAIN_DENYLIST = []

# Logging configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s:%(levelname)s:%(name)s:%(message)s'

# Database connection pool configuration
SQLALCHEMY_POOL_SIZE = 10
SQLALCHEMY_POOL_TIMEOUT = 30
SQLALCHEMY_MAX_OVERFLOW = 20
SQLALCHEMY_POOL_RECYCLE = 3600

# Row level security
ROW_LEVEL_SECURITY = True

# Enable scheduled queries
SCHEDULED_QUERIES = {
    'JSONSCHEMA_VALIDATION': False
}

# Async query configuration
GLOBAL_ASYNC_QUERIES_TRANSPORT = 'polling'
GLOBAL_ASYNC_QUERIES_POLLING_DELAY = 500

# Dashboard auto-refresh
DASHBOARD_AUTO_REFRESH_MODE = 'force'
DASHBOARD_AUTO_REFRESH_INTERVALS = [
    [0, 'Don\'t refresh'],
    [10, '10 seconds'],
    [30, '30 seconds'],
    [60, '1 minute'],
    [300, '5 minutes'],
    [1800, '30 minutes'],
    [3600, '1 hour'],
]

# Language support
LANGUAGES = {
    'en': {'flag': 'us', 'name': 'English'},
}

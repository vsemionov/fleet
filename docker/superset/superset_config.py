import os
from datetime import timedelta


# The SQLAlchemy connection string
SQLALCHEMY_DATABASE_URI = os.environ['SUPERSET_DATABASE_URL']

# Default cache for Superset objects
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': int(timedelta(days=1).total_seconds()),
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_URL': os.environ['SUPERSET_REDIS_URL'],
}

# Cache for datasource metadata and query results
DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': int(timedelta(days=1).total_seconds()),
    'CACHE_KEY_PREFIX': 'superset_data_',
    'CACHE_REDIS_URL': os.environ['SUPERSET_REDIS_URL'],
}

# Cache for dashboard filter state
FILTER_STATE_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': int(timedelta(days=1).total_seconds()),
    'CACHE_KEY_PREFIX': 'superset_filter_',
    'CACHE_REDIS_URL': os.environ['SUPERSET_REDIS_URL'],
}

# Cache for explore form data state
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': int(timedelta(days=1).total_seconds()),
    'CACHE_KEY_PREFIX': 'superset_explore_',
    'CACHE_REDIS_URL': os.environ['SUPERSET_REDIS_URL'],
}

FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
}

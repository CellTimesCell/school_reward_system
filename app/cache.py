from flask_caching import Cache

# Cache initialization
cache = Cache()  # This line was missing in the original file!

def init_cache(app):
    """Cache initialization for the application"""
    cache_config = {
        'CACHE_TYPE': 'simple',  # Using simple in-memory cache instead of Redis
    }
    app.config.from_mapping({'CACHE_CONFIG': cache_config})
    cache.init_app(app, config=cache_config)
    return cache

def cache_user_points(timeout=300):
    """Decorator for caching user points"""
    def decorator(f):
        return cache.memoize(timeout=timeout)(f)
    return decorator

def clear_user_points_cache(user_id):
    """Clear user points cache when changes occur"""
    cache.delete_memoized(user_id)

def cache_leaderboard(timeout=600):
    """Decorator for caching the leaderboard"""
    def decorator(f):
        return cache.cached(timeout=timeout, key_prefix="leaderboard")(f)
    return decorator

def clear_leaderboard_cache():
    """Clear leaderboard cache"""
    cache.delete("leaderboard")

def rate_limit(limit=100, per=60, scope_func=None):
    """Stub for request rate limiting"""
    def decorator(f):
        return f  # Simply return the function without limitations
    return decorator
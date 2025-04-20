from flask_caching import Cache

# Cache initialization
cache = Cache()

def init_cache(app):
    """Cache initialization for the application"""
    # Use simple in-memory cache for PythonAnywhere compatibility
    cache_config = {
        'CACHE_TYPE': 'simple',  # Using simple in-memory cache
        'CACHE_DEFAULT_TIMEOUT': 300  # 5 minutes default timeout
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
    """Simple rate limiting implementation without Redis dependency"""
    from flask import request, current_app
    import time
    import threading
    
    # Use a simple in-memory store for rate limiting
    if not hasattr(current_app, '_rate_limit_store'):
        current_app._rate_limit_store = {}
        current_app._rate_limit_lock = threading.Lock()
    
    def decorator(f):
        def wrapped(*args, **kwargs):
            # Simple key based on IP
            key = request.remote_addr
            if scope_func:
                key = f"{key}:{scope_func()}"
            
            current_time = time.time()
            with current_app._rate_limit_lock:
                # Clean up old entries
                if key in current_app._rate_limit_store:
                    current_app._rate_limit_store[key] = [
                        t for t in current_app._rate_limit_store[key] 
                        if current_time - t < per
                    ]
                else:
                    current_app._rate_limit_store[key] = []
                
                # Check if limit is exceeded
                if len(current_app._rate_limit_store[key]) >= limit:
                    from flask import abort
                    abort(429)  # Too Many Requests
                
                # Add current request
                current_app._rate_limit_store[key].append(current_time)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator

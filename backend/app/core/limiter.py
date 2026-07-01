"""
Shared rate limiter instance.

Defined here (not in main.py) to avoid circular imports between
main.py and the route modules that need @limiter.limit().
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

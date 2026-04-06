"""
Rate limiter instance shared across the application.
Configured with in-memory storage (suitable for single-process dev/prod).
For multi-process deployments, swap storage_uri to a Redis URL.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

"""
routers/__init__.py - Router package initialization
Exports all router modules for use in api.py
"""
from . import auth
from . import admin
from . import chat
from . import documents

__all__ = ['auth', 'admin', 'chat', 'documents']

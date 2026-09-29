"""Vercel entry point for the Engineering AI Platform API.

Expose the native WSGI application directly. Vercel's Python runtime should
invoke this WSGI callable; the local Uvicorn WSGI middleware wrapper remains
available through api.app for local development.
"""
from api.app import APIApp

app = APIApp()

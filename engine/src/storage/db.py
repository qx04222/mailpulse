"""
Single Supabase client instance for the entire engine.
"""
from supabase import create_client
from ..config import settings

db = create_client(settings.supabase_url, settings.supabase_service_key)

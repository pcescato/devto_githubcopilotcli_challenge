"""
API Dependencies - Authentication and Authorization

Provides dependency injection functions for FastAPI endpoints.
"""

import os
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Key configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Get API key from environment or use demo fallback
VALID_API_KEY = os.getenv("API_KEY", "devto-challenge-2026")


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key from X-API-Key header
    
    Args:
        api_key: API key from request header
        
    Returns:
        API key if valid
        
    Raises:
        HTTPException: 403 if missing or invalid
    """
    if api_key is None:
        raise HTTPException(
            status_code=403,
            detail="Missing API Key. Include 'X-API-Key' header in your request."
        )
    
    if api_key != VALID_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    
    return api_key

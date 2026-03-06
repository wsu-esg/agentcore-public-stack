"""Health check endpoint"""

import os

from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agent-core",
        "version": os.environ.get("APP_VERSION", "unknown")
    }

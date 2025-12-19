#!/usr/bin/env python3
"""
Health Check Endpoint for Cloud Hosting
Used by Railway, Render, Heroku, etc. to verify bot is running
"""

import json
import os
from datetime import datetime

def health_check():
    """Simple health check for cloud platforms"""
    try:
        # Check if bot token exists (basic validation)
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return {
                "status": "error",
                "message": "BOT_TOKEN not configured",
                "timestamp": datetime.utcnow().isoformat()
            }

        return {
            "status": "healthy",
            "message": "Medical Reports Bot is running",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    # For local testing
    result = health_check()
    print(json.dumps(result, indent=2))

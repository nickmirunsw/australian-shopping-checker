"""
Database configuration switcher for development/production.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Determine environment
IS_PRODUCTION = os.getenv("DATABASE_URL") is not None
USE_POSTGRESQL = IS_PRODUCTION or os.getenv("FORCE_POSTGRESQL", "false").lower() == "true"

# Import the appropriate database module
if USE_POSTGRESQL:
    logger.info("Using PostgreSQL database")
    from .database_pg import *
else:
    logger.info("Using SQLite database")
    from .database import *
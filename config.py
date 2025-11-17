"""Configuration module for OneTrueAddress agent."""
import os
from dotenv import load_dotenv

load_dotenv()

# Claude API Configuration
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "").strip()

# Golden Source Table Configuration
# Update these based on your database connection details
GOLDEN_SOURCE_DB_TYPE = os.getenv("GOLDEN_SOURCE_DB_TYPE", "postgresql")  # postgresql, mysql, sqlite, etc.
GOLDEN_SOURCE_HOST = os.getenv("GOLDEN_SOURCE_HOST")
GOLDEN_SOURCE_PORT = os.getenv("GOLDEN_SOURCE_PORT")
GOLDEN_SOURCE_DATABASE = os.getenv("GOLDEN_SOURCE_DATABASE")
GOLDEN_SOURCE_USER = os.getenv("GOLDEN_SOURCE_USER")
GOLDEN_SOURCE_PASSWORD = os.getenv("GOLDEN_SOURCE_PASSWORD")
GOLDEN_SOURCE_TABLE = os.getenv("GOLDEN_SOURCE_TABLE", "addresses")

# Confidence Threshold Configuration
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "90.0"))  # Default 90%


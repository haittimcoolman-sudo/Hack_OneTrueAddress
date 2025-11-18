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

# Golden Source and Internal Tables Configuration
GOLDEN_SOURCE_MATCH_TABLE = os.getenv("GOLDEN_SOURCE_MATCH_TABLE", "team_cool_and_gang.pinellas_fl")
INTERNAL_MATCH_TABLE = os.getenv("INTERNAL_MATCH_TABLE", "team_cool_and_gang.pinellas_fl_baddatascenarios")

# Confidence Threshold Configuration
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "90.0"))  # Default 90%

# Fuzzy Matching Configuration
FUZZY_MATCH_THRESHOLD = float(os.getenv("FUZZY_MATCH_THRESHOLD", "95.0"))  # Default 95% similarity
FUZZY_MATCH_MIN_THRESHOLD = 75.0  # Minimum allowed threshold (floor)


# Hack_OneTrueAddress
Hack-Ai-Thon OneTrueAddress agent repository

## Overview
An AI agent that uses Claude LLM to compare free-form plain English addresses against a golden source table of known good addresses.

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory with the following variables:

```env
# Claude API Configuration
CLAUDE_API_KEY=your_claude_api_key_here

# Golden Source Database Configuration
# Database type: postgresql, mysql, or sqlite
GOLDEN_SOURCE_DB_TYPE=postgresql
GOLDEN_SOURCE_HOST=localhost
GOLDEN_SOURCE_PORT=5432
GOLDEN_SOURCE_DATABASE=your_database_name
GOLDEN_SOURCE_USER=your_username
GOLDEN_SOURCE_PASSWORD=your_password
GOLDEN_SOURCE_TABLE=addresses

# Confidence Threshold Configuration (optional, default: 90.0)
# Matches with confidence below this threshold will trigger business rule exceptions
CONFIDENCE_THRESHOLD=90.0
```

### 3. Install Database Driver (if needed)
- For PostgreSQL: `pip install psycopg2-binary`
- For MySQL: `pip install mysql-connector-python`
- SQLite: Included with Python

## Usage

### Web Interface (Recommended)

Start the web application:

```bash
python web_app.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

The web interface features:
- **Down South Communications** branded UI
- Free-form text input for addresses
- Real-time address matching
- Detailed results display with confidence scores
- Business rule exception warnings

### Command Line Interface

Run the agent with an address to match:

```bash
python main.py "123 Main Street, New York, NY 10001"
```

The agent will:
1. Extract search criteria from the input address using Claude (with confidence score)
2. Filter the golden source database using extracted criteria
3. Query Claude to find the exact match from filtered candidates (with confidence score)
4. Display the match result with confidence and reasoning
5. Flag business rule exceptions for matches below the confidence threshold

## Confidence and Business Rules

The agent uses confidence scores (0-100) for both:
- **Extraction confidence**: How confident Claude is in extracting address components
- **Match confidence**: How confident Claude is in the final address match

**Business Rule Exception**: If the match confidence is below the configured threshold (default 90%), the system will:
- Log a warning message
- Flag the result with `business_rule_exception: true`
- Indicate that manual review may be required

You can configure the confidence threshold in your `.env` file using `CONFIDENCE_THRESHOLD` (default: 90.0).

## Project Structure

- `web_app.py` - Flask web application (web UI)
- `main.py` - Entry point and CLI interface
- `address_agent.py` - Main agent orchestrating the matching process
- `claude_client.py` - Claude API interaction module
- `golden_source.py` - Database connection and query module
- `config.py` - Configuration management
- `templates/` - HTML templates for web UI
- `static/` - CSS and static assets for web UI
- `requirements.txt` - Python dependencies
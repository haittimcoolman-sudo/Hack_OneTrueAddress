# Hack_OneTrueAddress
Hack-Ai-Thon OneTrueAddress agent repository

## Overview
An AI-powered address matching and consolidation system that uses fuzzy string matching combined with Claude AI to match user-input addresses against two database tables (Golden Source and Internal). The system provides intelligent address matching, identifies discrepancies, consolidates duplicate records, and pushes updates to a tracking table for review.

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

# Database Configuration
# Database type: postgresql, mysql, or sqlite
GOLDEN_SOURCE_DB_TYPE=postgresql
GOLDEN_SOURCE_HOST=localhost
GOLDEN_SOURCE_PORT=5432
GOLDEN_SOURCE_DATABASE=your_database_name
GOLDEN_SOURCE_USER=your_username
GOLDEN_SOURCE_PASSWORD=your_password

# Table Configuration
# Golden Source table (authoritative address data)
GOLDEN_SOURCE_MATCH_TABLE=team_cool_and_gang.pinellas_fl

# Internal table (customer addresses with potential duplicates)
INTERNAL_MATCH_TABLE=team_cool_and_gang.pinellas_fl_baddatascenarios

# Fuzzy Matching Configuration (optional)
# Minimum similarity score for matches (50-100, default: 95.0)
# Higher values = stricter matching
FUZZY_MATCH_THRESHOLD=95.0

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
- **Cool & Gang Communications** branded UI with light/dark theme support
- Free-form text input for addresses
- Fuzzy matching search across Golden Source and Internal tables
- AI-powered match review and validation by Claude
- Side-by-side display of matches from both tables with similarity scores
- Individual AI analysis for each match candidate
- Push updates functionality to consolidate and write records to `internal_updates` table
- Business rule exception warnings for low-confidence matches
- Configurable similarity threshold slider

### Command Line Interface

Run the agent with an address to match:

```bash
python main.py "123 Main Street, New York, NY 10001"
```

The agent will:
1. Perform fuzzy matching on MasterAddress column in both Golden Source and Internal tables
2. Filter results by street number (exact match required) and similarity threshold
3. Send top matches to Claude for AI-powered review and analysis
4. Display the best match with similarity score, Claude's reasoning, and source table
5. Flag business rule exceptions for matches below the confidence threshold

## How It Works

### Address Matching Process

1. **Fuzzy Matching**: The system performs fuzzy string matching on the `MasterAddress` column in both tables
   - Street numbers must match exactly
   - Zip codes and state abbreviations are removed before comparison
   - Uses token-based similarity scoring (rapidfuzz) to handle word order differences
   - Returns all matches above the configured similarity threshold

2. **AI Review**: Claude analyzes the top matches and provides:
   - Individual assessment for each candidate (1-2 sentences)
   - Confidence score for each match (0-100)
   - Reasoning for the best overall match
   - Identification of any concerns

3. **Results Display**: The web interface shows:
   - Best match with similarity score and source table
   - All Golden Source matches with AI analysis
   - All Internal matches with AI analysis
   - Claude's overall reasoning and recommendation

### Business Rules & Thresholds

- **Fuzzy Match Threshold** (default: 95%): Minimum similarity score to include a match
  - Configurable via `FUZZY_MATCH_THRESHOLD` in `.env`
  - Minimum allowed: 75%
  
- **Business Rule Exception**: Matches below the threshold trigger:
  - Warning message in the UI
  - `business_rule_exception: true` flag
  - Recommendation for manual review

### Address Consolidation

When multiple Internal addresses match a single Golden Source address, the system:
1. Checks for active customers and fiber media service
2. Applies consolidation rules:
   - Prefers Active Customer records
   - Upgrades to Fiber if any record has fiber service
   - Preserves "Y" flags for Exclusion and Engineering Review
   - Fails with error if multiple Active Customers or multiple Fiber records exist
3. Updates address fields from Golden Source (authoritative)
4. Writes consolidated record to `internal_updates` table with metadata:
   - **Scenario 1**: Multiple Internal Matches (tpi: 20)
   - **Scenario 2**: Single Internal Match with MasterAddress Mismatch (tpi: 10)
   - **Scenario 3**: No Internal Match / Golden Source Only (tpi: 5)

## Project Structure

- `web_app.py` - Flask web application with endpoints for address matching and updates
- `main.py` - Command-line interface for address matching
- `address_agent.py` - Main agent orchestrating fuzzy matching and Claude review
- `claude_client.py` - Claude API interaction module
- `golden_source.py` - Database connector with fuzzy matching, consolidation, and update logic
- `config.py` - Configuration management (environment variables)
- `templates/index.html` - Web UI template with dual-table results display
- `static/` - CSS and static assets (logo, styles with theme support)
- `requirements.txt` - Python dependencies (Flask, anthropic, rapidfuzz, psycopg2-binary, etc.)

## Key Features

### Dual-Table Search
- Searches both Golden Source (authoritative) and Internal (customer) tables simultaneously
- Displays results from both sources side-by-side for comparison
- Highlights best match and provides source table information

### Intelligent Matching
- **Fuzzy matching** with rapidfuzz for handling typos and variations
- **Exact street number matching** to avoid false positives
- **Normalized comparison** (removes zip codes and states before matching)
- **AI validation** by Claude for confidence and reasoning

### Data Quality Management
- Identifies addresses in Internal table that don't match Golden Source
- Consolidates duplicate Internal records using business rules
- Tracks all updates in `internal_updates` table with scenario classification
- Supports manual review workflow for complex cases

### Modern Web Interface
- Light and dark theme support
- Real-time search with configurable threshold slider
- Expandable match cards with detailed AI analysis
- "Push Updates" button to consolidate and write to database
- Responsive design for desktop and mobile

## API Endpoints

The web application provides the following REST endpoints:

- `GET /` - Main web interface
- `POST /match` - Match an address (returns Golden Source + Internal matches)
- `POST /push_updates` - Consolidate Internal records and push to `internal_updates`
- `POST /write_to_internal` - Write Golden Source record when no Internal match exists
- `GET /health` - Health check endpoint

## Database Requirements

Both the Golden Source and Internal tables must have the following column:
- `MasterAddress` - The full address string used for fuzzy matching (e.g., "123 Main St, City, FL 12345")

### Golden Source Table Expected Columns
- `MasterAddress` - Full address (required for matching)
- `address1` - Street address
- `address2` - Apartment/Unit (optional)
- `Mailing City` or `city` - City name
- `state` - State abbreviation
- `zipcode` - ZIP code

### Internal Table Expected Columns
- `MasterAddress` - Full address (required for matching)
- `Address` - Street address
- `City` - City name
- `State` - State abbreviation
- `Zipcode` - ZIP code
- `Active Customer` - Y/N flag for active customers (optional)
- `Media` - Service type (e.g., "FIBER", "COPPER") (optional)
- `Exclusion` - Y/N exclusion flag (optional)
- `Engineering Review` - Y/N flag for engineering review (optional)

### Internal Updates Table
The `team_cool_and_gang.internal_updates` table is used to track all consolidations and writes. It will be populated with:
- All columns from the consolidated record
- `Agent Action` (TEXT) - Description of the consolidation scenario
- `tpi` (INTEGER) - Task priority indicator (5, 10, or 20)
- `datetime` (TIMESTAMP or TIMESTAMPTZ) - Date and time of the operation

**Important**: The `datetime` column must be `TIMESTAMP` or `TIMESTAMPTZ` type (not `DATE`) to store both date and time information.

**Example SQL to create the datetime column**:
```sql
-- When creating the table:
CREATE TABLE team_cool_and_gang.internal_updates (
    -- ... other columns ...
    "Agent Action" TEXT,
    tpi INTEGER,
    datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Or to modify existing table:
ALTER TABLE team_cool_and_gang.internal_updates 
ALTER COLUMN datetime TYPE TIMESTAMP;
```

## Troubleshooting

### Connection Issues
- Verify database credentials in `.env` file
- Ensure PostgreSQL server is running and accessible
- Check firewall settings allow connection to database port
- Verify user has SELECT permission on source tables and INSERT permission on `internal_updates` table

### No Matches Found
- Lower the `FUZZY_MATCH_THRESHOLD` in `.env` (try 85 or 90)
- Verify the address includes a street number at the beginning
- Check that both tables have `MasterAddress` column populated
- Ensure the address format matches what's in the database

### Claude API Issues
- Verify `CLAUDE_API_KEY` is set correctly in `.env`
- Check you have sufficient API credits
- Review rate limits if making many requests

### Push Updates Fails
- Verify user has INSERT permission on `team_cool_and_gang.internal_updates` table
- Check that the table exists and has the required columns
- Review console logs for specific error messages

## Development Notes

- The system uses Claude Sonnet 4.5 for AI analysis
- Fuzzy matching uses rapidfuzz's `token_sort_ratio` algorithm
- Database queries use parameterized statements to prevent SQL injection
- The web interface automatically caches theme preference in localStorage
- All database operations use autocommit mode for read queries

## License

Developed for the Hack-AI-Thon OneTrueAddress project.
"""Module for connecting to and querying the golden source address table."""
import os
from typing import List, Dict, Any, Optional, Tuple
from config import (
    GOLDEN_SOURCE_DB_TYPE,
    GOLDEN_SOURCE_HOST,
    GOLDEN_SOURCE_PORT,
    GOLDEN_SOURCE_DATABASE,
    GOLDEN_SOURCE_USER,
    GOLDEN_SOURCE_PASSWORD,
    GOLDEN_SOURCE_TABLE,
    PINELLAS_TABLE
)


class GoldenSourceConnector:
    """Handles connection to the golden source address database."""
    
    def __init__(self):
        self.db_type = GOLDEN_SOURCE_DB_TYPE
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Establish connection to the database based on DB type."""
        if self.db_type.lower() == "postgresql":
            try:
                import psycopg2
            except ImportError:
                raise ImportError("psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary")
            
            # Validate that required credentials are provided
            if not GOLDEN_SOURCE_HOST:
                raise ValueError("GOLDEN_SOURCE_HOST environment variable is not set")
            if not GOLDEN_SOURCE_DATABASE:
                raise ValueError("GOLDEN_SOURCE_DATABASE environment variable is not set")
            if not GOLDEN_SOURCE_USER:
                raise ValueError("GOLDEN_SOURCE_USER environment variable is not set")
            if not GOLDEN_SOURCE_PASSWORD:
                raise ValueError("GOLDEN_SOURCE_PASSWORD environment variable is not set")
            
            try:
                self.connection = psycopg2.connect(
                    host=GOLDEN_SOURCE_HOST,
                    port=GOLDEN_SOURCE_PORT,
                    database=GOLDEN_SOURCE_DATABASE,
                    user=GOLDEN_SOURCE_USER,
                    password=GOLDEN_SOURCE_PASSWORD
                )
                # Enable autocommit mode for read-only queries to avoid transaction issues
                self.connection.autocommit = True
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                
                # Check if it's an OperationalError (connection/auth issues)
                if error_type == "OperationalError" or "OperationalError" in str(type(e)):
                    if "password authentication failed" in error_msg.lower():
                        raise ValueError(
                            f"PostgreSQL authentication failed for user '{GOLDEN_SOURCE_USER}'.\n"
                            f"Connection details: host={GOLDEN_SOURCE_HOST}, port={GOLDEN_SOURCE_PORT}, database={GOLDEN_SOURCE_DATABASE}\n"
                            f"Please verify:\n"
                            f"  1. The password in GOLDEN_SOURCE_PASSWORD is correct\n"
                            f"  2. The user '{GOLDEN_SOURCE_USER}' exists and has access to the database\n"
                            f"  3. The database server allows connections from your IP address\n"
                            f"  4. Check your .env file or environment variables\n"
                            f"\nOriginal error: {error_msg}"
                        )
                    elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
                        raise ValueError(
                            f"Could not connect to PostgreSQL server at {GOLDEN_SOURCE_HOST}:{GOLDEN_SOURCE_PORT}.\n"
                            f"Please verify:\n"
                            f"  1. The server is running and accessible\n"
                            f"  2. The host and port are correct\n"
                            f"  3. Your firewall allows connections to this server\n"
                            f"\nOriginal error: {error_msg}"
                        )
                    else:
                        raise ValueError(f"PostgreSQL connection error: {error_msg}")
                else:
                    raise ValueError(f"Failed to connect to PostgreSQL database: {error_msg}")
        elif self.db_type.lower() == "mysql":
            try:
                import mysql.connector
            except ImportError:
                raise ImportError("mysql-connector-python is required for MySQL. Install with: pip install mysql-connector-python")
            
            # Validate that required credentials are provided
            if not GOLDEN_SOURCE_HOST:
                raise ValueError("GOLDEN_SOURCE_HOST environment variable is not set")
            if not GOLDEN_SOURCE_DATABASE:
                raise ValueError("GOLDEN_SOURCE_DATABASE environment variable is not set")
            if not GOLDEN_SOURCE_USER:
                raise ValueError("GOLDEN_SOURCE_USER environment variable is not set")
            if not GOLDEN_SOURCE_PASSWORD:
                raise ValueError("GOLDEN_SOURCE_PASSWORD environment variable is not set")
            
            try:
                self.connection = mysql.connector.connect(
                    host=GOLDEN_SOURCE_HOST,
                    port=GOLDEN_SOURCE_PORT,
                    database=GOLDEN_SOURCE_DATABASE,
                    user=GOLDEN_SOURCE_USER,
                    password=GOLDEN_SOURCE_PASSWORD
                )
            except mysql.connector.Error as e:
                error_msg = str(e)
                if "access denied" in error_msg.lower() or "authentication" in error_msg.lower():
                    raise ValueError(
                        f"MySQL authentication failed for user '{GOLDEN_SOURCE_USER}'.\n"
                        f"Connection details: host={GOLDEN_SOURCE_HOST}, port={GOLDEN_SOURCE_PORT}, database={GOLDEN_SOURCE_DATABASE}\n"
                        f"Please verify your credentials in the .env file or environment variables.\n"
                        f"\nOriginal error: {error_msg}"
                    )
                else:
                    raise ValueError(f"MySQL connection error: {error_msg}")
            except Exception as e:
                raise ValueError(f"Failed to connect to MySQL database: {e}")
        elif self.db_type.lower() == "sqlite":
            try:
                import sqlite3
                self.connection = sqlite3.connect(GOLDEN_SOURCE_DATABASE)
            except ImportError:
                raise ImportError("sqlite3 should be included with Python")
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def get_all_addresses(self) -> List[Dict[str, Any]]:
        """Retrieve all addresses from the golden source table."""
        cursor = self.connection.cursor()
        
        # Parse schema and table name if schema-qualified
        table_parts = GOLDEN_SOURCE_TABLE.split('.')
        if len(table_parts) == 2:
            schema_name, table_name = table_parts
        else:
            schema_name = None
            table_name = GOLDEN_SOURCE_TABLE
        
        # Try to get column names first
        if self.db_type.lower() == "postgresql":
            if schema_name:
                # Handle schema-qualified table names
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema_name, table_name))
            else:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
            columns = [row[0] for row in cursor.fetchall()]
        elif self.db_type.lower() == "mysql":
            cursor.execute(f"DESCRIBE {GOLDEN_SOURCE_TABLE}")
            columns = [row[0] for row in cursor.fetchall()]
        else:  # sqlite
            cursor.execute(f"PRAGMA table_info({GOLDEN_SOURCE_TABLE})")
            columns = [row[1] for row in cursor.fetchall()]
        
        # Fetch all addresses - properly quote the table name
        if schema_name:
            # Use proper quoting for schema.table
            quoted_table = f'"{schema_name}"."{table_name}"'
        else:
            quoted_table = f'"{table_name}"'
        
        cursor.execute(f'SELECT * FROM {quoted_table}')
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        addresses = []
        for row in rows:
            address_dict = {columns[i]: row[i] for i in range(len(columns))}
            addresses.append(address_dict)
        
        cursor.close()
        return addresses
    
    def get_filtered_addresses(self, search_criteria: dict, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve filtered addresses from the golden source table based on search criteria.
        Only selects specific columns: address1, address2, Mailing City, state, zipcode
        
        Args:
            search_criteria: Dictionary with search terms (street_number, street_name, city, state, zip_code, search_terms)
            limit: Maximum number of addresses to return
            
        Returns:
            List of address dictionaries with only the specified columns
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Parse schema and table name if schema-qualified
            table_parts = GOLDEN_SOURCE_TABLE.split('.')
            if len(table_parts) == 2:
                schema_name, table_name = table_parts
                quoted_table = f'"{schema_name}"."{table_name}"'
            else:
                schema_name = None
                table_name = GOLDEN_SOURCE_TABLE
                quoted_table = f'"{table_name}"'
            
            # Define the specific columns we want to select
            target_columns = ['address1', 'address2', 'Mailing City', 'state', 'zipcode']
            quoted_columns = ', '.join([f'"{col}"' for col in target_columns])
            
            # Build WHERE clause based on search criteria
            # Logic: state AND city AND (street_name OR street_type in address1)
            # State and City use AND logic (must match)
            # Address1 searches (street_name, street_type) use OR logic
            
            params = []
            and_conditions = []
            address1_or_conditions = []
            
            # Filter by state (REQUIRED with AND logic)
            state = search_criteria.get("state")
            if state:
                and_conditions.append('"state"::text ILIKE %s')
                params.append(f'%{state}%')
            
            # Filter by city (REQUIRED with AND logic)
            city = search_criteria.get("city")
            if city:
                and_conditions.append('"Mailing City"::text ILIKE %s')
                params.append(f'%{city}%')
            
            # Filter by street_name (search in address1 with OR logic)
            street_name = search_criteria.get("street_name")
            if street_name:
                address1_or_conditions.append('"address1"::text ILIKE %s')
                params.append(f'%{street_name}%')
            
            # Filter by street_type (search in address1 with OR logic)
            street_type = search_criteria.get("street_type")
            if street_type:
                address1_or_conditions.append('"address1"::text ILIKE %s')
                params.append(f'%{street_type}%')
            
            # Build and execute query
            # Combine: state AND city AND (address1 OR conditions)
            where_parts = []
            
            # Add AND conditions (state, city)
            if and_conditions:
                where_parts.extend(and_conditions)
            
            # Add OR conditions for address1 (grouped with parentheses)
            if address1_or_conditions:
                if len(address1_or_conditions) > 1:
                    # Multiple address1 conditions - group them with OR
                    address1_clause = "(" + " OR ".join(address1_or_conditions) + ")"
                else:
                    # Single address1 condition - no need for parentheses
                    address1_clause = address1_or_conditions[0]
                where_parts.append(address1_clause)
            
            # Build final WHERE clause
            if where_parts:
                where_clause = " WHERE " + " AND ".join(where_parts)
                query = f'SELECT {quoted_columns} FROM {quoted_table}{where_clause} LIMIT {limit}'
            else:
                # If no criteria, return a small sample
                query = f'SELECT {quoted_columns} FROM {quoted_table} LIMIT {limit}'
            
            # Log the query for debugging
            print(f"\nDatabase Query Generated:")
            print(f"Query: {query}")
            print(f"Params: {params}")
            print("-" * 60)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries using the target columns
            addresses = []
            for row in rows:
                address_dict = {target_columns[i]: row[i] for i in range(len(target_columns))}
                addresses.append(address_dict)
            
            return addresses
            
        except Exception as e:
            # With autocommit enabled, we don't need rollback, but log the error
            error_msg = str(e)
            raise ValueError(f"Database query error: {error_msg}")
        finally:
            if cursor:
                cursor.close()
    
    def _get_pinellas_column_mapping(self, cursor, schema_name: Optional[str], table_name: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
        """
        Discover the column names in the Pinellas table and map them to standard address fields.
        
        Returns a tuple of:
        - Dictionary with keys: 'address', 'city', 'state', 'zip' (mapped to actual column names)
        - List of all column names in the table (in order)
        """
        # Get all column names from the Pinellas table
        if self.db_type.lower() == "postgresql":
            if schema_name:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema_name, table_name))
            else:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
            columns = [row[0] for row in cursor.fetchall()]
        elif self.db_type.lower() == "mysql":
            cursor.execute(f"DESCRIBE {PINELLAS_TABLE}")
            columns = [row[0] for row in cursor.fetchall()]
        else:  # sqlite
            cursor.execute(f"PRAGMA table_info({PINELLAS_TABLE})")
            columns = [row[1] for row in cursor.fetchall()]
        
        # Convert to lowercase for case-insensitive matching
        columns_lower = {col.lower(): col for col in columns}
        
        # Try to identify address-related columns
        mapping = {
            'address': None,
            'city': None,
            'state': None,
            'zip': None
        }
        
        # Look for address column (street address)
        address_patterns = ['address', 'street', 'addr', 'street_address', 'address1', 'address_1']
        for pattern in address_patterns:
            for col_lower, col_actual in columns_lower.items():
                if pattern in col_lower and mapping['address'] is None:
                    mapping['address'] = col_actual
                    break
            if mapping['address']:
                break
        
        # Look for city column
        city_patterns = ['city', 'mailing_city', 'mail_city', 'town']
        for pattern in city_patterns:
            for col_lower, col_actual in columns_lower.items():
                if pattern in col_lower and mapping['city'] is None:
                    mapping['city'] = col_actual
                    break
            if mapping['city']:
                break
        
        # Look for state column
        state_patterns = ['state', 'st', 'province']
        for pattern in state_patterns:
            for col_lower, col_actual in columns_lower.items():
                if col_lower == pattern or (pattern in col_lower and 'estate' not in col_lower):
                    if mapping['state'] is None:
                        mapping['state'] = col_actual
                        break
            if mapping['state']:
                break
        
        # Look for zip code column
        zip_patterns = ['zip', 'zipcode', 'zip_code', 'postal', 'postalcode', 'postal_code']
        for pattern in zip_patterns:
            for col_lower, col_actual in columns_lower.items():
                if pattern in col_lower and mapping['zip'] is None:
                    mapping['zip'] = col_actual
                    break
            if mapping['zip']:
                break
        
        print(f"\n[Pinellas Table Column Mapping]")
        print(f"  Available columns: {', '.join(columns)}")
        print(f"  Mapped columns:")
        print(f"    - Address field: {mapping['address']}")
        print(f"    - City field: {mapping['city']}")
        print(f"    - State field: {mapping['state']}")
        print(f"    - Zip field: {mapping['zip']}")
        
        return mapping, columns
    
    def get_pinellas_matches(self, golden_address: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query pinellas_fl_baddatascenarios table to find addresses matching the golden source address.
        Match criteria: street number AND street name (core, without type) AND state must match.
        This allows matching addresses with different street types (e.g., "LN" vs "Rd", "St" vs "Street").
        
        Args:
            golden_address: The matched address from golden_source table
            
        Returns:
            List of matching addresses from pinellas_fl_baddatascenarios table
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Parse schema and table name if schema-qualified
            table_parts = PINELLAS_TABLE.split('.')
            if len(table_parts) == 2:
                schema_name, table_name = table_parts
                quoted_table = f'"{schema_name}"."{table_name}"'
            else:
                schema_name = None
                table_name = PINELLAS_TABLE
                quoted_table = f'"{table_name}"'
            
            # Discover the column mapping for the Pinellas table
            column_mapping, all_columns = self._get_pinellas_column_mapping(cursor, schema_name, table_name)
            
            # Check if we found the required columns
            if not column_mapping['address']:
                print("  ⚠️  Warning: Could not identify address column in Pinellas table")
                return []
            if not column_mapping['state']:
                print("  ⚠️  Warning: Could not identify state column in Pinellas table")
                return []
            
            # Extract street number, street name, and state from golden address
            # The golden_address typically has fields like: address1, address2, Mailing City, state, zipcode
            address1 = golden_address.get('address1', '')
            state = golden_address.get('state', '')
            
            if not address1 or not state:
                return []
            
            # Extract street number and street name from address1
            # Typically address1 is in format like "123 Main St" or "456 Oak Avenue"
            import re
            
            # Common street type suffixes (abbreviations and full names)
            street_types = [
                'street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr',
                'lane', 'ln', 'court', 'ct', 'circle', 'cir', 'boulevard', 'blvd',
                'way', 'place', 'pl', 'terrace', 'ter', 'parkway', 'pkwy',
                'highway', 'hwy', 'trail', 'trl', 'plaza', 'plz', 'alley', 'aly',
                'loop', 'square', 'sq', 'crossing', 'xing', 'run', 'point', 'pt',
                'pike', 'row', 'path', 'walk', 'commons', 'green', 'crescent', 'cres'
            ]
            
            # Match pattern: street number at the start, followed by street name
            match = re.match(r'^(\d+)\s+(.+)$', str(address1).strip())
            
            if not match:
                # If no clear street number pattern, try to extract any number
                parts = str(address1).strip().split(None, 1)
                if len(parts) >= 2 and parts[0].isdigit():
                    street_number = parts[0]
                    street_name_full = parts[1]
                else:
                    # Can't extract street number, return empty
                    return []
            else:
                street_number = match.group(1)
                street_name_full = match.group(2)
            
            # Remove street type suffix from street name to allow matching across different types
            # e.g., "Village LN" becomes "Village", which can match "Village Rd", "Village Lane", etc.
            street_name_parts = street_name_full.strip().split()
            if len(street_name_parts) > 1:
                # Check if last word is a street type
                last_word = street_name_parts[-1].lower().rstrip('.')
                if last_word in street_types:
                    # Remove the street type suffix
                    street_name_core = ' '.join(street_name_parts[:-1])
                else:
                    # No recognized street type, use full name
                    street_name_core = street_name_full
            else:
                # Only one word, use as-is
                street_name_core = street_name_full
            
            print(f"\n[Pinellas Match Debug]")
            print(f"  Original address1: {address1}")
            print(f"  Extracted street number: {street_number}")
            print(f"  Full street name: {street_name_full}")
            print(f"  Core street name (without type): {street_name_core}")
            print(f"  State: {state}")
            
            # Build WHERE clause to match street number, street name, and state
            # Use the discovered column names from the mapping
            where_conditions = []
            params = []
            
            # Get the actual column names to use
            address_col = column_mapping['address']
            state_col = column_mapping['state']
            
            # Match street number in address column
            where_conditions.append(f'"{address_col}"::text ILIKE %s')
            params.append(f'{street_number}%')
            
            # Match core street name in address column (without street type for flexibility)
            where_conditions.append(f'"{address_col}"::text ILIKE %s')
            params.append(f'%{street_name_core}%')
            
            # Match state
            where_conditions.append(f'"{state_col}"::text ILIKE %s')
            params.append(state)
            
            # Combine with AND logic (all conditions must match)
            where_clause = " WHERE " + " AND ".join(where_conditions)
            
            # Execute query - select all columns
            query = f'SELECT * FROM {quoted_table}{where_clause}'
            
            # Log the query for debugging
            print(f"\nPinellas Query Generated:")
            print(f"Query: {query}")
            print(f"Params: {params}")
            print("-" * 60)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries using the column names we already discovered
            matches = []
            for row in rows:
                match_dict = {all_columns[i]: row[i] for i in range(len(all_columns))}
                matches.append(match_dict)
            
            print(f"  ✓ Found {len(matches)} matching address(es) in Pinellas table")
            
            return matches
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error querying Pinellas table: {error_msg}")
            # Return empty list instead of raising error to avoid breaking the main flow
            return []
        finally:
            if cursor:
                cursor.close()
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()


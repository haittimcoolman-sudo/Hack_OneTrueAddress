"""Module for connecting to and querying the golden source address table."""
import os
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz
from config import (
    GOLDEN_SOURCE_DB_TYPE,
    GOLDEN_SOURCE_HOST,
    GOLDEN_SOURCE_PORT,
    GOLDEN_SOURCE_DATABASE,
    GOLDEN_SOURCE_USER,
    GOLDEN_SOURCE_PASSWORD,
    GOLDEN_SOURCE_TABLE,
    GOLDEN_SOURCE_MATCH_TABLE,
    INTERNAL_MATCH_TABLE,
    FUZZY_MATCH_THRESHOLD
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
    
    def _get_internal_column_mapping(self, cursor, schema_name: Optional[str], table_name: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
        """
        Discover the column names in the Internal table and map them to standard address fields.
        
        Returns a tuple of:
        - Dictionary with keys: 'address', 'city', 'state', 'zip' (mapped to actual column names)
        - List of all column names in the table (in order)
        """
        # Get all column names from the Internal table
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
            cursor.execute(f"DESCRIBE {INTERNAL_MATCH_TABLE}")
            columns = [row[0] for row in cursor.fetchall()]
        else:  # sqlite
            cursor.execute(f"PRAGMA table_info({INTERNAL_MATCH_TABLE})")
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
        
        print(f"\n[Internal Table Column Mapping]")
        print(f"  Available columns: {', '.join(columns)}")
        print(f"  Mapped columns:")
        print(f"    - Address field: {mapping['address']}")
        print(f"    - City field: {mapping['city']}")
        print(f"    - State field: {mapping['state']}")
        print(f"    - Zip field: {mapping['zip']}")
        
        return mapping, columns
    
    def get_internal_matches(self, golden_address: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query internal table to find addresses matching the golden source address.
        Match criteria: street number AND street name (core, without type) AND state must match.
        This allows matching addresses with different street types (e.g., "LN" vs "Rd", "St" vs "Street").
        
        Args:
            golden_address: The matched address from golden_source table
            
        Returns:
            List of matching addresses from internal table
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Parse schema and table name if schema-qualified
            table_parts = INTERNAL_MATCH_TABLE.split('.')
            if len(table_parts) == 2:
                schema_name, table_name = table_parts
                quoted_table = f'"{schema_name}"."{table_name}"'
            else:
                schema_name = None
                table_name = INTERNAL_MATCH_TABLE
                quoted_table = f'"{table_name}"'
            
            # Discover the column mapping for the Internal table
            column_mapping, all_columns = self._get_internal_column_mapping(cursor, schema_name, table_name)
            
            # Check if we found the required columns
            if not column_mapping['address']:
                print("  ⚠️  Warning: Could not identify address column in Internal table")
                return []
            if not column_mapping['state']:
                print("  ⚠️  Warning: Could not identify state column in Internal table")
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
            
            print(f"\n[Internal Match Debug]")
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
            
            # Match EXACT street number in address column - must match exactly, not partially
            # Use regex to match street number followed by space or end of string
            where_conditions.append(f'"{address_col}"::text ~* %s')
            params.append(f'^{street_number}\\s')
            
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
            print(f"\nInternal Query Generated:")
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
            
            print(f"  ✓ Found {len(matches)} matching address(es) in Internal table")
            
            return matches
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error querying Internal table: {error_msg}")
            # Return empty list instead of raising error to avoid breaking the main flow
            return []
        finally:
            if cursor:
                cursor.close()
    
    def consolidate_internal_records(self, internal_matches: List[Dict[str, Any]], golden_source_address: Optional[Dict[str, Any]] = None, scenario: int = 1) -> Dict[str, Any]:
        """
        Consolidate multiple Internal records into a single record based on business rules.
        Address fields are taken from the Golden Source, while other fields follow the consolidation rules.
        
        Rules:
        1. Use address fields (address1, address2, City/Mailing City, state, zipcode) from Golden Source
        2. If there is a single address with an Active Customer, retain that record.
        3. If any addresses have Fiber Media, retain/update Fiber on the active customer record.
        4. If any addresses have Exclusion flag 'Y' or Engineering review 'Y', retain/update 'Y' flags.
        5. If no Active Customer but there is Fiber Media, retain the Fiber Media record.
        6. If multiple Active Customers or multiple Fiber Media records, return error for manual review.
        
        Args:
            internal_matches: List of address dictionaries from internal table
            golden_source_address: Optional Golden Source address to use for address fields
            scenario: Scenario identifier (1=Multiple Matches, 2=Single Match Mismatch, not used here but for consistency)
            
        Returns:
            Dictionary with 'status' and either 'consolidated_record' or 'error' message
        """
        if not internal_matches or len(internal_matches) == 0:
            return {"status": "error", "error": "No records to consolidate"}
        
        if len(internal_matches) == 1:
            consolidated_record = internal_matches[0].copy()
            
            # Apply Golden Source address even for single record
            if golden_source_address:
                print(f"\n[Single Record - Applying Golden Source Address]")
                
                golden_address_fields = {
                    'address1': golden_source_address.get('address1'),
                    'address2': golden_source_address.get('address2'),
                    'state': golden_source_address.get('state'),
                    'zipcode': golden_source_address.get('zipcode'),
                    'MasterAddress': golden_source_address.get('MasterAddress'),
                }
                
                city_value = golden_source_address.get('Mailing City') or golden_source_address.get('city')
                
                # Find the city column name in the consolidated record
                city_col = None
                for key in consolidated_record.keys():
                    key_lower = key.lower()
                    if 'city' in key_lower:
                        city_col = key
                        break
                
                # Update address fields in consolidated record
                # Define flexible matching patterns for each field
                field_patterns = {
                    'address1': ['address1', 'address_1', 'address 1', 'address', 'street', 'street address', 'street_address'],
                    'address2': ['address2', 'address_2', 'address 2', 'address line 2', 'address_line_2'],
                    'state': ['state', 'st'],
                    'zipcode': ['zipcode', 'zip_code', 'zip code', 'zip', 'postal', 'postalcode', 'postal_code'],
                    'MasterAddress': ['MasterAddress', 'master_address', 'master address']
                }
                
                for field_name, field_value in golden_address_fields.items():
                    if field_value is not None:
                        matching_col = None
                        patterns = field_patterns.get(field_name, [field_name])
                        
                        # Try to find matching column using various patterns
                        for col_name in consolidated_record.keys():
                            col_lower = col_name.lower().replace('_', ' ').strip()
                            for pattern in patterns:
                                pattern_normalized = pattern.lower().replace('_', ' ').strip()
                                if col_lower == pattern_normalized:
                                    matching_col = col_name
                                    break
                            if matching_col:
                                break
                        
                        if matching_col:
                            old_value = consolidated_record[matching_col]
                            consolidated_record[matching_col] = field_value
                            print(f"  Updated {matching_col}: '{old_value}' -> '{field_value}'")
                        else:
                            # Don't add new columns - only update existing ones
                            print(f"  ⚠️  Warning: No matching column found for '{field_name}' (value: '{field_value}') - skipping")
                            print(f"     Available columns: {list(consolidated_record.keys())}")
                
                # Update city field
                if city_value and city_col:
                    old_city = consolidated_record[city_col]
                    consolidated_record[city_col] = city_value
                    print(f"  Updated {city_col}: '{old_city}' -> '{city_value}'")
                elif city_value:
                    print(f"  ⚠️  Warning: No matching city column found (value: '{city_value}') - skipping")
                
                print(f"  ✓ Applied Golden Source address to single record")
            
            # Filter out metadata fields (starting with _) before returning
            filtered_consolidated_record = {k: v for k, v in consolidated_record.items() if not k.startswith('_')}
            if len(filtered_consolidated_record) < len(consolidated_record):
                removed_fields = [k for k in consolidated_record.keys() if k.startswith('_')]
                print(f"  Filtered out metadata fields from single record: {removed_fields}")
            
            return {"status": "success", "consolidated_record": filtered_consolidated_record, "message": "Single record, no consolidation needed"}
        
        # Identify records with Active Customer (assuming column names might vary)
        # Common column names: 'active_customer', 'Active Customer', 'ActiveCustomer', 'customer_status'
        active_customer_records = []
        fiber_media_records = []
        records_with_exclusion_y = []
        records_with_engineering_y = []
        
        # Try to identify column names dynamically
        sample_record = internal_matches[0]
        active_customer_col = None
        media_type_col = None
        exclusion_col = None
        engineering_col = None
        
        # Find the relevant columns (case-insensitive)
        for key in sample_record.keys():
            key_lower = key.lower()
            if 'active' in key_lower and 'customer' in key_lower:
                active_customer_col = key
            elif 'media' in key_lower or 'service' in key_lower:
                media_type_col = key
            elif 'exclusion' in key_lower:
                exclusion_col = key
            elif 'engineering' in key_lower and 'review' in key_lower:
                engineering_col = key
        
        print(f"\n[Consolidation Debug]")
        print(f"  Active Customer Column: {active_customer_col}")
        print(f"  Media Type Column: {media_type_col}")
        print(f"  Exclusion Column: {exclusion_col}")
        print(f"  Engineering Review Column: {engineering_col}")
        
        # Categorize records
        for record in internal_matches:
            # Check for active customer
            if active_customer_col and str(record.get(active_customer_col, '')).strip().upper() in ['Y', 'YES', 'TRUE', '1']:
                active_customer_records.append(record)
            
            # Check for Fiber Media
            if media_type_col and 'FIBER' in str(record.get(media_type_col, '')).upper():
                fiber_media_records.append(record)
            
            # Check for Exclusion flag Y
            if exclusion_col and str(record.get(exclusion_col, '')).strip().upper() in ['Y', 'YES', 'TRUE', '1']:
                records_with_exclusion_y.append(record)
            
            # Check for Engineering Review Y
            if engineering_col and str(record.get(engineering_col, '')).strip().upper() in ['Y', 'YES', 'TRUE', '1']:
                records_with_engineering_y.append(record)
        
        print(f"  Active Customer Records: {len(active_customer_records)}")
        print(f"  Fiber Media Records: {len(fiber_media_records)}")
        print(f"  Exclusion Y Records: {len(records_with_exclusion_y)}")
        print(f"  Engineering Review Y Records: {len(records_with_engineering_y)}")
        
        # Rule 5: If multiple Active Customers or multiple Fiber Media, prompt manual review
        if len(active_customer_records) > 1:
            return {
                "status": "error",
                "error": "Multiple Active Customer records found. Manual review required.",
                "requires_manual_review": True
            }
        
        if len(fiber_media_records) > 1:
            return {
                "status": "error",
                "error": "Multiple Fiber Media records found. Manual review required.",
                "requires_manual_review": True
            }
        
        # Start with the base record to consolidate
        consolidated_record = None
        
        # Rule 1: If there is a single Active Customer, use that as base
        if len(active_customer_records) == 1:
            consolidated_record = active_customer_records[0].copy()
            print(f"  Using Active Customer record as base")
            
            # Rule 2: If any address has Fiber Media, update the active customer record
            if fiber_media_records and media_type_col:
                fiber_value = fiber_media_records[0].get(media_type_col)
                # Update to Fiber if current is Copper
                if 'COPPER' in str(consolidated_record.get(media_type_col, '')).upper() or not consolidated_record.get(media_type_col):
                    consolidated_record[media_type_col] = fiber_value
                    print(f"  Updated Media Type to: {fiber_value}")
        
        # Rule 4: If no Active Customer but there is Fiber Media, use Fiber record as base
        elif fiber_media_records:
            consolidated_record = fiber_media_records[0].copy()
            print(f"  Using Fiber Media record as base")
        
        # If still no base record, use the first record
        if consolidated_record is None:
            consolidated_record = internal_matches[0].copy()
            print(f"  Using first record as base")
        
        # Rule 3: Update Exclusion and Engineering Review flags to 'Y' if any record has 'Y'
        if records_with_exclusion_y and exclusion_col:
            consolidated_record[exclusion_col] = 'Y'
            print(f"  Set Exclusion flag to: Y")
        elif exclusion_col and consolidated_record.get(exclusion_col) is None:
            consolidated_record[exclusion_col] = 'N'
        
        if records_with_engineering_y and engineering_col:
            consolidated_record[engineering_col] = 'Y'
            print(f"  Set Engineering Review flag to: Y")
        elif engineering_col and consolidated_record.get(engineering_col) is None:
            consolidated_record[engineering_col] = 'N'
        
        # Rule: Use address fields from Golden Source if provided
        if golden_source_address:
            print(f"\n  Applying Golden Source address fields to consolidated record...")
            
            # Define the address field mappings from Golden Source to Internal
            # Golden Source fields: address1, address2, Mailing City, state, zipcode
            # Internal fields may vary, but we'll try common mappings
            
            golden_address_fields = {
                'address1': golden_source_address.get('address1'),
                'address2': golden_source_address.get('address2'),
                'state': golden_source_address.get('state'),
                'zipcode': golden_source_address.get('zipcode'),
                'MasterAddress': golden_source_address.get('MasterAddress'),
            }
            
            # Handle city field which might be named differently
            city_value = golden_source_address.get('Mailing City') or golden_source_address.get('city')
            
            # Find the city column name in the consolidated record
            city_col = None
            for key in consolidated_record.keys():
                key_lower = key.lower()
                if 'city' in key_lower:
                    city_col = key
                    break
            
            # Update address fields in consolidated record
            # Define flexible matching patterns for each field
            field_patterns = {
                'address1': ['address1', 'address_1', 'address 1', 'address', 'street', 'street address', 'street_address'],
                'address2': ['address2', 'address_2', 'address 2', 'address line 2', 'address_line_2'],
                'state': ['state', 'st'],
                'zipcode': ['zipcode', 'zip_code', 'zip code', 'zip', 'postal', 'postalcode', 'postal_code'],
                'MasterAddress': ['MasterAddress', 'master_address', 'master address']
            }
            
            for field_name, field_value in golden_address_fields.items():
                if field_value is not None:
                    matching_col = None
                    patterns = field_patterns.get(field_name, [field_name])
                    
                    # Try to find matching column using various patterns
                    for col_name in consolidated_record.keys():
                        col_lower = col_name.lower().replace('_', ' ').strip()
                        for pattern in patterns:
                            pattern_normalized = pattern.lower().replace('_', ' ').strip()
                            if col_lower == pattern_normalized:
                                matching_col = col_name
                                break
                        if matching_col:
                            break
                    
                    if matching_col:
                        old_value = consolidated_record[matching_col]
                        consolidated_record[matching_col] = field_value
                        print(f"    Updated {matching_col}: '{old_value}' -> '{field_value}'")
                    else:
                        # Don't add new columns - only update existing ones
                        print(f"    ⚠️  Warning: No matching column found for '{field_name}' (value: '{field_value}') - skipping")
                        print(f"       Available columns: {list(consolidated_record.keys())}")
            
            # Update city field
            if city_value and city_col:
                old_city = consolidated_record[city_col]
                consolidated_record[city_col] = city_value
                print(f"    Updated {city_col}: '{old_city}' -> '{city_value}'")
            elif city_value:
                # Don't add new columns - only update existing ones
                print(f"    ⚠️  Warning: No matching city column found (value: '{city_value}') - skipping")
            
            print(f"  ✓ Successfully applied Golden Source address to consolidated record")
        
        # Filter out metadata fields (starting with _) before returning
        filtered_consolidated_record = {k: v for k, v in consolidated_record.items() if not k.startswith('_')}
        if len(filtered_consolidated_record) < len(consolidated_record):
            removed_fields = [k for k in consolidated_record.keys() if k.startswith('_')]
            print(f"  Filtered out metadata fields from consolidated record: {removed_fields}")
        
        return {
            "status": "success",
            "consolidated_record": filtered_consolidated_record,
            "message": f"Consolidated {len(internal_matches)} records successfully"
        }
    
    def _map_golden_source_to_internal(self, golden_source_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Golden Source column names to Internal table column names.
        
        Golden Source columns: address1, address2, Mailing City, state, zipcode
        Internal table columns: Address, City, State, Zipcode
        
        Args:
            golden_source_record: Record with Golden Source column names
            
        Returns:
            Record with Internal table column names
        """
        print(f"\n[Mapping Golden Source to Internal Schema]")
        print(f"  Input record keys: {list(golden_source_record.keys())}")
        
        # Filter out metadata fields (starting with _)
        filtered_record = {k: v for k, v in golden_source_record.items() if not k.startswith('_')}
        if len(filtered_record) < len(golden_source_record):
            removed_fields = [k for k in golden_source_record.keys() if k.startswith('_')]
            print(f"  Filtered out metadata fields: {removed_fields}")
        
        # Define the mapping from Golden Source to Internal column names
        column_mapping = {
            'address1': 'Address',
            'address2': 'Address 2',  # May or may not exist in internal table
            'Mailing City': 'City',
            'city': 'City',
            'state': 'State',
            'zipcode': 'Zipcode',
            'MasterAddress': 'MasterAddress'  # Keep same name in both tables
        }
        
        internal_record = {}
        
        for gs_col, gs_value in filtered_record.items():
            # Try to find the corresponding internal column name
            internal_col = column_mapping.get(gs_col)
            
            if internal_col:
                # Only add non-empty values
                if gs_value is not None and str(gs_value).strip() != '':
                    internal_record[internal_col] = gs_value
                    print(f"  Mapped '{gs_col}' -> '{internal_col}' = '{gs_value}'")
                else:
                    print(f"  Skipping '{gs_col}' (empty or None)")
            else:
                # Column doesn't have a mapping, check if it's already in internal format
                # (in case the record already has some internal column names)
                if gs_col in ['Address', 'City', 'State', 'Zipcode', 'MasterAddress', 'Media', 'Active Customer', 'Exclusion', 'Engineering Review']:
                    internal_record[gs_col] = gs_value
                    print(f"  Keeping '{gs_col}' = '{gs_value}' (already in internal format)")
                else:
                    print(f"  ⚠️  Warning: No mapping found for '{gs_col}' - skipping")
        
        print(f"  Output record keys: {list(internal_record.keys())}")
        print(f"  ✓ Mapping complete")
        
        return internal_record
    
    def push_to_internal_updates(self, consolidated_record: Dict[str, Any], scenario: int = 1) -> Dict[str, Any]:
        """
        Write a consolidated record to the team_cool_and_gang.internal_updates table.
        
        Automatically adds:
        - 'Agent Action': Description of the scenario
        - 'tpi': Task priority indicator (5, 10, or 20)
        - 'datetime': Current timestamp with date and time (TIMESTAMP type)
        
        Note: The 'datetime' column in the database should be TIMESTAMP or TIMESTAMPTZ type,
        not DATE, to store both date and time information.
        
        Args:
            consolidated_record: The consolidated address record to insert
            scenario: Scenario identifier (1=Multiple Matches, 2=Single Match Mismatch, 3=No Internal Match)
            
        Returns:
            Dictionary with 'status' and 'message' or 'error'
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Parse the internal_updates table name
            updates_table = "team_cool_and_gang.internal_updates"
            table_parts = updates_table.split('.')
            if len(table_parts) == 2:
                schema_name, table_name = table_parts
                quoted_table = f'"{schema_name}"."{table_name}"'
            else:
                table_name = updates_table
                quoted_table = f'"{table_name}"'
            
            # Filter out metadata fields (starting with _) before inserting
            filtered_record = {k: v for k, v in consolidated_record.items() if not k.startswith('_')}
            
            # Add Agent Action and tpi based on scenario
            scenario_mapping = {
                1: {
                    'Agent Action': 'Multiple Internal Matches (Consolidation Required)',
                    'tpi': 20
                },
                2: {
                    'Agent Action': 'Single Internal Match with MasterAddress Mismatch',
                    'tpi': 10
                },
                3: {
                    'Agent Action': 'No Internal Match (Golden Source Only)',
                    'tpi': 5
                }
            }
            
            scenario_data = scenario_mapping.get(scenario, scenario_mapping[1])
            filtered_record['Agent Action'] = scenario_data['Agent Action']
            filtered_record['tpi'] = scenario_data['tpi']
            
            # Add current datetime (includes both date and time)
            from datetime import datetime
            current_datetime = datetime.now()
            filtered_record['datetime'] = current_datetime
            
            print(f"\n[Scenario Metadata]")
            print(f"  Scenario: {scenario}")
            print(f"  Agent Action: {filtered_record['Agent Action']}")
            print(f"  tpi: {filtered_record['tpi']}")
            print(f"  datetime: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
            print(f"\n[Filtering Record for Insert]")
            print(f"  Original fields: {list(consolidated_record.keys())}")
            print(f"  Filtered fields: {list(filtered_record.keys())}")
            print(f"  Removed fields: {[k for k in consolidated_record.keys() if k.startswith('_')]}")
            
            # Build INSERT statement with filtered fields
            columns = list(filtered_record.keys())
            values = [filtered_record[col] for col in columns]
            
            # Create placeholders for parameterized query
            placeholders = ', '.join(['%s'] * len(columns))
            quoted_columns = ', '.join([f'"{col}"' for col in columns])
            
            insert_query = f'INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})'
            
            print(f"\n[Push to Internal Updates]")
            print(f"Query: {insert_query}")
            print(f"Values: {values[:5]}...")  # Show first 5 values for brevity
            
            cursor.execute(insert_query, values)
            
            # Commit the transaction
            if not self.connection.autocommit:
                self.connection.commit()
            
            print(f"  ✓ Successfully inserted record into {updates_table}")
            
            return {
                "status": "success",
                "message": f"Record successfully pushed to {updates_table}"
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ Error pushing to internal updates: {error_msg}")
            
            # Rollback on error
            if not self.connection.autocommit:
                try:
                    self.connection.rollback()
                except:
                    pass
            
            return {
                "status": "error",
                "error": f"Failed to push update: {error_msg}"
            }
        finally:
            if cursor:
                cursor.close()
    
    def fuzzy_match_addresses(self, input_address: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Perform fuzzy matching search on MasterAddress column in both Golden Source and Internal tables.
        Returns results separately for each table.
        
        Args:
            input_address: The address string to search for
            threshold: Minimum similarity score (0-100). Defaults to FUZZY_MATCH_THRESHOLD from config.
            
        Returns:
            Dictionary with 'golden_source_matches' and 'internal_matches', each containing list of matches
        """
        if threshold is None:
            threshold = FUZZY_MATCH_THRESHOLD
        
        # Enforce minimum threshold floor
        from config import FUZZY_MATCH_MIN_THRESHOLD
        if threshold < FUZZY_MATCH_MIN_THRESHOLD:
            print(f"⚠️  Warning: Threshold {threshold}% is below minimum. Adjusting to {FUZZY_MATCH_MIN_THRESHOLD}%")
            threshold = FUZZY_MATCH_MIN_THRESHOLD
        
        print(f"\n{'='*60}")
        print(f"FUZZY MATCH SEARCH")
        print(f"{'='*60}")
        print(f"Input Address: {input_address}")
        print(f"Similarity Threshold: {threshold}%")
        print(f"Searching in tables:")
        print(f"  1. Golden Source: {GOLDEN_SOURCE_MATCH_TABLE}")
        print(f"  2. Internal: {INTERNAL_MATCH_TABLE}")
        print(f"{'='*60}\n")
        
        # Search Golden Source table
        golden_source_matches = self._fuzzy_search_table(input_address, GOLDEN_SOURCE_MATCH_TABLE, threshold)
        for match in golden_source_matches:
            match['_source_table'] = GOLDEN_SOURCE_MATCH_TABLE
            match['_source_type'] = 'golden_source'
        
        # Search Internal table
        internal_matches = self._fuzzy_search_table(input_address, INTERNAL_MATCH_TABLE, threshold)
        for match in internal_matches:
            match['_source_table'] = INTERNAL_MATCH_TABLE
            match['_source_type'] = 'internal'
        
        # Sort each list by similarity score (highest first)
        golden_source_matches.sort(key=lambda x: x.get('_similarity_score', 0), reverse=True)
        internal_matches.sort(key=lambda x: x.get('_similarity_score', 0), reverse=True)
        
        print(f"\nFuzzy Match Results:")
        print(f"  Golden Source matches: {len(golden_source_matches)}")
        print(f"  Internal matches: {len(internal_matches)}")
        print(f"  Total matches: {len(golden_source_matches) + len(internal_matches)}")
        
        if golden_source_matches:
            print(f"\n  Top Golden Source matches:")
            print("-" * 80)
            for idx, match in enumerate(golden_source_matches[:5], 1):
                master_addr = match.get('MasterAddress', 'N/A')
                score = match.get('_similarity_score', 0)
                print(f"  {idx}. [{score:.1f}%] {master_addr}")
            print("-" * 80)
        
        if internal_matches:
            print(f"\n  Top Internal matches:")
            print("-" * 80)
            for idx, match in enumerate(internal_matches[:5], 1):
                master_addr = match.get('MasterAddress', 'N/A')
                score = match.get('_similarity_score', 0)
                print(f"  {idx}. [{score:.1f}%] {master_addr}")
            print("-" * 80)
        
        return {
            'golden_source_matches': golden_source_matches,
            'internal_matches': internal_matches,
            'total_matches': len(golden_source_matches) + len(internal_matches)
        }
    
    def _extract_street_number(self, address: str) -> Optional[str]:
        """
        Extract street number from an address string.
        
        Args:
            address: Address string to extract from
            
        Returns:
            Street number as string, or None if not found
        """
        import re
        # Match leading digits, possibly followed by letter (e.g., "123A")
        match = re.match(r'^(\d+[A-Za-z]?)', address.strip())
        if match:
            return match.group(1).upper()
        return None
    
    def _clean_address_for_fuzzy_match(self, address: str) -> str:
        """
        Clean address by removing zip code and state for fuzzy matching.
        
        Args:
            address: Address string to clean
            
        Returns:
            Cleaned address string
        """
        import re
        
        # Remove common state abbreviations (2 letter codes at the end)
        # Pattern: Remove state codes like "FL", "NY", "CA", etc.
        address = re.sub(r'\b[A-Z]{2}\b\s*$', '', address)
        address = re.sub(r',\s*[A-Z]{2}\b', '', address)
        
        # Remove zip codes (5 digits or 5+4 format)
        address = re.sub(r'\b\d{5}(-\d{4})?\b', '', address)
        
        # Remove extra whitespace and commas
        address = re.sub(r'\s+', ' ', address)
        address = re.sub(r',+', ',', address)
        address = address.strip(' ,')
        
        return address
    
    def _fuzzy_search_table(self, input_address: str, table_name: str, threshold: float) -> List[Dict[str, Any]]:
        """
        Search a single table for fuzzy matches on MasterAddress column.
        Street numbers must match exactly. Zip codes and states are removed before fuzzy matching.
        
        Args:
            input_address: The address string to search for
            table_name: Name of the table to search
            threshold: Minimum similarity score (0-100)
            
        Returns:
            List of matching address dictionaries with similarity scores
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Parse schema and table name if schema-qualified
            table_parts = table_name.split('.')
            if len(table_parts) == 2:
                schema_name, table_only = table_parts
                quoted_table = f'"{schema_name}"."{table_only}"'
            else:
                schema_name = None
                table_only = table_name
                quoted_table = f'"{table_only}"'
            
            # First, check if MasterAddress column exists in the table
            if self.db_type.lower() == "postgresql":
                if schema_name:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    """, (schema_name, table_only))
                else:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = %s
                        ORDER BY ordinal_position
                    """, (table_only,))
                columns = [row[0] for row in cursor.fetchall()]
            elif self.db_type.lower() == "mysql":
                cursor.execute(f"DESCRIBE {table_name}")
                columns = [row[0] for row in cursor.fetchall()]
            else:  # sqlite
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]
            
            # Check if MasterAddress exists
            if 'MasterAddress' not in columns:
                print(f"  ⚠️  Warning: MasterAddress column not found in {table_name}")
                print(f"     Available columns: {', '.join(columns)}")
                return []
            
            # Extract street number from input address
            input_street_number = self._extract_street_number(input_address)
            if not input_street_number:
                print(f"  ⚠️  Warning: Could not extract street number from input address: {input_address}")
                return []
            
            print(f"\n  Input street number: {input_street_number}")
            
            # Clean input address (remove zip and state)
            cleaned_input = self._clean_address_for_fuzzy_match(input_address)
            print(f"  Cleaned input address: {cleaned_input}")
            
            # Fetch all records with MasterAddress
            # We need to fetch all and do fuzzy matching in Python since SQL doesn't have built-in fuzzy matching
            query = f'SELECT * FROM {quoted_table} WHERE "MasterAddress" IS NOT NULL AND "MasterAddress" != \'\''
            
            print(f"\nQuerying {table_name}...")
            print(f"Query: {query}")
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            print(f"  Fetched {len(rows)} records with MasterAddress")
            
            # Perform fuzzy matching on each record
            matches = []
            street_number_matches = 0
            
            for row in rows:
                row_dict = {columns[i]: row[i] for i in range(len(columns))}
                master_address = str(row_dict.get('MasterAddress', '')).strip()
                
                if not master_address:
                    continue
                
                # Extract street number from master address
                master_street_number = self._extract_street_number(master_address)
                
                # Street numbers must match exactly
                if master_street_number != input_street_number:
                    continue
                
                street_number_matches += 1
                
                # Clean master address (remove zip and state)
                cleaned_master = self._clean_address_for_fuzzy_match(master_address)
                
                # Calculate similarity score using rapidfuzz on cleaned addresses
                # Using token_sort_ratio which handles word order differences
                similarity = fuzz.token_sort_ratio(cleaned_input.lower(), cleaned_master.lower())
                
                if similarity >= threshold:
                    row_dict['_similarity_score'] = similarity
                    row_dict['_cleaned_address'] = cleaned_master  # For debugging
                    matches.append(row_dict)
            
            print(f"  Records with matching street number ({input_street_number}): {street_number_matches}")
            print(f"  Found {len(matches)} matches above {threshold}% threshold (after fuzzy match)")
            
            return matches
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ Error searching {table_name}: {error_msg}")
            return []
        finally:
            if cursor:
                cursor.close()
    
    def get_time_saved(self) -> Dict[str, Any]:
        """
        Calculate the total time saved by the system based on tpi values in internal_updates table.
        
        Returns:
            Dictionary with 'hours_saved' (float) and 'status'
        """
        cursor = None
        try:
            cursor = self.connection.cursor()
            
            # Query to sum tpi values and convert to hours
            updates_table = "team_cool_and_gang.internal_updates"
            table_parts = updates_table.split('.')
            if len(table_parts) == 2:
                schema_name, table_name = table_parts
                quoted_table = f'"{schema_name}"."{table_name}"'
            else:
                table_name = updates_table
                quoted_table = f'"{table_name}"'
            
            query = f'SELECT COALESCE(SUM("tpi"), 0) / 60.0 FROM {quoted_table}'
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            hours_saved = float(result[0]) if result and result[0] is not None else 0.0
            
            return {
                'status': 'success',
                'hours_saved': round(hours_saved, 2)
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ Error getting time saved: {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
                'hours_saved': 0.0
            }
        finally:
            if cursor:
                cursor.close()
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()


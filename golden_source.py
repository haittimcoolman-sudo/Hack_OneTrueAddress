"""Module for connecting to and querying the golden source address table."""
import os
from typing import List, Dict, Any, Optional
from config import (
    GOLDEN_SOURCE_DB_TYPE,
    GOLDEN_SOURCE_HOST,
    GOLDEN_SOURCE_PORT,
    GOLDEN_SOURCE_DATABASE,
    GOLDEN_SOURCE_USER,
    GOLDEN_SOURCE_PASSWORD,
    GOLDEN_SOURCE_TABLE
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
                self.connection = psycopg2.connect(
                    host=GOLDEN_SOURCE_HOST,
                    port=GOLDEN_SOURCE_PORT,
                    database=GOLDEN_SOURCE_DATABASE,
                    user=GOLDEN_SOURCE_USER,
                    password=GOLDEN_SOURCE_PASSWORD
                )
            except ImportError:
                raise ImportError("psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary")
        elif self.db_type.lower() == "mysql":
            try:
                import mysql.connector
                self.connection = mysql.connector.connect(
                    host=GOLDEN_SOURCE_HOST,
                    port=GOLDEN_SOURCE_PORT,
                    database=GOLDEN_SOURCE_DATABASE,
                    user=GOLDEN_SOURCE_USER,
                    password=GOLDEN_SOURCE_PASSWORD
                )
            except ImportError:
                raise ImportError("mysql-connector-python is required for MySQL. Install with: pip install mysql-connector-python")
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
        Only selects specific columns: prefix, address1, address2, suffix, MailingCity, State, ZipCode
        
        Args:
            search_criteria: Dictionary with search terms (street_number, street_name, city, state, zip_code, search_terms)
            limit: Maximum number of addresses to return
            
        Returns:
            List of address dictionaries with only the specified columns
        """
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
        # Only filter using: street_name, street_type, city, and state
        # Use OR logic so any provided criteria can match (more flexible)
        where_conditions = []
        params = []
        
        # Filter by street_name (search in address1)
        street_name = search_criteria.get("street_name")
        if street_name:
            where_conditions.append('"address1"::text ILIKE %s')
            params.append(f'%{street_name}%')
        
        # Filter by street_type (search in address1)
        street_type = search_criteria.get("street_type")
        if street_type:
            where_conditions.append('"address1"::text ILIKE %s')
            params.append(f'%{street_type}%')
        
        # Filter by city (search in MailingCity)
        city = search_criteria.get("city")
        if city:
            where_conditions.append('"Mailing City"::text ILIKE %s')
            params.append(f'%{city}%')
        
        # Filter by state (search in State)
        state = search_criteria.get("state")
        if state:
            where_conditions.append('"state"::text ILIKE %s')
            params.append(f'%{state}%')
        
        # Build and execute query
        # Use OR logic so any provided criteria can match (more flexible than requiring all)
        if where_conditions:
            where_clause = " WHERE " + " OR ".join(where_conditions)
            query = f'SELECT {quoted_columns} FROM {quoted_table}{where_clause} LIMIT {limit}'
        else:
            # If no criteria, return a small sample
            query = f'SELECT {quoted_columns} FROM {quoted_table} LIMIT {limit}'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries using the target columns
        addresses = []
        for row in rows:
            address_dict = {target_columns[i]: row[i] for i in range(len(target_columns))}
            addresses.append(address_dict)
        
        cursor.close()
        return addresses
    
    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()


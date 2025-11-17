"""Module for interacting with Claude API."""
from typing import Optional
from anthropic import Anthropic
from config import CLAUDE_API_KEY


class ClaudeClient:
    """Handles interactions with Claude API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client with API key."""
        self.api_key = (api_key or CLAUDE_API_KEY).strip() if (api_key or CLAUDE_API_KEY) else None
        if not self.api_key:
            raise ValueError("Claude API key is required. Set CLAUDE_API_KEY environment variable.")
        # Validate API key format
        if not self.api_key.startswith("sk-ant-api"):
            raise ValueError(
                f"Invalid API key format. Claude API keys should start with 'sk-ant-api'. "
                f"Your key starts with: {self.api_key[:15]}..."
            )
        self.client = Anthropic(api_key=self.api_key)
    
    def extract_search_criteria(self, input_address: str) -> dict:
        """
        Use Claude to extract search criteria from an input address.
        This helps us filter the database before sending all addresses to Claude.
        
        Args:
            input_address: The free-form plain English address
            
        Returns:
            Dictionary containing extracted search criteria
        """
        prompt = f"""Extract searchable components from this address:
{input_address}

Return a JSON object with the following structure (use null for missing values):
{{
    "street_number": "123",
    "street_name": "Main",
    "street_type": "Street",
    "city": "New York",
    "state": "NY",
    "zip_code": "10001",
    "search_terms": ["main", "street", "new york", "ny", "10001"],
    "confidence": 95
}}

The search_terms array should contain normalized, lowercase search terms that could help find this address in a database.
Be flexible with variations - for example, "St" and "Street" should both be considered.

The confidence field should be a numeric value from 0-100 indicating how confident you are in the extracted components.
Higher values indicate more certainty that the components are correctly identified."""
        
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = message.content[0].text
            # Try to parse JSON from response
            import json
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"raw_response": response_text}
        except Exception as e:
            raise ValueError(f"Failed to extract search criteria: {e}")
    
    def find_address_match(self, input_address: str, address_table: list) -> tuple:
        """
        Ask Claude to find the exact match for an input address from the address table.
        
        Args:
            input_address: The free-form plain English address to match
            address_table: List of dictionaries containing addresses from golden source
            
        Returns:
            Tuple of (response_dict, prompt_string) where response_dict contains Claude's response
            and prompt_string is the full prompt that was sent to Claude
        """
        # Format the address table for Claude
        address_table_str = self._format_address_table(address_table)
        
        # Create the prompt
        prompt = f"""You are an expert at matching addresses. I will provide you with:
1. An input address (in free-form plain English)
2. A table of known good addresses (the golden source)

Your task is to find the EXACT match from the table that corresponds to the input address.

Input Address:
{input_address}

Golden Source Address Table:
{address_table_str}

Please analyze the input address and find the exact matching address from the table. 
If you find a match, return it in JSON format with the following structure:
{{
    "match_found": true,
    "matched_address": {{...all fields from the matched row...}},
    "confidence": 95,
    "reasoning": "brief explanation of why this is the match"
}}

If no exact match is found, return:
{{
    "match_found": false,
    "confidence": 0,
    "reasoning": "explanation of why no match was found"
}}

The confidence field should be a numeric value from 0-100 indicating how confident you are in the match.
- 90-100: Very high confidence, exact match
- 70-89: High confidence, very close match with minor variations
- 50-69: Medium confidence, similar but some differences
- 0-49: Low confidence, uncertain match or no match

Be very careful to match addresses exactly - consider variations in formatting, abbreviations, 
and minor spelling differences, but ensure the core address components match."""
        
        # Call Claude API
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
        except Exception as e:
            # Provide more detailed error information
            error_msg = str(e)
            if "401" in error_msg or "authentication" in error_msg.lower():
                raise ValueError(
                    f"Claude API authentication failed (401). "
                    f"Please check your API key. "
                    f"API key starts with: {self.api_key[:20] if self.api_key else 'None'}... "
                    f"Full error: {error_msg}"
                )
            raise
        
        # Extract the response
        response_text = message.content[0].text
        
        response_dict = {
            "response": response_text,
            "raw_message": message
        }
        
        return response_dict, prompt
    
    def _format_address_table(self, address_table: list) -> str:
        """Format the address table as a readable string for Claude.
        Only includes: address1, address2, Mailing City, state, zipcode"""
        if not address_table:
            return "No addresses in table."
        
        # Only include these specific columns in the prompt
        # Note: Column names must match what's returned from golden_source.py
        display_columns = ['address1', 'address2', 'Mailing City', 'state', 'zipcode']
        
        # Create header
        header = " | ".join(display_columns)
        separator = "-" * len(header)
        
        # Format rows
        rows = []
        for idx, address in enumerate(address_table, 1):
            row_values = [str(address.get(col, "")) for col in display_columns]
            row_str = " | ".join(row_values)
            rows.append(f"{idx}. {row_str}")
        
        return f"{header}\n{separator}\n" + "\n".join(rows)


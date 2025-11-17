"""Main agent module for OneTrueAddress - compares addresses using Claude."""
from typing import Dict, Any, Optional
from golden_source import GoldenSourceConnector
from claude_client import ClaudeClient
from config import CONFIDENCE_THRESHOLD
import json
import re


class AddressAgent:
    """Main agent that orchestrates address matching using Claude."""
    
    def __init__(self, claude_api_key: Optional[str] = None):
        """Initialize the address agent."""
        self.claude_client = ClaudeClient(claude_api_key)
        self.golden_source = GoldenSourceConnector()
    
    def match_address(self, input_address: str) -> Dict[str, Any]:
        """
        Match an input address against the golden source table using a two-step approach:
        1. Extract search criteria from input address using Claude
        2. Filter database to get candidate addresses
        3. Use Claude to find exact match from filtered candidates
        
        Args:
            input_address: Free-form plain English address to match
            
        Returns:
            Dictionary containing the match result
        """
        # Step 1: Extract search criteria from input address
        print("Step 1: Extracting search criteria from input address...")
        search_criteria = self.claude_client.extract_search_criteria(input_address)
        print(f"Extracted search criteria: {search_criteria}")
        
        # Log confidence from search criteria extraction
        extraction_confidence = search_criteria.get("confidence")
        if extraction_confidence is not None:
            print(f"Extraction Confidence: {extraction_confidence}%")
            if extraction_confidence < CONFIDENCE_THRESHOLD:
                print(f"⚠️  WARNING: Extraction confidence ({extraction_confidence}%) is below threshold ({CONFIDENCE_THRESHOLD}%)")
        else:
            print("⚠️  WARNING: No confidence value returned from extraction")
        
        # Step 2: Get filtered addresses from golden source
        print("\nStep 2: Querying database with search criteria...")
        address_table = self.golden_source.get_filtered_addresses(search_criteria, limit=50)
        print(f"\n{'='*60}")
        print(f"FILTERED SUBSET: {len(address_table)} records")
        print(f"{'='*60}")
        
        if address_table:
            print("\nAddresses in filtered subset:")
            print("-" * 60)
            for idx, addr in enumerate(address_table, 1):
                # Format address for display (show all fields)
                addr_str = " | ".join([f"{k}: {v}" for k, v in addr.items()])
                print(f"{idx}. {addr_str}")
            print("-" * 60)
        
        if not address_table:
            return {
                "input_address": input_address,
                "claude_response": {
                    "match_found": False,
                    "reasoning": "No candidate addresses found in database matching the search criteria."
                },
                "raw_response": "No addresses found",
                "candidates_searched": 0
            }
        
        # Step 3: Ask Claude to find the exact match from filtered candidates
        print(f"\nStep 3: Querying Claude to find exact match from {len(address_table)} candidates...")
        claude_response, final_prompt = self.claude_client.find_address_match(input_address, address_table)
        
        # Log the final prompt sent to Claude
        print(f"\n{'='*60}")
        print("FINAL PROMPT SENT TO CLAUDE:")
        print(f"{'='*60}")
        print(final_prompt)
        print(f"{'='*60}\n")
        
        # Try to parse JSON from Claude's response
        parsed_result = self._parse_claude_response(claude_response["response"])
        
        # Log confidence from matching
        match_confidence = parsed_result.get("confidence") if isinstance(parsed_result, dict) else None
        if match_confidence is not None:
            print(f"\n{'='*60}")
            print(f"MATCH CONFIDENCE: {match_confidence}%")
            print(f"{'='*60}")
            
            if match_confidence < CONFIDENCE_THRESHOLD:
                print(f"⚠️  BUSINESS RULE EXCEPTION: Confidence ({match_confidence}%) is below threshold ({CONFIDENCE_THRESHOLD}%)")
                print(f"⚠️  This match may require manual review.")
                parsed_result["business_rule_exception"] = True
                parsed_result["confidence_threshold"] = CONFIDENCE_THRESHOLD
            else:
                parsed_result["business_rule_exception"] = False
        else:
            print(f"\n{'='*60}")
            print("⚠️  WARNING: No confidence value returned from matching")
            print(f"{'='*60}")
            if isinstance(parsed_result, dict):
                parsed_result["business_rule_exception"] = True
                parsed_result["confidence_threshold"] = CONFIDENCE_THRESHOLD
        
        return {
            "input_address": input_address,
            "claude_response": parsed_result,
            "raw_response": claude_response["response"],
            "candidates_searched": len(address_table),
            "confidence_threshold": CONFIDENCE_THRESHOLD
        }
    
    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response, attempting to extract JSON if present."""
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # If no JSON found, return the raw text
        return {
            "raw_text": response_text,
            "note": "Could not parse JSON from Claude response"
        }
    
    def close(self):
        """Close connections and clean up resources."""
        self.golden_source.close()


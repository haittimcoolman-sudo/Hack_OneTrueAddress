"""Main agent module for OneTrueAddress - compares addresses using Claude."""
from typing import Dict, Any, Optional, List
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
    
    def _check_exact_match(self, golden_address: Dict[str, Any], internal_matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check if the Golden Source address exactly matches any of the Internal addresses.
        
        Args:
            golden_address: The matched address from golden_source
            internal_matches: List of internal addresses from Internal table
            
        Returns:
            Dictionary with 'is_exact_match' boolean and optional 'matched_record' if exact match found
        """
        if not internal_matches or len(internal_matches) == 0:
            return {"is_exact_match": False}
        
        # Extract the primary address fields from golden_address
        golden_addr1 = str(golden_address.get('address1', '')).strip().lower()
        golden_city = str(golden_address.get('Mailing City', '')).strip().lower()
        golden_state = str(golden_address.get('state', '')).strip().lower()
        golden_zip = str(golden_address.get('zipcode', '')).strip().lower()
        
        # Try to find the address field name in internal records
        if not internal_matches:
            return {"is_exact_match": False}
        
        sample_record = internal_matches[0]
        address_col = None
        city_col = None
        state_col = None
        zip_col = None
        
        # Find column names (case-insensitive)
        for key in sample_record.keys():
            key_lower = key.lower()
            if 'address' in key_lower or 'street' in key_lower:
                if address_col is None:
                    address_col = key
            elif 'city' in key_lower or 'town' in key_lower:
                if city_col is None:
                    city_col = key
            elif key_lower in ['state', 'st']:
                if state_col is None:
                    state_col = key
            elif 'zip' in key_lower or 'postal' in key_lower:
                if zip_col is None:
                    zip_col = key
        
        # Check each internal address for exact match
        for internal_record in internal_matches:
            internal_addr = str(internal_record.get(address_col, '')).strip().lower() if address_col else ''
            internal_city = str(internal_record.get(city_col, '')).strip().lower() if city_col else ''
            internal_state = str(internal_record.get(state_col, '')).strip().lower() if state_col else ''
            internal_zip = str(internal_record.get(zip_col, '')).strip().lower() if zip_col else ''
            
            # Check if all fields match exactly (case-insensitive)
            if (golden_addr1 == internal_addr and 
                golden_city == internal_city and 
                golden_state == internal_state and 
                golden_zip == internal_zip):
                return {
                    "is_exact_match": True,
                    "matched_record": internal_record
                }
        
        return {"is_exact_match": False}
    
    def match_address(self, input_address: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        """
        Match an input address using fuzzy matching on MasterAddress column
        in both internal tables.
        
        Args:
            input_address: Free-form plain English address to match
            threshold: Optional fuzzy match threshold (50-100). If None, uses default from config.
            
        Returns:
            Dictionary containing the match result with fuzzy match scores
        """
        # Perform fuzzy matching search
        print("Performing fuzzy match search on MasterAddress column...")
        match_results = self.golden_source.fuzzy_match_addresses(input_address, threshold=threshold)
        
        golden_source_matches = match_results.get('golden_source_matches', [])
        internal_matches = match_results.get('internal_matches', [])
        total_matches = match_results.get('total_matches', 0)
        
        # Check if we have NO matches at all
        if total_matches == 0:
            return {
                "input_address": input_address,
                "match_found": False,
                "golden_source_matches": [],
                "internal_matches": [],
                "reasoning": "No addresses found matching the search criteria with sufficient similarity in either table.",
                "candidates_searched": 0,
                "search_method": "fuzzy_match",
                "has_golden_source": False,
                "has_internal": False
            }
        
        # We have matches in at least one table
        # Get the best match overall (from whichever table has results)
        all_matches = golden_source_matches + internal_matches
        all_matches.sort(key=lambda x: x.get('_similarity_score', 0), reverse=True)
        
        # Send fuzzy results to Claude for review
        print(f"\n{'='*60}")
        print(f"SENDING FUZZY MATCHES TO CLAUDE FOR REVIEW")
        print(f"{'='*60}")
        print(f"Total matches to review: {len(all_matches)}")
        
        # Send matches to Claude for individual analysis
        claude_review = self._review_fuzzy_matches_with_claude(
            input_address, 
            all_matches[:10],  # Send top 10 matches
            golden_source_matches[:10],
            internal_matches[:10]
        )
        
        # Add individual AI analysis to each match
        match_analyses = claude_review.get('match_analyses', {})
        print(f"\n[Attaching AI analyses to matches]")
        print(f"  Total analyses available: {len(match_analyses)}")
        print(f"  Analysis keys: {list(match_analyses.keys())}")
        
        gs_analyses_attached = 0
        for idx, match in enumerate(golden_source_matches[:10]):
            analysis_key = f"gs_{idx}"
            if analysis_key in match_analyses:
                match['_ai_analysis'] = match_analyses[analysis_key]
                gs_analyses_attached += 1
                print(f"  ✓ Attached AI analysis to Golden Source match {idx+1}")
        print(f"  Golden Source: {gs_analyses_attached}/{len(golden_source_matches[:10])} analyses attached")
        
        int_analyses_attached = 0
        for idx, match in enumerate(internal_matches[:10]):
            analysis_key = f"int_{idx}"
            if analysis_key in match_analyses:
                match['_ai_analysis'] = match_analyses[analysis_key]
                int_analyses_attached += 1
                print(f"  ✓ Attached AI analysis to Internal match {idx+1}")
        print(f"  Internal: {int_analyses_attached}/{len(internal_matches[:10])} analyses attached")
        
        # Get Claude's recommended best match or use fuzzy match result
        if claude_review.get('match_found'):
            best_match = claude_review.get('best_match', all_matches[0])
            best_score = claude_review.get('confidence', all_matches[0].get('_similarity_score', 0))
            claude_reasoning = claude_review.get('reasoning', 'Claude reviewed and confirmed the match')
        else:
            best_match = all_matches[0]
            best_score = best_match.get('_similarity_score', 0)
            claude_reasoning = claude_review.get('reasoning', 'Fuzzy match result')
        
        # Determine which table has the best match
        best_match_source = best_match.get('_source_type', 'unknown')
        best_match_table = best_match.get('_source_table', 'Unknown')
        
        print(f"\n{'='*60}")
        print(f"BEST MATCH (AFTER CLAUDE REVIEW)")
        print(f"{'='*60}")
        print(f"Similarity Score: {best_score:.2f}%")
        print(f"MasterAddress: {best_match.get('MasterAddress', 'N/A')}")
        print(f"Source: {best_match_source.upper()}")
        print(f"Table: {best_match_table}")
        print(f"Claude's Reasoning: {claude_reasoning}")
        print(f"{'='*60}\n")
        
        # Log table status
        if not golden_source_matches:
            print("ℹ️  No matches found in Golden Source table")
        if not internal_matches:
            print("ℹ️  No matches found in Internal table")
        
        # Determine if this is a high-confidence match
        from config import FUZZY_MATCH_THRESHOLD
        business_rule_exception = best_score < FUZZY_MATCH_THRESHOLD
        
        if business_rule_exception:
            print(f"⚠️  BUSINESS RULE EXCEPTION: Similarity score ({best_score:.2f}%) is below threshold ({FUZZY_MATCH_THRESHOLD}%)")
            print(f"⚠️  This match may require manual review.")
        else:
            print(f"✓ High confidence match: {best_score:.2f}% >= {FUZZY_MATCH_THRESHOLD}%")
        
        return {
            "input_address": input_address,
            "match_found": True,
            "best_match": best_match,
            "golden_source_matches": golden_source_matches,
            "internal_matches": internal_matches,
            "has_golden_source": len(golden_source_matches) > 0,
            "has_internal": len(internal_matches) > 0,
            "similarity_score": best_score,
            "confidence": best_score,  # For compatibility with existing UI
            "reasoning": claude_reasoning,
            "claude_review": claude_review,
            "business_rule_exception": business_rule_exception,
            "confidence_threshold": FUZZY_MATCH_THRESHOLD,
            "candidates_searched": total_matches,
            "search_method": "fuzzy_match_with_ai",
            "matched_address": best_match  # For compatibility with existing code
        }
    
    def _review_fuzzy_matches_with_claude(
        self, 
        input_address: str, 
        all_matches: List[Dict[str, Any]],
        golden_source_matches: List[Dict[str, Any]],
        internal_matches: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Send fuzzy match results to Claude for AI-powered review and validation.
        
        Args:
            input_address: The original input address
            all_matches: Combined list of top matches from both tables
            golden_source_matches: Top matches from Golden Source
            internal_matches: Top matches from Internal table
            
        Returns:
            Dictionary with Claude's review, including best match recommendation and reasoning
        """
        try:
            # Format matches for Claude - send Golden Source and Internal separately for clarity
            gs_matches_summary = []
            for idx, match in enumerate(golden_source_matches, 1):
                score = match.get('_similarity_score', 0)
                master_addr = match.get('MasterAddress', 'N/A')
                gs_matches_summary.append(f"GS-{idx}. [{score:.1f}%] {master_addr}")
            
            int_matches_summary = []
            for idx, match in enumerate(internal_matches, 1):
                score = match.get('_similarity_score', 0)
                master_addr = match.get('MasterAddress', 'N/A')
                int_matches_summary.append(f"INT-{idx}. [{score:.1f}%] {master_addr}")
            
            gs_section = f"GOLDEN SOURCE MATCHES:\n{chr(10).join(gs_matches_summary)}" if gs_matches_summary else "GOLDEN SOURCE MATCHES:\nNone"
            int_section = f"INTERNAL MATCHES:\n{chr(10).join(int_matches_summary)}" if int_matches_summary else "INTERNAL MATCHES:\nNone"
            
            prompt = f"""You are an address matching expert. Review these fuzzy match results and provide detailed analysis FOR EVERY SINGLE MATCH.

INPUT ADDRESS:
{input_address}

{gs_section}

{int_section}

CRITICAL TASK:
1. You MUST analyze EVERY match listed above individually (1-2 sentences each)
2. For each match, provide an assessment and confidence score
3. Determine which is the overall best match
4. Consider ONLY: street number, street name, city, and state
5. DO NOT consider zip codes in your analysis - they were already normalized before matching
6. In your assessments, DO NOT use labels like "GS-1" or "INT-1" - just describe the address directly (e.g., "This address matches perfectly" not "GS-1 matches perfectly")

Return your analysis in JSON format with analysis for EVERY match:
{{
    "match_found": true/false,
    "best_match_source": "golden_source" or "internal",
    "best_match_index": 1-based index within that source,
    "confidence": 0-100,
    "reasoning": "Why this is the best overall match",
    "concerns": "Any concerns (or null)",
    "golden_source_analyses": {{
        "1": {{"assessment": "Analysis of GS-1", "confidence": 0-100}},
        "2": {{"assessment": "Analysis of GS-2", "confidence": 0-100}},
        ... (include ALL Golden Source matches)
    }},
    "internal_analyses": {{
        "1": {{"assessment": "Analysis of INT-1", "confidence": 0-100}},
        "2": {{"assessment": "Analysis of INT-2", "confidence": 0-100}},
        ... (include ALL Internal matches)
    }}
}}"""

            print(f"\n[Sending to Claude for Review]")
            print(f"Prompt length: {len(prompt)} characters")
            print(f"\n--- PROMPT START ---")
            print(prompt)
            print(f"--- PROMPT END ---\n")
            
            # Call Claude API directly with our custom prompt
            message = self.claude_client.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract the response
            response_text = message.content[0].text
            print(f"\n[Raw Claude Response]")
            print(f"{response_text[:500]}..." if len(response_text) > 500 else response_text)
            
            parsed_response = self._parse_claude_response(response_text)
            
            print(f"[Claude Review Received]")
            print(f"Response: {parsed_response}")
            
            # Extract Claude's recommended match
            if isinstance(parsed_response, dict):
                # Determine best match from Claude's response
                best_match_source = parsed_response.get('best_match_source', 'golden_source')
                best_match_index = parsed_response.get('best_match_index', 1) - 1  # Convert to 0-based
                
                if best_match_source == 'golden_source' and 0 <= best_match_index < len(golden_source_matches):
                    recommended_match = golden_source_matches[best_match_index]
                elif best_match_source == 'internal' and 0 <= best_match_index < len(internal_matches):
                    recommended_match = internal_matches[best_match_index]
                elif len(all_matches) > 0:
                    recommended_match = all_matches[0]
                else:
                    recommended_match = {}
                
                # Process analyses for both sources
                converted_analyses = {}
                
                # Process Golden Source analyses
                gs_analyses = parsed_response.get('golden_source_analyses', {})
                print(f"  Golden Source analyses received: {len(gs_analyses)} analyses")
                for idx_str, analysis in gs_analyses.items():
                    try:
                        idx = int(idx_str) - 1  # Convert to 0-based
                        converted_analyses[f"gs_{idx}"] = analysis
                        print(f"    GS-{idx}: confidence={analysis.get('confidence', 'N/A')}%")
                    except ValueError:
                        continue
                
                # Process Internal analyses
                int_analyses = parsed_response.get('internal_analyses', {})
                print(f"  Internal analyses received: {len(int_analyses)} analyses")
                for idx_str, analysis in int_analyses.items():
                    try:
                        idx = int(idx_str) - 1  # Convert to 0-based
                        converted_analyses[f"int_{idx}"] = analysis
                        print(f"    INT-{idx}: confidence={analysis.get('confidence', 'N/A')}%")
                    except ValueError:
                        continue
                
                print(f"  Total converted analyses: {len(converted_analyses)}")
                
                return {
                    "match_found": parsed_response.get('match_found', True),
                    "best_match": recommended_match,
                    "confidence": parsed_response.get('confidence', all_matches[0].get('_similarity_score', 0) if all_matches else 0),
                    "reasoning": parsed_response.get('reasoning', 'Claude reviewed the matches'),
                    "concerns": parsed_response.get('concerns'),
                    "fuzzy_score": all_matches[0].get('_similarity_score', 0) if all_matches else 0,
                    "match_analyses": converted_analyses
                }
            else:
                # If Claude's response can't be parsed, fall back to fuzzy match result
                return {
                    "match_found": True,
                    "best_match": all_matches[0],
                    "confidence": all_matches[0].get('_similarity_score', 0),
                    "reasoning": "Using fuzzy match result (Claude review unavailable)",
                    "concerns": None,
                    "fuzzy_score": all_matches[0].get('_similarity_score', 0),
                    "match_analyses": {}
                }
                
        except Exception as e:
            print(f"⚠️  Error during Claude review: {e}")
            # Fall back to fuzzy match result
            return {
                "match_found": True,
                "best_match": all_matches[0],
                "confidence": all_matches[0].get('_similarity_score', 0),
                "reasoning": f"Using fuzzy match result (Claude review failed: {str(e)})",
                "concerns": None,
                "fuzzy_score": all_matches[0].get('_similarity_score', 0),
                "match_analyses": {}
            }
    
    def _parse_claude_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Claude's response, attempting to extract JSON if present."""
        # First, try to parse the entire response as JSON
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON code blocks (```json ... ```)
        json_code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_code_block:
            try:
                return json.loads(json_code_block.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find any JSON object in the text (using a bracket counting approach for nested objects)
        start_idx = response_text.find('{')
        if start_idx != -1:
            bracket_count = 0
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(response_text)):
                char = response_text[i]
                
                if escape_next:
                    escape_next = False
                    continue
                    
                if char == '\\':
                    escape_next = True
                    continue
                    
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found complete JSON object
                            json_str = response_text[start_idx:i+1]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError as e:
                                print(f"  JSON parse error: {e}")
                                break
        
        # If no JSON found, return the raw text
        return {
            "raw_text": response_text,
            "note": "Could not parse JSON from Claude response"
        }
    
    def close(self):
        """Close connections and clean up resources."""
        self.golden_source.close()


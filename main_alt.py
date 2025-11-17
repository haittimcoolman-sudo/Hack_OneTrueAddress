"""Main entry point for OneTrueAddress agent - Alternative Table Version."""
import sys
import os
from address_agent import AddressAgent


def main():
    """Main function to run the address matching agent with alternative table."""
    # Check for minimum arguments (at least the address)
    if len(sys.argv) < 2:
        print("Usage: python main_alt.py '<address to match>' [table_name]")
        print("\nExample:")
        print("  python main_alt.py '123 Main St, New York, NY 10001'")
        print("  python main_alt.py '123 Main St, New York, NY 10001' 'public.addresses_backup'")
        print("\nNote: If no table_name is provided, uses GOLDEN_SOURCE_TABLE_ALT environment variable")
        print("      or defaults to 'addresses_backup'")
        sys.exit(1)
    
    # Parse arguments
    # Last argument might be table name if it looks like a table reference
    # (contains a dot for schema.table or ends with certain keywords)
    if len(sys.argv) >= 3:
        potential_table = sys.argv[-1]
        # Check if last argument looks like a table name
        if '.' in potential_table or any(keyword in potential_table.lower() 
                                        for keyword in ['addresses', 'table', 'backup', '_alt']):
            table_name = potential_table
            input_address = " ".join(sys.argv[1:-1])
        else:
            # All arguments are part of the address
            input_address = " ".join(sys.argv[1:])
            table_name = None
    else:
        input_address = sys.argv[1]
        table_name = None
    
    # Determine which table to use
    if table_name:
        # Use provided table name
        pass
    elif os.getenv("GOLDEN_SOURCE_TABLE_ALT"):
        # Use alternative table from environment variable
        table_name = os.getenv("GOLDEN_SOURCE_TABLE_ALT")
    else:
        # Default to addresses_backup
        table_name = "addresses_backup"
    
    # Override the environment variable for this run
    os.environ["GOLDEN_SOURCE_TABLE"] = table_name
    
    print("=" * 60)
    print("OneTrueAddress Agent - Address Matching (Alternative Table)")
    print("=" * 60)
    print(f"Using Table: {table_name}")
    print()
    
    # Initialize and run the agent
    agent = AddressAgent()
    
    try:
        result = agent.match_address(input_address)
        
        print("\n" + "=" * 60)
        print("MATCH RESULT")
        print("=" * 60)
        print(f"\nInput Address: {result['input_address']}")
        if 'candidates_searched' in result:
            print(f"Candidates Searched: {result['candidates_searched']}")
        print("\nClaude's Analysis:")
        print("-" * 60)
        
        if isinstance(result['claude_response'], dict):
            confidence = result['claude_response'].get('confidence', 'N/A')
            business_rule_exception = result['claude_response'].get('business_rule_exception', False)
            confidence_threshold = result.get('confidence_threshold', 90.0)
            
            if result['claude_response'].get('match_found'):
                print("✓ Match Found!")
                print(f"Confidence: {confidence}%")
                if business_rule_exception:
                    print(f"⚠️  BUSINESS RULE EXCEPTION: Confidence below threshold ({confidence_threshold}%)")
                    print(f"⚠️  This match requires manual review.")
                print(f"\nMatched Address:")
                matched = result['claude_response'].get('matched_address', {})
                for key, value in matched.items():
                    print(f"  {key}: {value}")
                print(f"\nReasoning: {result['claude_response'].get('reasoning', 'N/A')}")
            else:
                print("✗ No Match Found")
                if confidence != 'N/A' and isinstance(confidence, (int, float)):
                    print(f"Confidence: {confidence}%")
                print(f"Reasoning: {result['claude_response'].get('reasoning', 'N/A')}")
        else:
            print(result['raw_response'])
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        agent.close()


if __name__ == "__main__":
    main()


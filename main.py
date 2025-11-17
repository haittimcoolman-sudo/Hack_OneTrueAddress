"""Main entry point for OneTrueAddress agent."""
import sys
from address_agent import AddressAgent


def main():
    """Main function to run the address matching agent."""
    if len(sys.argv) < 2:
        print("Usage: python main.py '<address to match>'")
        print("\nExample:")
        print("  python main.py '123 Main St, New York, NY 10001'")
        sys.exit(1)
    
    # Get the input address from command line arguments
    input_address = " ".join(sys.argv[1:])
    
    print("=" * 60)
    print("OneTrueAddress Agent - Address Matching")
    print("=" * 60)
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


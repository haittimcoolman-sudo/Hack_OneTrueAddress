"""Simple test script to verify Claude API connection."""
from config import CLAUDE_API_KEY
from anthropic import Anthropic

print("Testing Claude API Connection...")
print("=" * 60)

# Check if API key is loaded
if not CLAUDE_API_KEY:
    print("ERROR: CLAUDE_API_KEY is not set or empty")
    exit(1)

print(f"API Key loaded: {CLAUDE_API_KEY[:20]}...{CLAUDE_API_KEY[-10:]}")
print(f"API Key length: {len(CLAUDE_API_KEY)} characters")

# Try to create client
try:
    client = Anthropic(api_key=CLAUDE_API_KEY)
    print("✓ Anthropic client created successfully")
except Exception as e:
    print(f"✗ Failed to create Anthropic client: {e}")
    exit(1)

# Try a simple API call
try:
    print("\nTesting API call...")
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": "Say 'Hello'"
            }
        ]
    )
    print("✓ API call successful!")
    print(f"Response: {message.content[0].text}")
except Exception as e:
    print(f"✗ API call failed: {e}")
    if "401" in str(e):
        print("\n401 Error indicates authentication failure.")
        print("Possible causes:")
        print("  1. API key is invalid or expired")
        print("  2. API key has extra whitespace or characters")
        print("  3. API key doesn't have proper permissions")
    exit(1)

print("\n" + "=" * 60)
print("All tests passed!")


"""Quick test to verify custom API endpoint configuration."""

import os
import sys
from dotenv import load_dotenv

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables
load_dotenv()

print("=" * 60)
print("Custom API Configuration Test")
print("=" * 60)
print()

# Check environment variables
api_key = os.getenv('ANTHROPIC_API_KEY')
base_url = os.getenv('ANTHROPIC_BASE_URL')

print("Configuration:")
print(f"  API Key: {api_key[:20]}..." if api_key else "  API Key: NOT SET")
print(f"  Base URL: {base_url}" if base_url else "  Base URL: Using default Anthropic endpoint")
print()

# Test API connection
print("Testing API connection...")
try:
    from anthropic import Anthropic

    if base_url:
        client = Anthropic(base_url=base_url)
        print(f"  [OK] Using custom endpoint: {base_url}")
    else:
        client = Anthropic()
        print(f"  [OK] Using default Anthropic endpoint")

    print("  Sending test request...")
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": "Say 'API connection successful!' and nothing else."
        }]
    )

    print(f"  [OK] Response: {response.content[0].text}")
    print()
    print("=" * 60)
    print("SUCCESS! Your custom API is configured correctly!")
    print("=" * 60)
    print()
    print("You can now run the Pokemon AI Agent:")
    print("  python main.py")
    print()

except Exception as e:
    print(f"  [ERROR] {e}")
    print()
    print("=" * 60)
    print("FAILED! Please check your configuration.")
    print("=" * 60)
    print()
    print("Troubleshooting:")
    print("  1. Verify your API key is correct")
    print("  2. Verify the base URL is correct")
    print("  3. Check if the API endpoint is accessible")
    print("  4. Ensure the model name is supported by your API")
    print()

"""Test script for validating Pokemon AI Agent setup."""

import os
import sys
from pathlib import Path


def test_python_version():
    """Test Python version."""
    print("Testing Python version...", end=" ")
    if sys.version_info < (3, 9):
        print("FAIL")
        print(f"  Python 3.9+ required, found {sys.version}")
        return False
    print("OK")
    return True


def test_dependencies():
    """Test required dependencies."""
    print("Testing dependencies...")

    required_packages = [
        'pyboy',
        'PIL',
        'numpy',
        'yaml',
        'colorlog'
    ]

    all_ok = True

    for package in required_packages:
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'yaml':
                __import__('yaml')
            else:
                __import__(package)
            print(f"  {package}: OK")
        except ImportError:
            print(f"  {package}: FAIL - not installed")
            all_ok = False

    return all_ok


def test_api_key():
    """Test AI API configuration."""
    print("Testing API key...", end=" ")

    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('AI_API_KEY')
    base_url = os.getenv('AI_BASE_URL')
    model = os.getenv('AI_MODEL')

    if not api_key:
        print("FAIL")
        print("  AI_API_KEY environment variable not set")
        return False

    if api_key == 'your-api-key-here':
        print("FAIL")
        print("  API key is still the placeholder value")
        return False

    if len(api_key) < 20:
        print("WARN")
        print("  API key seems too short")
        return False

    if not base_url:
        print("FAIL")
        print("  AI_BASE_URL environment variable not set")
        return False

    if not model:
        print("FAIL")
        print("  AI_MODEL environment variable not set")
        return False

    print("OK")
    print(f"  Using endpoint: {base_url}")
    return True


def test_rom():
    """Test ROM file."""
    print("Testing ROM file...", end=" ")

    if not Path('PokemonRed.gb').exists():
        print("FAIL")
        print("  PokemonRed.gb not found in current directory")
        return False

    file_size = Path('PokemonRed.gb').stat().st_size

    if file_size != 1048576:  # 1MB
        print("WARN")
        print(f"  ROM file size is {file_size} bytes, expected 1048576")
        print("  This may still work, but verify it's a valid Pokemon Red ROM")

    print("OK")
    return True


def test_config():
    """Test configuration file."""
    print("Testing configuration...", end=" ")

    if not Path('config.yaml').exists():
        print("FAIL")
        print("  config.yaml not found")
        return False

    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        required_sections = ['game', 'ai', 'memory', 'actions', 'logging']
        for section in required_sections:
            if section not in config:
                print("FAIL")
                print(f"  Missing required section: {section}")
                return False

        print("OK")
        return True

    except Exception as e:
        print("FAIL")
        print(f"  Error loading config: {e}")
        return False


def test_directories():
    """Test required directories."""
    print("Testing directories...", end=" ")

    required_dirs = [
        'src',
        'src/emulator',
        'src/state',
        'src/agents',
        'src/memory',
        'src/tools',
        'src/utils',
        'data',
    ]

    all_ok = True

    for directory in required_dirs:
        if not Path(directory).exists():
            print("FAIL")
            print(f"  Missing directory: {directory}")
            all_ok = False

    if all_ok:
        print("OK")

    return all_ok


def test_api_connection():
    """Test API connection using configured endpoint."""
    print("Testing API connection...", end=" ")

    try:
        from src.utils.ai_client import AIClient
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv('AI_API_KEY')
        base_url = os.getenv('AI_BASE_URL')
        model = os.getenv('AI_MODEL')

        if not model:
            print("FAIL")
            print("  AI_MODEL environment variable not set")
            return False

        if not base_url:
            print("FAIL")
            print("  AI_BASE_URL environment variable not set")
            return False

        client = AIClient(api_key=api_key, base_url=base_url)

        # Try a minimal API call
        client.create_message(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
        )

        print("OK")
        if base_url:
            print(f"  Connected to: {base_url}")
        return True

    except Exception as e:
        print("FAIL")
        print(f"  {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Pokemon AI Agent - Setup Test")
    print("=" * 60)
    print()

    tests = [
        ("Python Version", test_python_version),
        ("Dependencies", test_dependencies),
        ("API Key", test_api_key),
        ("ROM File", test_rom),
        ("Configuration", test_config),
        ("Directories", test_directories),
        ("API Connection", test_api_connection),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR in {test_name}: {e}")
            results.append((test_name, False))
        print()

    # Summary
    print("=" * 60)
    print("Test Summary:")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {status}: {test_name}")

    print()
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print()
        print("All tests passed! You're ready to run the AI agent.")
        print("Run with: python main.py")
        return 0
    else:
        print()
        print("Some tests failed. Please fix the issues above before running.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

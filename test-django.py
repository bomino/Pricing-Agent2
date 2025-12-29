#!/usr/bin/env python
"""
Django Test Script - Checks if Django can run
"""
import os
import sys

print("=" * 50)
print("Django Test Script")
print("=" * 50)
print()

# Check Python version
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print()

# Check current directory
print(f"Current directory: {os.getcwd()}")
print()

# Try to import Django
try:
    import django
    print(f"✓ Django is installed (version {django.__version__})")
except ImportError as e:
    print(f"✗ Django is NOT installed")
    print(f"  Error: {e}")
    print(f"  Run: pip install django")
    sys.exit(1)

# Check for django_app directory
if os.path.exists("django_app"):
    print("✓ Found django_app directory")
    os.chdir("django_app")
    print(f"  Changed to: {os.getcwd()}")
else:
    print("✗ django_app directory not found")
    print(f"  Looking in: {os.getcwd()}")
    print(f"  Available directories: {[d for d in os.listdir('.') if os.path.isdir(d)]}")
    sys.exit(1)

# Check for manage.py
if os.path.exists("manage.py"):
    print("✓ Found manage.py")
else:
    print("✗ manage.py not found")
    print(f"  Looking in: {os.getcwd()}")
    print(f"  Available files: {[f for f in os.listdir('.') if f.endswith('.py')]}")
    sys.exit(1)

# Try to run Django check
print()
print("Testing Django setup...")
print("-" * 30)

import subprocess
result = subprocess.run([sys.executable, "manage.py", "check"],
                       capture_output=True, text=True)

if result.returncode == 0:
    print("✓ Django check passed!")
    print(result.stdout)
else:
    print("✗ Django check failed:")
    print(result.stderr)
    print(result.stdout)

# Try to get Django settings
print()
print("Checking Django settings...")
print("-" * 30)

try:
    # Add django_app to path
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pricing_agent.settings")

    django.setup()
    print("✓ Django settings loaded successfully")

    from django.conf import settings
    print(f"  DEBUG: {settings.DEBUG}")
    print(f"  DATABASES: {list(settings.DATABASES.keys())}")

except Exception as e:
    print(f"✗ Error loading Django settings: {e}")

print()
print("=" * 50)
print("Test complete. If all checks passed, run:")
print("  cd django_app")
print("  python manage.py runserver")
print("=" * 50)
input("\nPress Enter to exit...")
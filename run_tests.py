#!/usr/bin/env python3
"""
Test runner script for NextFlix - runs all tests with coverage reporting.
"""

import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a shell command and report result."""
    print(f"\n{'='*70}")
    print(f"▶ {description}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ {description} failed")
        return False
    print(f"✅ {description} passed")
    return True


def main():
    """Run all test suites."""
    os.chdir(os.path.join(os.path.dirname(__file__), 'backend', 'flask'))
    
    results = {}
    
    # Run unit tests
    results['unit_tests'] = run_command(
        'pytest test_server.py -v --tb=short',
        'Unit Tests (test_server.py)'
    )
    
    # Run integration tests
    results['integration_tests'] = run_command(
        'pytest test_integration.py -v --tb=short',
        'Integration Tests (test_integration.py)'
    )
    
    # Run with coverage
    results['coverage'] = run_command(
        'pytest test_server.py test_integration.py --cov=. --cov-report=html --cov-report=term-missing',
        'Coverage Report Generation'
    )
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
    
    print(f"{'='*70}")
    
    if all_passed:
        print("\n✅ All tests passed!")
        print("\nCoverage report generated in htmlcov/index.html")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

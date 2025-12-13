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
    repo_root = os.path.dirname(__file__)
    # run backend tests from backend/flask
    os.chdir(os.path.join(repo_root, 'backend', 'flask'))

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

    # Run with coverage (backend) — assume coverage tooling is provided by the environment (e.g. your venv)
    results['coverage_backend'] = run_command(
        'pytest test_server.py test_integration.py --cov=. --cov-report=html --cov-report=term-missing',
        'Backend Coverage Report Generation'
    )

    # Frontend: run tests with coverage (if frontend exists)
    frontend_dir = os.path.join(repo_root, 'frontend')
    if os.path.isdir(frontend_dir) and os.path.isfile(os.path.join(frontend_dir, 'package.json')):
        # Always install frontend dependencies to ensure devDependencies are present
        install_cmd = f'cd "{frontend_dir}" && npm install --no-audit --no-fund'
        install_ok = run_command(install_cmd, 'Install Frontend Dependencies (npm install)')
        results['frontend_install'] = install_ok
        if not install_ok:
            print('\n❌ Failed to install frontend dependencies; skipping frontend tests')
            results['frontend_tests'] = False
        else:
            # Use CI=true to make react-scripts run tests non-interactively and --watchAll=false to exit
            cmd = f'cd "{frontend_dir}" && CI=true npm test -- --coverage --watchAll=false'
            results['frontend_tests'] = run_command(cmd, 'Frontend Tests (npm test with coverage)')
    else:
        print('\n⚠️  Frontend not found or missing package.json; skipping frontend tests')
        results['frontend_tests'] = True
    
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
        print("\nBackend coverage report generated in backend/flask/htmlcov/index.html")
        if results.get('frontend_tests'):
            print("Frontend coverage (if generated) is at frontend/coverage/lcov-report/index.html")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
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
    repo_root = os.path.dirname(__file__)
    # run backend tests from backend/flask
    os.chdir(os.path.join(repo_root, 'backend', 'flask'))

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

    # Run with coverage (backend) — assume coverage tooling is provided by the environment (e.g. your venv)
    results['coverage_backend'] = run_command(
        'pytest test_server.py test_integration.py --cov=. --cov-report=html --cov-report=term-missing',
        'Backend Coverage Report Generation'
    )

    # Frontend: run tests with coverage (if frontend exists)
    frontend_dir = os.path.join(repo_root, 'frontend')
    if os.path.isdir(frontend_dir) and os.path.isfile(os.path.join(frontend_dir, 'package.json')):
        # Always install frontend dependencies to ensure devDependencies are present
        install_cmd = f'cd "{frontend_dir}" && npm install --no-audit --no-fund'
        install_ok = run_command(install_cmd, 'Install Frontend Dependencies (npm install)')
        results['frontend_install'] = install_ok
        if not install_ok:
            print('\n❌ Failed to install frontend dependencies; skipping frontend tests')
            results['frontend_tests'] = False
        else:
            # Use CI=true to make react-scripts run tests non-interactively and --watchAll=false to exit
            cmd = f'cd "{frontend_dir}" && CI=true npm test -- --coverage --watchAll=false'
            results['frontend_tests'] = run_command(cmd, 'Frontend Tests (npm test with coverage)')
    else:
        print('\n⚠️  Frontend not found or missing package.json; skipping frontend tests')
        results['frontend_tests'] = True
    
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
        print("\nBackend coverage report generated in backend/flask/htmlcov/index.html")
        if results.get('frontend_tests'):
            print("Frontend coverage (if generated) is at frontend/coverage/lcov-report/index.html")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

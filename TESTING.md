# NextFlix Testing Documentation

## Overview
This document outlines the testing strategy for the NextFlix recommendation engine, including unit tests, integration tests, functional tests, and non-functional requirements validation.

## Test Coverage

### 1. Unit Tests (`test_server.py`)

#### Utility Functions
- `test_split_field_with_commas()` - Verify comma-separated value parsing
- `test_split_field_with_pipes()` - Verify pipe-separated value parsing
- `test_split_field_with_and()` - Verify 'and' keyword parsing
- `test_split_field_empty()` - Handle empty/null inputs gracefully
- `test_split_field_with_mixed_delimiters()` - Support multiple delimiters

#### Similarity Scoring
- `test_exact_director_match()` - Movies with same director score high (+5)
- `test_shared_actors_scoring()` - Shared actors contribute to score (+3 per actor)
- `test_shared_genres_scoring()` - Shared genres contribute to score (+1 per genre)
- `test_tag_similarity()` - Tag-based similarity matching (+0.5 per tag)

#### Database Operations
- `test_movies_table_exists()` - Verify `movies_flat` table creation
- `test_users_preferences_table_exists()` - Verify `users_preferences` table
- `test_bug_reports_table_exists()` - Verify `bug_reports` table
- `test_insert_and_retrieve_movie()` - CRUD operations on movies
- `test_user_preferences_persistence()` - Preferences persist in DB

#### API Endpoints
- `test_home_endpoint()` - Home endpoint returns 200
- `test_search_by_title()` - Title search finds movies
- `test_search_by_director()` - Director search works
- `test_search_by_actor()` - Actor search works
- `test_search_missing_params_returns_all()` - Fallback behavior
- `test_similar_movies_endpoint()` - Similarity scoring returns results
- `test_similar_movies_movie_not_found()` - 404 for non-existent movies
- `test_movie_details_endpoint()` - Movie detail endpoint
- `test_catalog_options_endpoint()` - Catalog dropdown data

#### User Workflows
- `test_save_user_preferences()` - Preferences can be saved
- `test_retrieve_user_preferences()` - Preferences persist and retrieve
- `test_add_to_watchlist()` - Movies added to watchlist
- `test_remove_from_watchlist()` - Movies removed from watchlist
- `test_add_to_favorites()` - Favorites persist
- `test_mark_movie_as_seen()` - Movies marked as seen
- `test_submit_feedback()` - Feedback submission works
- `test_create_bug_report()` - Bug reports can be created

#### Non-Functional Requirements
- `test_api_response_time()` - APIs respond < 1 second
- `test_invalid_user_id_handling()` - Graceful error handling
- `test_missing_required_fields()` - Missing fields return 400
- `test_case_insensitive_search()` - Search is case-insensitive
- `test_duplicate_watchlist_prevention()` - Duplicates are prevented

### 2. Integration Tests (`test_integration.py`)

#### End-to-End User Journeys
- `test_complete_user_flow_search_and_recommend()` - Full search → preferences → recommendations workflow
- `test_user_watchlist_workflow()` - Watchlist → mark as seen flow
- `test_user_feedback_workflow()` - Rating and feedback submission
- `test_favorites_and_preferences_integration()` - Favorites stored in preferences
- `test_director_search_and_recommendations()` - Director-based recommendations
- `test_actor_search_recommendations()` - Actor-based recommendations

#### Similarity and Recommendation Logic
- `test_similar_movies_scoring()` - Similar movies scored correctly
- `test_genre_based_similarity()` - Genre overlap considered
- `test_director_based_similarity()` - Director matching works

#### Data Integrity
- `test_movie_data_integrity()` - All movie fields correct
- `test_preference_overwrite_behavior()` - New preferences overwrite old
- `test_watchlist_deduplication()` - Duplicates prevented in watchlist

## Running Tests Locally

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
cd backend/flask
pytest -v --tb=short
```

### Run Specific Test Suite
```bash
# Unit tests only
pytest test_server.py -v

# Integration tests only
pytest test_integration.py -v

# With coverage
pytest test_server.py test_integration.py test_admin.py --cov=. --cov-report=html

# Admin tests
pytest test_admin.py -v
```

### Run Specific Test Class
```bash
pytest test_server.py::TestSimilarityScoring -v
```

### Run Specific Test
```bash
pytest test_server.py::TestSimilarityScoring::test_exact_director_match -v
```

## Test Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Backend Functions | 85% | TBD |
| API Endpoints | 90% | TBD |
| Database Layer | 95% | TBD |
| User Workflows | 85% | TBD |
| Overall | 85% | TBD |

## Functional Requirements Tested

| Requirement | Test | Status |
|-------------|------|--------|
| Search by title/director/actor | `test_search_*` | ✓ |
| Movie similarity scoring | `TestSimilarityScoring` | ✓ |
| User preferences save/retrieve | `test_save_user_preferences`, `test_retrieve_user_preferences` | ✓ |
| Add to watchlist | `test_add_to_watchlist` | ✓ |
| Add to favorites | `test_add_to_favorites` | ✓ |
| Mark movie as seen | `test_mark_movie_as_seen` | ✓ |
| Submit feedback/ratings | `test_submit_feedback` | ✓ |
| Recommendations from preferences | `test_complete_user_flow_search_and_recommend` | ✓ |
| Bug report creation | `test_create_bug_report` | ✓ |

## Non-Functional Requirements Tested

| Requirement | Test | Target | Status |
|-------------|------|--------|--------|
| Response time | `test_api_response_time` | < 1s | ✓ |
| Case-insensitive search | `test_case_insensitive_search` | - | ✓ |
| Error handling | `test_invalid_user_id_handling`, `test_missing_required_fields` | - | ✓ |
| Data persistence | `test_user_preferences_persistence` | - | ✓ |
| Duplicate prevention | `test_duplicate_watchlist_prevention` | - | ✓ |

## CI/CD Pipeline

### GitHub Actions Workflow (`.github/workflows/ci.yml`)

The workflow includes:

1. **Backend Tests** - Run on Python 3.9, 3.10, 3.11
   - Unit tests (`test_server.py`)
   - Integration tests (`test_integration.py`)
   - Coverage reports (uploads to Codecov)

2. **Frontend Tests** - Run on Node 16, 18, 20
   - Linting (ESLint)
   - Build verification
   - Component tests (if defined)

### Admin Server Tests

These tests unit-test and validate the admin server endpoints implemented in `backend/flask/admin.py`.
- CSV loading: validating required columns, ingest behavior, and error handling
- CRUD operations: add, edit, delete and listing via API and templates
- Reports: listing and deletion

Run admin tests locally:
```bash
cd backend/flask
pytest test_admin.py -v
```

### Continuous Deployment (GitHub Pages)

The repository contains a CD workflow to publish the built frontend to GitHub Pages when code is pushed to `main` (e.g., after you merge `dev` into `main`).

- File: `.github/workflows/cd.yml`
- Trigger: `push` to `main` branch
- What it does:
   - Runs the full backend test suite (including `test_admin.py`) and generates coverage reports
   - Builds the frontend (`npm run build`)
   - Publishes the frontend build output (`frontend/build`) to GitHub Pages using the official Pages actions (`actions/upload-pages-artifact` and `actions/deploy-pages`).

Notes:
- No additional repository secrets are required for GitHub Pages deployment—the workflow uses the built-in `GITHUB_TOKEN` to perform the Pages deployment.
- The CD workflow will still run tests and builds even if Pages deployment is disabled in repository settings; you can enable/disable Pages in the repository's GitHub settings as needed.

### Frontend (Jest) Tests

Frontend tests live in `frontend/src/tests` and assert component rendering, interactions, and local state.
Run all frontend tests with coverage:
```bash
cd frontend
npm test -- --coverage --watchAll=false --passWithNoTests
```

3. **Code Quality** - Flake8 and Pylint
   - PEP8 compliance
   - Syntax validation

4. **Database Tests** - Schema initialization
   - Table creation verification
   - Data type validation

5. **Dependency Check** - Security scanning
   - Vulnerability detection
   - Outdated package warnings

### Running CI/CD Locally

```bash
# Install act (GitHub Actions local runner)
# https://github.com/nektos/act

act push -j backend-tests
act push -j code-quality
act push -j database-tests
```

## Test Data

All tests use a temporary SQLite database populated with sample movies:
- **Inception** (Christopher Nolan, Leonardo DiCaprio) - Sci-Fi, Thriller, Action
- **The Dark Knight** (Christopher Nolan, Christian Bale) - Action, Crime, Drama
- **The Shawshank Redemption** (Frank Darabont, Tim Robbins) - Drama, Crime
- **War of the Worlds** (Steven Spielberg, Tom Cruise) - Sci-Fi, Action
- **V for Vendetta** (James McTeigue, Natalie Portman) - Action, Drama, Thriller

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the correct directory
cd backend/flask
# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Locks
```bash
# Remove stale test databases
find . -name "*.db" -type f -delete
```

### Slow Tests
```bash
# Run with verbose output to identify bottlenecks
pytest -v -s --tb=short
```

## Future Improvements

1. **Performance Tests** - Load testing with multiple concurrent users
2. **Frontend Component Tests** - Jest/React Testing Library tests
3. **E2E Tests** - Selenium/Cypress for full browser testing
4. **Security Tests** - SQL injection, XSS, CSRF validation
5. **Accessibility Tests** - WCAG compliance checking
6. **Load Testing** - Monitor API performance under stress

## Contributing Tests

When adding new features:

1. Write unit tests first (TDD)
2. Add integration tests for user workflows
3. Update this documentation
4. Run full test suite before submitting PR
5. Ensure coverage stays above 85%

## Test Metrics

View coverage reports:
```bash
# Generate HTML report
pytest --cov=. --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
```

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Flask Testing Guide](https://flask.palletsprojects.com/testing/)

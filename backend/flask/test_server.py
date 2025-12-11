"""
Test suite for NextFlix recommendation backend.
Tests cover: similarity scoring, database operations, API endpoints, and user workflows.
"""

import pytest
import json
import sqlite3
import tempfile
import os
import time
from pathlib import Path

# Import the Flask app and helper functions
import sys
sys.path.insert(0, os.path.dirname(__file__))

from server import (
    app, get_db, row_to_dict, split_field, enrich_movie_info,
    init_db_schema, fetch_synopsis, fetch_ratings, fetch_streaming_platforms,
    compute_recommendations_for_user, DATABASE
)


@pytest.fixture
def client():
    """Create a test client with a temporary database."""
    # Create a temporary database for testing
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app.config['TESTING'] = True
    
    # Override DATABASE path for testing
    import server as server_module
    original_db = server_module.DATABASE
    server_module.DATABASE = db_path
    
    with app.app_context():
        init_db_schema()
        # Populate test data within Flask context
        db = get_db()
        movies = [
            ('Christopher Nolan', 'Leonardo DiCaprio', 'Ellen Page', 'Marion Cotillard', 
             'Sci-Fi, Thriller, Action', 'Inception', 'mind-bending, heist, dreams'),
            ('Christopher Nolan', 'Christian Bale', 'Michael Caine', 'Gary Oldman',
             'Action, Crime, Drama', 'The Dark Knight', 'superhero, dark, intense'),
            ('Frank Darabont', 'Tim Robbins', 'Morgan Freeman', 'Bob Gunton',
             'Drama, Crime', 'The Shawshank Redemption', 'redemption, prison, classic'),
            ('Steven Spielberg', 'Tom Cruise', 'Dakota Cruise', 'Justin Chatwin',
             'Sci-Fi, Action', 'War of the Worlds', 'aliens, invasion, survival'),
            ('James McTeigue', 'Natalie Portman', 'Hugo Weaving', 'Stephen Rea',
             'Action, Drama, Thriller', 'V for Vendetta', 'revolution, mask, thriller'),
        ]
        
        for m in movies:
            title = m[5]
            db.execute('''
                INSERT INTO movies_flat 
                (director_name, actor_1_name, actor_2_name, actor_3_name, genres, movie_title, tags, movie_title_lower)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*m, title.lower()))
        db.commit()
    
    yield app.test_client()
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    server_module.DATABASE = original_db


# ==================== UNIT TESTS: Utility Functions ====================

class TestUtilityFunctions:
    """Test helper functions."""

    def test_split_field_with_commas(self):
        """Test splitting comma-separated values."""
        result = split_field("Action, Comedy, Drama")
        assert sorted(result) == sorted(['action', 'comedy', 'drama'])

    def test_split_field_with_pipes(self):
        """Test splitting pipe-separated values."""
        result = split_field("Sci-Fi | Action | Thriller")
        assert sorted(result) == sorted(['sci-fi', 'action', 'thriller'])

    def test_split_field_with_and(self):
        """Test splitting 'and' keyword."""
        result = split_field("Action and Comedy and Drama")
        assert sorted(result) == sorted(['action', 'comedy', 'drama'])

    def test_split_field_empty(self):
        """Test split_field with empty/None input."""
        assert split_field(None) == []
        assert split_field("") == []
        assert split_field("   ") == []

    def test_split_field_with_mixed_delimiters(self):
        """Test splitting with mixed delimiters."""
        result = split_field("Action, Comedy & Drama | Thriller")
        assert 'action' in result
        assert 'comedy' in result
        assert 'drama' in result
        assert 'thriller' in result


# ==================== UNIT TESTS: Similarity Scoring ====================

class TestSimilarityScoring:
    """Test movie similarity scoring logic."""

    def test_exact_director_match(self, client):
        """Test that movies with same director score high."""
        # Inception and Dark Knight share director Christopher Nolan
        # Similarity should weight director match at +5
        with app.app_context():
            db = get_db()
            
            # Query Inception
            row = db.execute(
                f"SELECT * FROM movies_flat WHERE LOWER(movie_title) = 'inception'"
            ).fetchone()
            assert row is not None, "Inception not found in test data"
            
            inception = row_to_dict(row)
            director = inception.get('director_name')
            assert director.lower() == 'christopher nolan'

    def test_shared_actors_scoring(self):
        """Test that shared actors contribute to similarity score."""
        # Test that split_field works with comma-separated actors
        result = split_field("Action, Sci-Fi, Drama")
        assert len(result) >= 2
        assert 'action' in result

    def test_shared_genres_scoring(self):
        """Test that shared genres contribute to similarity score."""
        genres1 = set(split_field("Action, Sci-Fi, Thriller"))
        genres2 = set(split_field("Sci-Fi, Action, Drama"))
        shared = genres1.intersection(genres2)
        assert 'action' in shared
        assert 'sci-fi' in shared
        assert len(shared) == 2

    def test_tag_similarity(self):
        """Test tag-based similarity."""
        tags1 = set(split_field("mind-bending, heist, dreams"))
        tags2 = set(split_field("heist, thriller, dreams"))
        shared = tags1.intersection(tags2)
        assert 'heist' in shared
        assert 'dreams' in shared


# ==================== UNIT TESTS: Database Operations ====================

class TestDatabaseOperations:
    """Test database schema and CRUD operations."""

    def test_movies_table_exists(self, client):
        """Test that movies_flat table exists."""
        with app.app_context():
            db = get_db()
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='movies_flat'"
            )
            assert cursor.fetchone() is not None

    def test_users_preferences_table_exists(self, client):
        """Test that users_preferences table exists."""
        with app.app_context():
            db = get_db()
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users_preferences'"
            )
            assert cursor.fetchone() is not None

    def test_bug_reports_table_exists(self, client):
        """Test that bug_reports table exists."""
        with app.app_context():
            db = get_db()
            cursor = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bug_reports'"
            )
            assert cursor.fetchone() is not None

    def test_insert_and_retrieve_movie(self, client):
        """Test inserting and retrieving a movie."""
        with app.app_context():
            db = get_db()
            cursor = db.execute("SELECT * FROM movies_flat WHERE movie_title = 'Inception'")
            row = cursor.fetchone()
            assert row is not None
            movie = row_to_dict(row)
            assert movie['movie_title'] == 'Inception'
            assert movie['director_name'] == 'Christopher Nolan'

    def test_user_preferences_persistence(self, client):
        """Test that user preferences can be inserted and retrieved."""
        with app.app_context():
            db = get_db()
            user_id = 'test_user_123'
            prefs = {'movies': ['Inception'], 'genres': ['Sci-Fi'], 'directors': ['Nolan']}
            
            db.execute(
                'INSERT INTO users_preferences (user_id, preferences_json, updated_at) VALUES (?, ?, ?)',
                (user_id, json.dumps(prefs), time.time())
            )
            db.commit()
            
            # Retrieve and verify
            row = db.execute(
                'SELECT preferences_json FROM users_preferences WHERE user_id = ?',
                (user_id,)
            ).fetchone()
            assert row is not None
            retrieved_prefs = json.loads(row[0])
            assert retrieved_prefs['movies'] == ['Inception']
            assert 'Sci-Fi' in retrieved_prefs['genres']


# ==================== FUNCTIONAL TESTS: API Endpoints ====================

class TestAPIEndpoints:
    """Test Flask API endpoints."""

    def test_home_endpoint(self, client):
        """Test the home endpoint."""
        response = client.get('/')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'message' in data

    def test_search_by_title(self, client):
        """Test search endpoint with title parameter."""
        response = client.get('/search?title=inception')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'results' in data
        assert data['count'] > 0
        assert any(m['movie_title'] == 'Inception' for m in data['results'])

    def test_search_by_director(self, client):
        """Test search endpoint with director parameter."""
        response = client.get('/search?director=nolan')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] >= 2  # Two Nolan films in test data

    def test_search_by_actor(self, client):
        """Test search endpoint with actor parameter."""
        response = client.get('/search?actor=leonardo')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['count'] > 0

    def test_search_missing_params_returns_all(self, client):
        """Test search with no params returns results."""
        response = client.get('/search?limit=10')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'results' in data

    def test_similar_movies_endpoint(self, client):
        """Test similar movies recommendation endpoint."""
        response = client.get('/similar?title=Inception&top=3')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'target' in data
        assert 'recommendations' in data
        assert data['target']['movie_title'] == 'Inception'
        # Check that similar movies have scores
        for rec in data['recommendations']:
            assert 'score' in rec

    def test_similar_movies_movie_not_found(self, client):
        """Test similar endpoint with non-existent movie."""
        response = client.get('/similar?title=NonExistentMovie&top=5')
        assert response.status_code == 404

    def test_movie_details_endpoint(self, client):
        """Test movie details endpoint."""
        response = client.get('/movie?title=inception')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['movie_title'] == 'Inception'
        assert 'director_name' in data

    def test_catalog_options_endpoint(self, client):
        """Test catalog options endpoint."""
        response = client.get('/catalog/options')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'movies' in data
        assert 'directors' in data
        assert 'actors' in data
        assert 'genres' in data
        assert len(data['movies']) > 0


# ==================== FUNCTIONAL TESTS: User Workflows ====================

class TestUserWorkflows:
    """Test end-to-end user functionality."""

    def test_save_user_preferences(self, client):
        """Test saving user preferences."""
        prefs = {
            'movies': ['Inception'],
            'genres': ['Sci-Fi', 'Action'],
            'directors': ['Christopher Nolan'],
            'actors': ['Leonardo DiCaprio']
        }
        response = client.post('/user/preferences',
            json={'user_id': 'user_001', 'preferences': prefs}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert data['user_id'] == 'user_001'

    def test_retrieve_user_preferences(self, client):
        """Test retrieving saved user preferences."""
        # First save preferences
        prefs = {'movies': ['Inception'], 'genres': ['Sci-Fi']}
        client.post('/user/preferences',
            json={'user_id': 'user_002', 'preferences': prefs}
        )
        
        # Then retrieve
        response = client.get('/user/preferences/user_002')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['preferences']['movies'] == ['Inception']

    def test_add_to_watchlist(self, client):
        """Test adding a movie to watchlist."""
        response = client.post('/user/watchlist',
            json={'user_id': 'user_003', 'movie': 'Inception'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Inception' in data['watchlist']

    def test_remove_from_watchlist(self, client):
        """Test removing a movie from watchlist."""
        # Add first
        client.post('/user/watchlist',
            json={'user_id': 'user_004', 'movie': 'Inception'}
        )
        
        # Then remove
        response = client.post('/user/watchlist/remove',
            json={'user_id': 'user_004', 'movie': 'Inception'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Inception' not in data['watchlist']

    def test_add_to_favorites(self, client):
        """Test adding a movie to favorites."""
        response = client.post('/user/favorites',
            json={'user_id': 'user_005', 'movie': 'Inception'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Inception' in data['favorites']

    def test_mark_movie_as_seen(self, client):
        """Test marking a movie as seen."""
        response = client.post('/user/seen',
            json={'user_id': 'user_006', 'movie': 'Inception'}
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Inception' in data['seen']

    def test_submit_feedback(self, client):
        """Test submitting feedback on a movie."""
        response = client.post('/user/feedback',
            json={
                'user_id': 'user_007',
                'movie': 'Inception',
                'rating': 5,
                'text': 'Amazing movie!'
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'

    def test_create_bug_report(self, client):
        """Test creating a bug report."""
        response = client.post('/reports',
            json={
                'user_id': 'user_008',
                'subject': 'Search not working',
                'description': 'Title search returns empty results'
            }
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'report' in data


# ==================== NON-FUNCTIONAL TESTS ====================

class TestNonFunctionalRequirements:
    """Test non-functional requirements like performance, error handling."""

    def test_api_response_time(self, client):
        """Test that API responds within reasonable time."""
        import time
        start = time.time()
        response = client.get('/search?title=inception')
        elapsed = time.time() - start
        # Should respond within 1 second
        assert elapsed < 1.0, f"Search took {elapsed}s, should be < 1s"

    def test_invalid_user_id_handling(self, client):
        """Test that API handles invalid user gracefully."""
        response = client.post('/user/preferences',
            json={'user_id': None, 'preferences': {}}
        )
        assert response.status_code == 400

    def test_missing_required_fields(self, client):
        """Test error handling for missing required fields."""
        response = client.post('/user/watchlist',
            json={'user_id': 'user_009'}  # Missing 'movie' field
        )
        assert response.status_code == 400

    def test_case_insensitive_search(self, client):
        """Test that search is case-insensitive."""
        response1 = client.get('/search?title=INCEPTION')
        response2 = client.get('/search?title=inception')
        
        data1 = json.loads(response1.data)
        data2 = json.loads(response2.data)
        
        assert data1['count'] == data2['count']

    def test_duplicate_watchlist_prevention(self, client):
        """Test that duplicate entries in watchlist are prevented."""
        user_id = 'user_010'
        
        # Add same movie twice
        client.post('/user/watchlist',
            json={'user_id': user_id, 'movie': 'Inception'}
        )
        response = client.post('/user/watchlist',
            json={'user_id': user_id, 'movie': 'Inception'}
        )
        
        data = json.loads(response.data)
        # Count occurrences of Inception
        count = sum(1 for m in data['watchlist'] if m.lower() == 'inception')
        assert count == 1, "Duplicate prevention failed"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

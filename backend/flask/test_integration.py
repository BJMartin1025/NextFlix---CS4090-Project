"""
Integration tests for NextFlix recommendation system.
Tests end-to-end workflows combining multiple features.
"""

import pytest
import json
import tempfile
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from server import app, init_db_schema, get_db, row_to_dict, DATABASE


@pytest.fixture
def client():
    """Create a test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    app.config['TESTING'] = True
    
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
    
    os.close(db_fd)
    os.unlink(db_path)
    server_module.DATABASE = original_db


class TestEndToEndUserJourney:
    """Test complete user workflows."""

    def test_complete_user_flow_search_and_recommend(self, client):
        """Test complete flow: search → add preferences → get recommendations."""
        user_id = 'integration_user_001'
        
        # Step 1: Search for a movie
        search_response = client.get('/search?title=inception')
        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data['count'] > 0
        
        # Step 2: Save user preferences based on search
        prefs = {
            'movies': ['Inception'],
            'genres': ['Sci-Fi'],
            'directors': ['Christopher Nolan'],
            'actors': ['Leonardo DiCaprio']
        }
        pref_response = client.post('/user/preferences',
            json={'user_id': user_id, 'preferences': prefs}
        )
        assert pref_response.status_code == 200
        
        # Step 3: Get recommendations based on preferences
        rec_response = client.post('/recommend/user',
            json={'user_id': user_id, 'top_n': 5}
        )
        assert rec_response.status_code == 200
        rec_data = json.loads(rec_response.data)
        assert 'recommendations' in rec_data

    def test_user_watchlist_workflow(self, client):
        """Test user adding to watchlist and marking as seen."""
        user_id = 'integration_user_002'
        movie = 'Inception'
        
        # Add to watchlist
        add_response = client.post('/user/watchlist',
            json={'user_id': user_id, 'movie': movie}
        )
        assert add_response.status_code == 200
        
        # Verify it's in watchlist
        get_response = client.get(f'/user/watchlist/{user_id}')
        assert get_response.status_code == 200
        get_data = json.loads(get_response.data)
        assert movie in get_data['watchlist']
        
        # Mark as seen
        seen_response = client.post('/user/seen',
            json={'user_id': user_id, 'movie': movie}
        )
        assert seen_response.status_code == 200
        
        # Should be removed from watchlist
        final_response = client.get(f'/user/watchlist/{user_id}')
        final_data = json.loads(final_response.data)
        assert movie not in final_data['watchlist']

    def test_user_feedback_workflow(self, client):
        """Test user rating and feedback submission."""
        user_id = 'integration_user_003'
        
        # Submit feedback with rating
        feedback_response = client.post('/user/feedback',
            json={
                'user_id': user_id,
                'movie': 'Inception',
                'rating': 5,
                'text': 'Brilliant movie!'
            }
        )
        assert feedback_response.status_code == 200
        
        # Retrieve feedback
        get_response = client.get(f'/user/feedback/{user_id}')
        assert get_response.status_code == 200
        get_data = json.loads(get_response.data)
        assert len(get_data['feedback']) > 0
        assert get_data['feedback'][0]['movie'] == 'Inception'
        assert get_data['feedback'][0]['rating'] == 5

    def test_favorites_and_preferences_integration(self, client):
        """Test that favorites are persisted in preferences."""
        user_id = 'integration_user_004'
        
        # Add to favorites
        fav_response = client.post('/user/favorites',
            json={'user_id': user_id, 'movie': 'Inception'}
        )
        assert fav_response.status_code == 200
        fav_data = json.loads(fav_response.data)
        assert 'Inception' in fav_data['favorites']
        
        # Verify it's in preferences
        assert 'Inception' in fav_data['preferences']['movies']

    def test_director_search_and_recommendations(self, client):
        """Test searching by director and getting recommendations."""
        # Search by director
        search_response = client.get('/search?director=nolan')
        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data['count'] >= 2  # At least 2 Nolan films
        
        # Verify results
        nolan_films = [m['movie_title'] for m in search_data['results']]
        assert any('Dark Knight' in f or 'Inception' in f for f in nolan_films)

    def test_actor_search_recommendations(self, client):
        """Test searching by actor."""
        search_response = client.get('/search?actor=leonardo')
        assert search_response.status_code == 200
        search_data = json.loads(search_response.data)
        assert search_data['count'] > 0
        
        # Should find Inception
        assert any('Inception' in m.get('movie_title', '') for m in search_data['results'])


class TestSimilarityAndRecommendationLogic:
    """Test the core recommendation/similarity logic."""

    def test_similar_movies_scoring(self, client):
        """Test that similar movies are properly scored."""
        response = client.get('/similar?title=inception&top=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check that movies are scored
        recommendations = data['recommendations']
        assert len(recommendations) > 0
        
        # Scores should be positive and in descending order
        for i in range(len(recommendations) - 1):
            current_score = recommendations[i].get('score', 0)
            next_score = recommendations[i + 1].get('score', 0)
            assert current_score >= next_score, "Scores not in descending order"

    def test_genre_based_similarity(self, client):
        """Test that movies with same genres are recommended."""
        # All movies have some genre overlap
        response = client.get('/similar?title=inception&top=3')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have recommendations (genre-based matching)
        assert len(data['recommendations']) > 0

    def test_director_based_similarity(self, client):
        """Test that movies from same director are highly scored."""
        response = client.get('/similar?title=inception&top=5')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Dark Knight (same director as Inception) should be in recommendations
        rec_titles = [m.get('movie_title', '') for m in data['recommendations']]
        assert any('Dark Knight' in t for t in rec_titles)


class TestDataIntegrity:
    """Test database integrity and consistency."""

    def test_movie_data_integrity(self, client):
        """Test that movie data is correctly stored and retrieved."""
        response = client.get('/movie?title=inception')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Verify all expected fields
        assert data['movie_title'] == 'Inception'
        assert data['director_name'] == 'Christopher Nolan'
        assert 'Sci-Fi' in data['genres']
        assert data['actor_1_name'] == 'Leonardo DiCaprio'

    def test_preference_overwrite_behavior(self, client):
        """Test that saving preferences overwrites previous data."""
        user_id = 'integrity_user_001'
        
        # Save initial preferences
        initial = {
            'movies': ['Inception'],
            'genres': ['Sci-Fi'],
            'directors': [],
            'actors': []
        }
        client.post('/user/preferences',
            json={'user_id': user_id, 'preferences': initial}
        )
        
        # Save new preferences (should overwrite)
        new = {
            'movies': ['Dark Knight'],
            'genres': ['Action', 'Crime'],
            'directors': ['Christopher Nolan'],
            'actors': []
        }
        client.post('/user/preferences',
            json={'user_id': user_id, 'preferences': new}
        )
        
        # Retrieve and verify overwrite
        response = client.get(f'/user/preferences/{user_id}')
        data = json.loads(response.data)
        retrieved = data['preferences']
        
        # New data should be present, old movies list should be replaced
        assert 'Dark Knight' in retrieved['movies']
        assert 'Inception' not in retrieved['movies']
        assert 'Christopher Nolan' in retrieved['directors']

    def test_watchlist_deduplication(self, client):
        """Test that watchlist prevents duplicate entries."""
        user_id = 'integrity_user_002'
        
        # Add same movie multiple times
        for _ in range(3):
            client.post('/user/watchlist',
                json={'user_id': user_id, 'movie': 'Inception'}
            )
        
        # Retrieve and verify single entry
        response = client.get(f'/user/watchlist/{user_id}')
        data = json.loads(response.data)
        
        inception_count = sum(1 for m in data['watchlist'] 
                             if m.lower() == 'inception')
        assert inception_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

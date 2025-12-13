"""
Admin server tests for NextFlix project.
Tests cover: CSV upload, index/search, add/edit/delete, API list, and reports.
"""

import io
import os
import tempfile
import json
import sqlite3
import pytest
import time
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(__file__))

import admin
import server
from server import init_db_schema, get_db


@pytest.fixture
def admin_client():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    admin.app.config['TESTING'] = True

    # Set both server and admin modules to use this DB
    original_server_db = server.DATABASE
    original_admin_db = admin.DATABASE
    server.DATABASE = db_path
    admin.DATABASE = db_path

    # Initialize schema and populate a sample movie
    with server.app.app_context():
        init_db_schema()
        db = get_db()
        db.execute('''
            INSERT INTO movies_flat
            (director_name, actor_1_name, actor_2_name, actor_3_name, genres, movie_title, tags, movie_title_lower)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Christopher Nolan', 'Leonardo DiCaprio', 'Ellen Page', 'Marion Cotillard', 'Sci-Fi', 'Inception', 'dreams', 'inception'))
        db.commit()
    
    yield admin.app.test_client()

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
    server.DATABASE = original_server_db
    admin.DATABASE = original_admin_db


def test_upload_csv_no_file(admin_client):
    resp = admin_client.post('/upload_csv')
    assert resp.status_code == 400
    assert b'No file uploaded' in resp.data


def test_upload_csv_missing_columns(admin_client):
    # Build a CSV missing required columns
    csv_data = "movie_title,director_name\nTitle Only,Some Director\n"
    data = {'csv_file': (io.BytesIO(csv_data.encode('utf-8')), 'test.csv')}
    resp = admin_client.post('/upload_csv', data=data, content_type='multipart/form-data')
    assert resp.status_code == 400
    assert b'missing required columns' in resp.data.lower() or b'missing required columns' in resp.get_data(as_text=True).lower()


def test_upload_csv_success(admin_client):
    csv_data = (
        "movie_title,director_name,actor_1_name,actor_2_name,actor_3_name,genres,tags\n"
        "Fone,Someone,Actor A,Actor B,Actor C,Drama,tag1\n"
        "Ftwo,Someone,Actor X,Actor Y,Actor Z,Action,tag2\n"
    )
    data = {'csv_file': (io.BytesIO(csv_data.encode('utf-8')), 'movies.csv')}
    resp = admin_client.post('/upload_csv', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    payload = json.loads(resp.data)
    assert payload['status'] == 'completed'
    assert payload['inserted'] == 2
    assert payload['errors'] == []


def test_index_shows_movies(admin_client):
    # Index page should render and include the sample 'Inception' title we inserted
    resp = admin_client.get('/')
    assert resp.status_code == 200
    assert b'Inception' in resp.data


def test_api_movies(admin_client):
    resp = admin_client.get('/api/movies')
    assert resp.status_code == 200
    movies = json.loads(resp.data)
    assert isinstance(movies, list)
    assert any(m['movie_title'] == 'Inception' for m in movies)


def test_add_movie_json(admin_client):
    payload = {
        'movie_title': 'New Film',
        'director_name': 'Someone',
        'actor_1_name': 'A B',
        'actor_2_name': 'C D',
        'actor_3_name': 'E F',
        'genres': 'Comedy',
        'tags': 'fun'
    }
    resp = admin_client.post('/add', data=json.dumps(payload), content_type='application/json')
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data['status'] == 'ok'
    # Confirm inserted
    with server.app.app_context():
        db = get_db()
        row = db.execute("SELECT movie_title FROM movies_flat WHERE movie_title = 'New Film'").fetchone()
        assert row is not None


def test_add_movie_missing_title(admin_client):
    payload = {'director_name': 'Someone'}
    resp = admin_client.post('/add', data=json.dumps(payload), content_type='application/json')
    assert resp.status_code == 400
    data = json.loads(resp.data)
    assert 'Movie title is required' in data['error']


def test_edit_movie_json_success(admin_client):
    # Get existing Inception row id
    with server.app.app_context():
        db = get_db()
        r = db.execute("SELECT rowid FROM movies_flat WHERE movie_title = 'Inception'").fetchone()
        assert r is not None
        movie_id = r['rowid']

    payload = {'movie_title': 'Inception Updated', 'director_name': 'C Nolan', 'genres': 'Sci-Fi'}
    resp = admin_client.post(f'/edit/{movie_id}', data=json.dumps(payload), content_type='application/json')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['status'] == 'ok'
    with server.app.app_context():
        db = get_db()
        r = db.execute("SELECT movie_title FROM movies_flat WHERE rowid = ?", (movie_id,)).fetchone()
        assert r['movie_title'] == 'Inception Updated'


def test_edit_movie_missing_title(admin_client):
    # Create a specific movie for this test to avoid relying on previous tests
    with server.app.app_context():
        db = get_db()
        db.execute("INSERT INTO movies_flat (movie_title, movie_title_lower) VALUES (?, ?)", ('MovieToEdit', 'movietoedit'))
        db.commit()
        r = db.execute("SELECT rowid FROM movies_flat WHERE movie_title = 'MovieToEdit'").fetchone()
        assert r is not None
        movie_id = r['rowid']

    payload = {'director_name': 'C Nolan'}  # missing title
    resp = admin_client.post(f'/edit/{movie_id}', data=json.dumps(payload), content_type='application/json')
    assert resp.status_code == 400
    d = json.loads(resp.data)
    assert 'Movie title is required' in d['error']


def test_delete_movie_json_success(admin_client):
    # Insert a movie to delete
    with server.app.app_context():
        db = get_db()
        db.execute("INSERT INTO movies_flat (movie_title, movie_title_lower) VALUES (?, ?)", ('Temp Movie', 'temp movie'))
        db.commit()
        row = db.execute("SELECT rowid FROM movies_flat WHERE movie_title = 'Temp Movie'").fetchone()
        movie_id = row['rowid']

    resp = admin_client.post(f'/delete/{movie_id}', json={})
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['status'] == 'ok'
    with server.app.app_context():
        db = get_db()
        r = db.execute("SELECT rowid FROM movies_flat WHERE rowid = ?", (movie_id,)).fetchone()
        assert r is None


def test_delete_movie_not_found(admin_client):
    resp = admin_client.post('/delete/99999', json={})
    assert resp.status_code == 404


def test_reports_and_delete(admin_client):
    # Insert a report and then delete via endpoint
    with server.app.app_context():
        db = get_db()
        db.execute("INSERT INTO bug_reports (user_id, subject, description, created_at) VALUES (?, ?, ?, ?)", ('u1', 'Issue', 'desc', time.time()))
        db.commit()
        row = db.execute("SELECT report_id FROM bug_reports ORDER BY created_at DESC LIMIT 1").fetchone()
        rep_id = row['report_id']

    # GET reports page
    resp = admin_client.get('/reports')
    assert resp.status_code == 200
    assert b'Issue' in resp.data

    # Delete report
    resp2 = admin_client.post(f'/reports/delete/{rep_id}', json={})
    assert resp2.status_code == 200
    d = json.loads(resp2.data)
    assert d['status'] == 'ok' or d.get('message') is not None

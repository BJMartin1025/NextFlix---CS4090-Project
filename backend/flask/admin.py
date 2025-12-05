# admin.py - Admin interface for movie metadata entry
from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from pathlib import Path
import csv
from io import TextIOWrapper

app = Flask(__name__)
DATABASE = "movies.db"
MOVIES_TABLE = "movies_flat"

def get_db():
    db_path = Path(DATABASE)
    if not db_path.exists():
        raise RuntimeError(f"Database file not found: {DATABASE}")
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

#CSV Loader
@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    file = request.files.get('csv_file')
    if not file:
        return "No file uploaded", 400

    # CSV assumed UTF-8
    wrapper = TextIOWrapper(file, encoding='utf-8')
    reader = csv.DictReader(wrapper)

    required_columns = {"movie_title", "director_name", "actor_1_name", "actor_2_name", "actor_3_name", "genres", "tags"}
    if not required_columns.issubset(reader.fieldnames):
        return f"CSV is missing required columns. Required: {required_columns}", 400

    db = get_db()
    inserted = 0
    errors = []

    for i, row in enumerate(reader, start=2):  # line numbers for reporting
        try:
            title = (row.get("movie_title") or "").strip()
            if not title:
                errors.append(f"Line {i}: Missing title")
                continue

            db.execute(f"""
                INSERT INTO {MOVIES_TABLE}
                (director_name, actor_1_name, actor_2_name, actor_3_name, genres, movie_title, tags, movie_title_lower)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                (row.get("director_name") or "").strip(),
                (row.get("actor_1_name") or "").strip(),
                (row.get("actor_2_name") or "").strip(),
                (row.get("actor_3_name") or "").strip(),
                (row.get("genres") or "").strip(),
                title,
                (row.get("tags") or "").strip(),
                title.lower()
            ))
            inserted += 1
        except Exception as e:
            errors.append(f"Line {i}: {str(e)}")

    db.commit()
    db.close()

    return jsonify({
        "status": "completed",
        "inserted": inserted,
        "errors": errors
    })

@app.route('/')
def index():
    """Admin dashboard - list movies and provide add form."""
    # Support optional search filters via query parameters (title, director, actor, genres, tags)
    args = request.args
    clauses = []
    params = []

    title = (args.get('title') or '').strip()
    if title:
        clauses.append("movie_title LIKE ?")
        params.append(f"%{title}%")

    director = (args.get('director') or '').strip()
    if director:
        clauses.append("director_name LIKE ?")
        params.append(f"%{director}%")

    actor = (args.get('actor') or '').strip()
    if actor:
        # search across the three actor columns
        clauses.append("(actor_1_name LIKE ? OR actor_2_name LIKE ? OR actor_3_name LIKE ?)")
        params.extend([f"%{actor}%"] * 3)

    genres = (args.get('genres') or '').strip()
    if genres:
        clauses.append("genres LIKE ?")
        params.append(f"%{genres}%")

    tags = (args.get('tags') or '').strip()
    if tags:
        clauses.append("tags LIKE ?")
        params.append(f"%{tags}%")

    sql = f"SELECT rowid, * FROM {MOVIES_TABLE}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY movie_title"

    db = get_db()
    movies = db.execute(sql, params).fetchall()
    db.close()
    return render_template('admin_index.html', movies=movies)

@app.route('/add', methods=['GET', 'POST'])
def add_movie():
    """Add a new movie to the database."""
    if request.method == 'POST':
        data = request.get_json() or {}
        
        # Validate required fields
        title = (data.get('movie_title') or '').strip()
        if not title:
            return jsonify({'error': 'Movie title is required'}), 400
        
        director = (data.get('director_name') or '').strip()
        actor_1 = (data.get('actor_1_name') or '').strip()
        actor_2 = (data.get('actor_2_name') or '').strip()
        actor_3 = (data.get('actor_3_name') or '').strip()
        genres = (data.get('genres') or '').strip()
        tags = (data.get('tags') or '').strip()
        
        try:
            db = get_db()
            db.execute(f"""
                INSERT INTO {MOVIES_TABLE} 
                (director_name, actor_1_name, actor_2_name, actor_3_name, genres, movie_title, tags, movie_title_lower)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (director, actor_1, actor_2, actor_3, genres, title, tags, title.lower()))
            db.commit()
            db.close()
            # If the client posted JSON (AJAX), return JSON; otherwise redirect to index so
            # traditional form submissions update the dashboard immediately.
            if request.is_json:
                return jsonify({'status': 'ok', 'message': f"Movie '{title}' added successfully"}), 201
            return redirect(url_for('index'))
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request: show form
    return render_template('add_movie.html')

@app.route('/edit/<int:movie_id>', methods=['GET', 'POST'])
def edit_movie(movie_id):
    """Edit an existing movie."""
    db = get_db()
    movie = db.execute(f"SELECT rowid as id, * FROM {MOVIES_TABLE} WHERE rowid = ?", (movie_id,)).fetchone()
    db.close()
    
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404
    
    if request.method == 'POST':
        data = request.get_json() or {}
        
        title = (data.get('movie_title') or '').strip()
        if not title:
            return jsonify({'error': 'Movie title is required'}), 400
        
        director = (data.get('director_name') or '').strip()
        actor_1 = (data.get('actor_1_name') or '').strip()
        actor_2 = (data.get('actor_2_name') or '').strip()
        actor_3 = (data.get('actor_3_name') or '').strip()
        genres = (data.get('genres') or '').strip()
        tags = (data.get('tags') or '').strip()
        
        try:
            db = get_db()
            db.execute(f"""
                UPDATE {MOVIES_TABLE}
                SET director_name=?, actor_1_name=?, actor_2_name=?, actor_3_name=?, 
                    genres=?, movie_title=?, tags=?, movie_title_lower=?
                WHERE rowid = ?
            """, (director, actor_1, actor_2, actor_3, genres, title, tags, title.lower(), movie_id))
            db.commit()
            db.close()
            # Return JSON for AJAX clients, otherwise redirect back to the index page
            if request.is_json:
                return jsonify({'status': 'ok', 'message': f"Movie '{title}' updated successfully"}), 200
            return redirect(url_for('index'))
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request: show form with existing data
    return render_template('edit_movie.html', movie=movie)

@app.route('/delete/<int:movie_id>', methods=['POST'])
def delete_movie(movie_id):
    """Delete a movie from the database."""
    db = get_db()
    movie = db.execute(f"SELECT movie_title FROM {MOVIES_TABLE} WHERE rowid = ?", (movie_id,)).fetchone()
    
    if not movie:
        db.close()
        return jsonify({'error': 'Movie not found'}), 404
    
    try:
        db.execute(f"DELETE FROM {MOVIES_TABLE} WHERE rowid = ?", (movie_id,))
        db.commit()
        title = movie['movie_title']
        db.close()
        if request.is_json:
            return jsonify({'status': 'ok', 'message': f"Movie '{title}' deleted successfully"}), 200
        return redirect(url_for('index'))
    except Exception as e:
        db.close()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        return (str(e), 500)

@app.route('/api/movies', methods=['GET'])
def api_movies():
    """API endpoint to fetch all movies (for dashboard updates)."""
    db = get_db()
    movies = db.execute(f"SELECT rowid, * FROM {MOVIES_TABLE} ORDER BY movie_title").fetchall()
    db.close()
    return jsonify([dict(m) for m in movies])


@app.route('/reports', methods=['GET'])
def reports():
    """Admin reports view - list stored bug reports."""
    db = get_db()
    rows = db.execute('SELECT report_id, user_id, subject, description, created_at FROM bug_reports ORDER BY created_at DESC').fetchall()
    db.close()
    reports = [dict(r) for r in rows]
    return render_template('admin_reports.html', reports=reports)


@app.route('/reports/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    db = get_db()
    row = db.execute('SELECT report_id FROM bug_reports WHERE report_id = ?', (report_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': 'Report not found'}), 404
    try:
        db.execute('DELETE FROM bug_reports WHERE report_id = ?', (report_id,))
        db.commit()
        db.close()
        if request.is_json:
            return jsonify({'status': 'ok', 'message': f'Report {report_id} deleted'}), 200
        return redirect(url_for('reports'))
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)

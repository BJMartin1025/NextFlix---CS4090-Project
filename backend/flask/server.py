# server.py  (replacement - removes similarity.pkl & pandas)
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
from pathlib import Path
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# -----------------------
# CONFIG
# -----------------------
DATABASE = "movies.db"      # path to your sqlite database file
MOVIES_TABLE = "movies_flat"

# separators for genres/tags/actor fields (handles '|' , ',' , ';')
SPLIT_RE = re.compile(r'\s*[|,;]\s*')

# -----------------------
# DB helpers
# -----------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_path = Path(DATABASE)
        if not db_path.exists():
            raise RuntimeError(f"Database file not found: {DATABASE}. Create it first.")
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def row_to_dict(row):
    return {k: row[k] for k in row.keys()}

def split_field(s):
    if s is None:
        return []
    s = str(s).strip()
    if s == "":
        return []
    return [part.strip().lower() for part in SPLIT_RE.split(s) if part.strip()]

# -----------------------
# SEARCH endpoint
# Supports query params:
#   - title (partial match)
#   - genre (partial or full)
#   - director (partial or full)
#   - actor (partial or full)
#
# Example: /search?title=matrix
#          /search?genre=action&actor=reeves
# -----------------------
@app.route("/search", methods=["GET"])
def search():
    params = []
    where_clauses = []

    title = request.args.get("title")
    genre = request.args.get("genre")
    director = request.args.get("director")
    actor = request.args.get("actor")
    limit = int(request.args.get("limit", 100))

    if title:
        where_clauses.append("LOWER(movie_title) LIKE ?")
        params.append(f"%{title.strip().lower()}%")
    if director:
        where_clauses.append("LOWER(director_name) LIKE ?")
        params.append(f"%{director.strip().lower()}%")
    if actor:
        # check actor_1_name, actor_2_name, actor_3_name
        sub = "(LOWER(actor_1_name) LIKE ? OR LOWER(actor_2_name) LIKE ? OR LOWER(actor_3_name) LIKE ?)"
        where_clauses.append(sub)
        aterm = f"%{actor.strip().lower()}%"
        params.extend([aterm, aterm, aterm])
    if genre:
        # genre field contains a delimited list - partial match ok
        where_clauses.append("LOWER(genres) LIKE ?")
        params.append(f"%{genre.strip().lower()}%")

    sql = f"SELECT * FROM {MOVIES_TABLE}"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " LIMIT ?"
    params.append(limit)

    db = get_db()
    cur = db.execute(sql, params)
    rows = cur.fetchall()
    results = [row_to_dict(r) for r in rows]
    return jsonify({"count": len(results), "results": results})

# -----------------------
# SIMILAR endpoint
# Given a movie title, find similar movies by overlapping director/actors/genres/tags.
# Query param: title (required), top (optional, default 5)
# Returns: list of movie records with 'score' float
# -----------------------
@app.route("/similar", methods=["GET"])
def similar():
    title_raw = request.args.get("title", "")
    if not title_raw:
        return jsonify({"error": "Missing 'title' query parameter"}), 400
    top_n = int(request.args.get("top", 5))
    title = title_raw.strip().lower()

    db = get_db()

    # find the target movie row (case-insensitive exact match or best partial match)
    cur = db.execute(f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(TRIM(movie_title)) = ? LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        # try partial match (first match)
        cur = db.execute(f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(movie_title) LIKE ? LIMIT 1", (f"%{title}%",))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Movie not found"}), 404

    target = row_to_dict(row)

    # extract features from target
    target_director = target.get("director_name", "")
    target_actors = []
    for col in ("actor_1_name", "actor_2_name", "actor_3_name"):
        v = target.get(col)
        if v:
            target_actors.extend(split_field(v))
    target_genres = split_field(target.get("genres", ""))
    target_tags = split_field(target.get("tags", ""))

    # Build candidate SQL: any row that shares director, actor, genre, or tag.
    # We'll construct OR clauses for director equality, actor columns (LIKE), and genres/tags LIKE
    candidate_clauses = []
    candidate_params = []

    # director equality (normalized lower)
    if target_director:
        candidate_clauses.append("LOWER(director_name) = ?")
        candidate_params.append(target_director.strip().lower())

    # actors - check any actor column equals any actor name (lowered)
    for actor_name in target_actors:
        # match exact actor names in any actor column
        candidate_clauses.append("(LOWER(actor_1_name) = ? OR LOWER(actor_2_name) = ? OR LOWER(actor_3_name) = ?)")
        candidate_params.extend([actor_name, actor_name, actor_name])

    # genres/tags - partial match with LIKE (match any genre/tag string)
    for g in target_genres:
        candidate_clauses.append("LOWER(genres) LIKE ?")
        candidate_params.append(f"%{g}%")
    for t in target_tags:
        candidate_clauses.append("LOWER(tags) LIKE ?")
        candidate_params.append(f"%{t}%")

    # fallback: if no features found, return empty
    if not candidate_clauses:
        return jsonify({"error": "No metadata available for this movie to compute similarity"}), 400

    # exclude the movie itself; we'll compare by movie_title (normalized)
    sql = f"""
        SELECT * FROM {MOVIES_TABLE}
        WHERE ({' OR '.join(candidate_clauses)})
          AND LOWER(TRIM(movie_title)) != ?
    """
    candidate_params.append(title)  # exclude target
    # limit the number of candidates fetched to a reasonable amount to compute scoring
    sql += " LIMIT 1000"

    cur = db.execute(sql, candidate_params)
    candidates = [row_to_dict(r) for r in cur.fetchall()]

    # Scoring function (weights)
    # same director -> +5
    # each shared actor -> +3
    # each shared genre -> +1
    # each shared tag -> +0.5
    def score_candidate(candidate):
        s = 0.0
        # director
        cand_dir = (candidate.get("director_name") or "").strip().lower()
        if cand_dir and target_director and cand_dir == target_director.strip().lower():
            s += 5.0
        # actors
        cand_actors = []
        for c in ("actor_1_name", "actor_2_name", "actor_3_name"):
            cand_actors.extend(split_field(candidate.get(c, "")))
        # count unique overlaps
        shared_actors = set(cand_actors).intersection(set(target_actors))
        s += 3.0 * len(shared_actors)
        # genres
        cand_genres = set(split_field(candidate.get("genres", "")))
        shared_genres = cand_genres.intersection(set(target_genres))
        s += 1.0 * len(shared_genres)
        # tags
        cand_tags = set(split_field(candidate.get("tags", "")))
        shared_tags = cand_tags.intersection(set(target_tags))
        s += 0.5 * len(shared_tags)
        return s

    scored = []
    for c in candidates:
        sc = score_candidate(c)
        if sc > 0:
            c_with_score = dict(c)
            c_with_score["score"] = sc
            scored.append(c_with_score)

    # sort descending by score, then by movie_title to stabilize output
    scored_sorted = sorted(scored, key=lambda r: (-r["score"], r.get("movie_title","")))

    # return top_n
    top_results = scored_sorted[:top_n]

    return jsonify({
        "target": {"movie_title": target.get("movie_title")},
        "count_candidates": len(candidates),
        "recommendations": top_results
    })


# -----------------------
# optional simple endpoint to return a single movie by title
# -----------------------
@app.route("/movie", methods=["GET"])
def movie_details():
    title_raw = request.args.get("title", "")
    if not title_raw:
        return jsonify({"error": "Missing 'title' query parameter"}), 400
    title = title_raw.strip().lower()
    db = get_db()
    cur = db.execute(f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(TRIM(movie_title)) = ? LIMIT 1", (title,))
    row = cur.fetchone()
    if not row:
        # try partial
        cur = db.execute(f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(movie_title) LIKE ? LIMIT 1", (f"%{title}%",))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Movie not found"}), 404
    return jsonify(row_to_dict(row))

# -----------------------
# home
# -----------------------
@app.route("/")
def home():
    return {"message": "Recommendation backend (DB-based) running"}

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    movie_name = data['movie_name'].strip().lower()

    try:
        # Attempt to find the movie index
        movie_index = final_data[final_data['movie_title'] == movie_name].index[0]
        distances = similarity[movie_index]
        recommended_movies_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:11]

        # Prepare the recommendations
        recommendations = [final_data.iloc[i[0]].movie_title for i in recommended_movies_list]

        return jsonify({"recommendations": recommendations})
    except IndexError:
        # Add logging for debugging purposes
        app.logger.error(f'Movie title "{movie_name}" not found in the dataset')
        return jsonify({"error": "Movie title not found"}), 404
    except Exception as e:
        app.logger.error(f'An error occurred: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/movie', methods=['GET'])
def movie_details():
    """Return details for a movie by title. Query param: title="..." (case-insensitive)"""
    title = request.args.get('title', '')
    if not title:
        return jsonify({"error": "title query parameter required"}), 400
    t = title.strip().lower()
    try:
        rows = final_data[final_data['movie_title'] == t]
        if rows.empty:
            return jsonify({"error": "movie not found"}), 404
        row = rows.iloc[0]
        details = {
            'movie_title': row.get('movie_title'),
            'director_name': row.get('director_name'),
            'actor_1_name': row.get('actor_1_name'),
            'actor_2_name': row.get('actor_2_name'),
            'actor_3_name': row.get('actor_3_name'),
            'genres': row.get('genres'),
            'tags': row.get('tags') if 'tags' in row.index else None,
        }
        return jsonify({'details': details}), 200
    except Exception as e:
        app.logger.error(f'Error fetching movie details: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/catalog/options', methods=['GET'])
def catalog_options():
    """Return lists of distinct movies, directors, actors, and genres from the CSV dataset."""
    try:
        movies = final_data['movie_title'].dropna().astype(str).str.strip().unique().tolist()
        directors = final_data['director_name'].dropna().astype(str).str.strip().unique().tolist()

        # actors: combine actor_1_name, actor_2_name, actor_3_name
        actors = []
        for col in ['actor_1_name', 'actor_2_name', 'actor_3_name']:
            if col in final_data.columns:
                vals = final_data[col].dropna().astype(str).str.strip().unique().tolist()
                actors.extend(vals)
        actors = sorted(list(set([a for a in actors if a and a.lower() != 'unknown'])))

        # genres: split on common separators (|, comma, space) — the dataset uses space-separated multi-genres
        genre_set = set()
        if 'genres' in final_data.columns:
            for g in final_data['genres'].dropna().astype(str):
                # split on comma or pipe or slash, else on space
                parts = []
                if ',' in g:
                    parts = [p.strip() for p in g.split(',')]
                elif '|' in g:
                    parts = [p.strip() for p in g.split('|')]
                else:
                    parts = [p.strip() for p in g.split()]
                for p in parts:
                    if p:
                        genre_set.add(p)

        genres = sorted(list(genre_set))

        return jsonify({
            'movies': sorted(movies),
            'directors': sorted([d for d in directors if d and d.lower() != 'unknown']),
            'actors': actors,
            'genres': genres
        }), 200
    except Exception as e:
        app.logger.error(f'Error building catalog options: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/recommend/user', methods=['POST'])
def recommend_for_user():
    """Generate recommendations for a user based on their stored preferences.
    Expected JSON: { "user_id": "...", "top_n": 10 }
    Strategy:
      - If user has favorite movies, average their similarity vectors.
      - Apply simple attribute boosts for matching genres, directors, actors.
    """
    try:
        data = request.json or {}
        user_id = data.get('user_id')
        top_n = int(data.get('top_n', 10))
        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        profile = user_profiles.get(user_id)
        if not profile:
            return jsonify({"error": "user profile not found"}), 404

        prefs = {}
        if isinstance(profile, dict) and 'preferences' in profile:
            prefs = profile.get('preferences', {})
        elif isinstance(profile, dict) and all(k in profile for k in ('movies', 'genres', 'directors', 'actors')):
            prefs = {
                'movies': profile.get('movies', []),
                'genres': profile.get('genres', []),
                'directors': profile.get('directors', []),
                'actors': profile.get('actors', []),
            }
        else:
            prefs = profile.get('preferences', {}) if isinstance(profile, dict) else {}

        # Normalize preference lists to lowercase
        pref_movies = [m.strip().lower() for m in prefs.get('movies', []) if m]
        pref_genres = [g.strip().lower() for g in prefs.get('genres', []) if g]
        pref_directors = [d.strip().lower() for d in prefs.get('directors', []) if d]
        pref_actors = [a.strip().lower() for a in prefs.get('actors', []) if a]

        if not (pref_movies or pref_genres or pref_directors or pref_actors):
            return jsonify({"error": "no preferences found for user"}), 400

        n = len(final_data)
        combined_scores = np.zeros(n, dtype=float)

        # Base score from favorite movies via similarity
        base_scores = np.zeros(n, dtype=float)
        count = 0
        for m in pref_movies:
            idxs = final_data[final_data['movie_title'] == m].index
            if len(idxs) > 0:
                idx = idxs[0]
                try:
                    base_scores += np.array(similarity[idx])
                    count += 1
                except Exception:
                    pass

        if count > 0:
            base_scores = base_scores / float(count)
            # normalize base_scores to 0..1
            if base_scores.max() > base_scores.min():
                bs_norm = (base_scores - base_scores.min()) / (base_scores.max() - base_scores.min())
            else:
                bs_norm = np.zeros_like(base_scores)
        else:
            bs_norm = np.zeros(n, dtype=float)

        # Attribute boosts
        boost = np.zeros(n, dtype=float)
        for i, row in final_data.iterrows():
            score = 0
            # genres: row may be a string like 'Action Adventure'
            row_genres = str(row.get('genres', '') or '').lower()
            row_director = str(row.get('director_name', '') or '').strip().lower()
            actors_concat = ' '.join([str(row.get('actor_1_name', '') or ''), str(row.get('actor_2_name', '') or ''), str(row.get('actor_3_name', '') or '')]).lower()

            if pref_genres:
                for g in pref_genres:
                    if g and g in row_genres:
                        score += 1
                        break

            if pref_directors:
                for d in pref_directors:
                    if d and d in row_director:
                        score += 1
                        break

            if pref_actors:
                for a in pref_actors:
                    if a and a in actors_concat:
                        score += 1
                        break

            boost[i] = score

        # normalize boost to 0..1 (max possible 3)
        if boost.max() > 0:
            boost_norm = boost / max(boost.max(), 1.0)  # divides by max to scale to 0..1
        else:
            boost_norm = boost

        # Combine normalized similarity and boosts. We weight them so base movie similarity is stronger when available.
        combined = bs_norm * 0.8 + boost_norm * 0.4

        # Remove any movies that are explicitly in the user's favorites (don't recommend exact same)
        exclude = set(pref_movies)
        scored = list(enumerate(combined))
        scored = [s for s in scored if final_data.iloc[s[0]].movie_title not in exclude]

        recommended = sorted(scored, reverse=True, key=lambda x: x[1])[:top_n]
        recommendations = [final_data.iloc[i[0]].movie_title for i in recommended]

        return jsonify({"recommendations": recommendations})
    except Exception as e:
        app.logger.error(f'Error generating user recommendations: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/user/preferences', methods=['POST'])
def save_preferences():
    """Save or update a user's preferences in the in-memory store.
    Expected JSON body: { "user_id": "string", "preferences": { ... } }
    """
    try:
        data = request.json
        user_id = data.get('user_id')
        preferences = data.get('preferences')
        if not user_id or preferences is None:
            return jsonify({"error": "Missing user_id or preferences"}), 400

        # Merge preferences into existing profile instead of overwriting.
        # Normalize incoming structure to lists for the expected keys.
        incoming = {
            'movies': list(preferences.get('movies', [])) if isinstance(preferences.get('movies', []), (list, tuple)) else [],
            'genres': list(preferences.get('genres', [])) if isinstance(preferences.get('genres', []), (list, tuple)) else [],
            'directors': list(preferences.get('directors', [])) if isinstance(preferences.get('directors', []), (list, tuple)) else [],
            'actors': list(preferences.get('actors', [])) if isinstance(preferences.get('actors', []), (list, tuple)) else [],
        }

        # Ensure profile dict exists
        profile = user_profiles.setdefault(user_id, {})

        # Existing preferences may previously have been stored directly as a dict (old format)
        existing_prefs = {}
        if isinstance(profile, dict) and 'preferences' in profile:
            existing_prefs = profile.get('preferences', {})
        elif isinstance(profile, dict) and all(k in profile for k in ('movies', 'genres', 'directors', 'actors')):
            # older code may have stored preferences directly at profile
            existing_prefs = {
                'movies': profile.get('movies', []),
                'genres': profile.get('genres', []),
                'directors': profile.get('directors', []),
                'actors': profile.get('actors', []),
            }
        else:
            existing_prefs = profile.get('preferences', {}) if isinstance(profile, dict) else {}

        # Helper to merge lists uniquely while preserving order
        def merge_lists(old, new):
            result = list(old) if isinstance(old, (list, tuple)) else []
            for item in new:
                if item and item not in result:
                    result.append(item)
            return result

        merged = {
            'movies': merge_lists(existing_prefs.get('movies', []), incoming['movies']),
            'genres': merge_lists(existing_prefs.get('genres', []), incoming['genres']),
            'directors': merge_lists(existing_prefs.get('directors', []), incoming['directors']),
            'actors': merge_lists(existing_prefs.get('actors', []), incoming['actors']),
        }

        # Store under unified profile structure
        profile['preferences'] = merged
        user_profiles[user_id] = profile

        return jsonify({"status": "saved", "user_id": user_id, "preferences": merged}), 200
    except Exception as e:
        app.logger.error(f'Error saving preferences: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/user/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    """Retrieve stored preferences for a given user_id."""
    profile = user_profiles.get(user_id)
    if profile is None:
        return jsonify({"error": "preferences not found"}), 404

    # Support both new profile format (dict with 'preferences') and legacy direct preferences
    if isinstance(profile, dict):
        if 'preferences' in profile:
            prefs = profile.get('preferences', {})
        else:
            # legacy support: profile might directly be the preferences dict
            prefs = {
                'movies': profile.get('movies', []),
                'genres': profile.get('genres', []),
                'directors': profile.get('directors', []),
                'actors': profile.get('actors', []),
            }
    else:
        prefs = profile

    return jsonify({"user_id": user_id, "preferences": prefs}), 200


@app.route('/user/feedback', methods=['POST'])
def save_feedback():
    """Save user feedback (rating + optional text) under the user's profile.
    Expected JSON body: { "user_id": "string", "movie": "title", "rating": int, "text": "optional" }
    """
    try:
        data = request.json
        user_id = data.get('user_id')
        movie = data.get('movie')
        rating = data.get('rating')
        text = data.get('text', '')

        if not user_id or not movie or rating is None:
            return jsonify({"error": "Missing user_id, movie, or rating"}), 400

        # Ensure profile exists
        profile = user_profiles.setdefault(user_id, {})

        # Store feedback as a list of entries under 'feedback'
        feedback_list = profile.setdefault('feedback', [])
        entry = {
            'movie': movie,
            'rating': int(rating),
            'text': text,
        }
        feedback_list.append(entry)

        return jsonify({"status": "saved", "entry": entry}), 200
    except Exception as e:
        app.logger.error(f'Error saving feedback: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/user/feedback/<user_id>', methods=['GET'])
def get_feedback(user_id):
    """Retrieve saved feedback entries for a user."""
    profile = user_profiles.get(user_id)
    if not profile or 'feedback' not in profile:
        return jsonify({"feedback": []}), 200
    return jsonify({"user_id": user_id, "feedback": profile['feedback']}), 200


@app.route('/reports', methods=['POST'])
def submit_report():
    """Submit a bug/issue report. Expected JSON body: { user_id?, subject, description }
    Stores in-memory under `bug_reports` with timestamp and an id.
    """
    try:
        data = request.json or {}
        subject = data.get('subject', '').strip()
        description = data.get('description', '').strip()
        user_id = data.get('user_id')

        if not subject or not description:
            return jsonify({"error": "subject and description are required"}), 400

        import time, uuid
        entry = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'subject': subject,
            'description': description,
            'timestamp': int(time.time())
        }
        bug_reports.append(entry)
        return jsonify({"status": "received", "report": entry}), 201
    except Exception as e:
        app.logger.error(f'Error submitting report: {e}')
        return jsonify({"error": str(e)}), 500


@app.route('/reports', methods=['GET'])
def list_reports():
    """Return all submitted reports. (No auth for now; add admin protection later.)"""
    return jsonify({"reports": bug_reports}), 200

if __name__ == '__main__':
    app.run(debug=True)

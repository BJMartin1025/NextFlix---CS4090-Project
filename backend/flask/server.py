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

# separators for genres/tags/actor fields (handles spaces, '|', ',', ';', '/', '&', and the word 'and')
SPLIT_RE = re.compile(r'(?:\s+|[|,;/&]|\band\b)', re.IGNORECASE)

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

    # optional user_id parameter: exclude user's watchlist/seen from results
    user_id_param = request.args.get('user_id')
    user_watchlist = set()
    user_seen = set()
    if user_id_param:
        u = user_profiles.get(user_id_param)
        if u:
            user_watchlist = set([m.lower().strip() for m in (u.get('watchlist') or [])])
            user_seen = set([m.lower().strip() for m in (u.get('seen') or [])])

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
        # skip if candidate is in user's watchlist or seen list
        c_title = (c.get('movie_title') or '').strip().lower()
        if c_title and (c_title in user_watchlist or c_title in user_seen):
            continue
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
# Catalog options (movies, directors, actors, genres)
# -----------------------
@app.route('/catalog/options', methods=['GET'])
def catalog_options():
    db = get_db()
    # movies
    movies = [r[0] for r in db.execute(f"SELECT DISTINCT movie_title FROM {MOVIES_TABLE} WHERE movie_title IS NOT NULL").fetchall()]
    # directors
    directors = [r[0] for r in db.execute(f"SELECT DISTINCT director_name FROM {MOVIES_TABLE} WHERE director_name IS NOT NULL").fetchall()]
    # actors (collect from actor_1/2/3)
    actors = set()
    for col in ('actor_1_name', 'actor_2_name', 'actor_3_name'):
        rows = db.execute(f"SELECT DISTINCT {col} FROM {MOVIES_TABLE} WHERE {col} IS NOT NULL").fetchall()
        for r in rows:
            v = r[0]
            if v:
                actors.add(v)
    # genres - split and unique
    genres_set = set()
    rows = db.execute(f"SELECT genres FROM {MOVIES_TABLE} WHERE genres IS NOT NULL").fetchall()
    for r in rows:
        val = r[0]
        if val:
            parts = SPLIT_RE.split(val)
            for p in parts:
                t = p.strip()
                if t:
                    genres_set.add(t)

    return jsonify({
        'movies': sorted(movies),
        'directors': sorted([d for d in directors if d]),
        'actors': sorted(list(actors)),
        'genres': sorted(list(genres_set))
    })


# -----------------------
# In-memory user/profile and reports storage (simple)
# -----------------------
user_profiles = {}
bug_reports = []


@app.route('/user/preferences', methods=['POST'])
def save_preferences():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    prefs = data.get('preferences')
    if not user_id or prefs is None:
        return jsonify({'error': 'user_id and preferences required'}), 400
    user = user_profiles.setdefault(user_id, {})
    # Merge incoming preferences with existing ones (append, dedupe case-insensitive)
    existing = user.get('preferences', {})

    def merge_lists(old, new):
        old_list = old or []
        new_list = new or []
        seen = {v.strip().lower(): v for v in old_list if v}
        merged = list(old_list)[:]  # preserve existing order
        for v in new_list:
            if not v: 
                continue
            key = v.strip().lower()
            if key not in seen:
                merged.append(v)
                seen[key] = v
        return merged

    merged_prefs = {
        'movies': merge_lists(existing.get('movies'), prefs.get('movies')),
        'genres': merge_lists(existing.get('genres'), prefs.get('genres')),
        'directors': merge_lists(existing.get('directors'), prefs.get('directors')),
        'actors': merge_lists(existing.get('actors'), prefs.get('actors')),
    }

    user['preferences'] = merged_prefs
    return jsonify({'status': 'ok', 'user_id': user_id, 'preferences': merged_prefs})


@app.route('/user/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    user = user_profiles.get(user_id, {})
    return jsonify({'user_id': user_id, 'preferences': user.get('preferences', {})})


@app.route('/user/feedback', methods=['POST'])
def save_feedback():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie = data.get('movie')
    rating = data.get('rating')
    text = data.get('text')
    entry = {'movie': movie, 'rating': rating, 'text': text}
    if user_id:
        user = user_profiles.setdefault(user_id, {})
        fb = user.setdefault('feedback', [])
        fb.append(entry)
    else:
        # anonymous feedback - append to global list under None
        anon = user_profiles.setdefault('__anonymous__', {})
        afb = anon.setdefault('feedback', [])
        afb.append(entry)
    return jsonify({'status': 'ok'})


@app.route('/user/feedback/<user_id>', methods=['GET'])
def get_feedback(user_id):
    user = user_profiles.get(user_id, {})
    return jsonify({'user_id': user_id, 'feedback': user.get('feedback', [])})


@app.route('/user/watchlist', methods=['POST'])
def add_watchlist():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie = data.get('movie')
    if not user_id or not movie:
        return jsonify({'error': 'user_id and movie required'}), 400
    user = user_profiles.setdefault(user_id, {})
    wl = user.setdefault('watchlist', [])
    # dedupe case-insensitive
    low = {m.strip().lower() for m in wl if m}
    if movie.strip().lower() not in low:
        wl.append(movie)
    return jsonify({'status': 'ok', 'watchlist': wl})


@app.route('/user/watchlist/remove', methods=['POST'])
def remove_watchlist():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie = data.get('movie')
    if not user_id or not movie:
        return jsonify({'error': 'user_id and movie required'}), 400
    user = user_profiles.setdefault(user_id, {})
    wl = user.get('watchlist', [])
    new_wl = [m for m in wl if m.strip().lower() != movie.strip().lower()]
    user['watchlist'] = new_wl
    return jsonify({'status': 'ok', 'watchlist': new_wl})


@app.route('/user/watchlist/<user_id>', methods=['GET'])
def get_watchlist(user_id):
    user = user_profiles.get(user_id, {})
    return jsonify({'user_id': user_id, 'watchlist': user.get('watchlist', [])})


@app.route('/user/favorites', methods=['POST'])
def add_favorite():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie = data.get('movie')
    if not user_id or not movie:
        return jsonify({'error': 'user_id and movie required'}), 400
    user = user_profiles.setdefault(user_id, {})
    # ensure preferences.movies contains it (merge)
    prefs = user.setdefault('preferences', {})
    movies = prefs.setdefault('movies', [])
    low = {m.strip().lower() for m in movies if m}
    if movie.strip().lower() not in low:
        movies.append(movie)
    favs = user.setdefault('favorites', [])
    if movie.strip().lower() not in {f.strip().lower() for f in favs if f}:
        favs.append(movie)
    return jsonify({'status': 'ok', 'favorites': favs, 'preferences': prefs})


@app.route('/user/seen', methods=['POST'])
def mark_seen():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie = data.get('movie')
    if not user_id or not movie:
        return jsonify({'error': 'user_id and movie required'}), 400
    user = user_profiles.setdefault(user_id, {})
    seen = user.setdefault('seen', [])
    low = {m.strip().lower() for m in seen if m}
    if movie.strip().lower() not in low:
        seen.append(movie)
    # also remove from watchlist if present
    wl = user.get('watchlist', [])
    user['watchlist'] = [m for m in wl if m.strip().lower() != movie.strip().lower()]
    return jsonify({'status': 'ok', 'seen': seen, 'watchlist': user.get('watchlist', [])})


# -----------------------
# Recommend from user preferences (POST) - returns list of titles
# -----------------------
@app.route('/recommend/user', methods=['POST'])
def recommend_from_user():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    top_n = int(data.get('top_n', 10))
    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    user = user_profiles.get(user_id)
    if not user or 'preferences' not in user:
        return jsonify({'error': 'No preferences found for user'}), 404
    prefs = user['preferences']
    pref_movies = set([m.lower().strip() for m in (prefs.get('movies') or [])])
    pref_directors = set([d.lower().strip() for d in (prefs.get('directors') or [])])
    pref_actors = set([a.lower().strip() for a in (prefs.get('actors') or [])])
    pref_genres = set([g.lower().strip() for g in (prefs.get('genres') or [])])
    pref_watchlist = set([w.lower().strip() for w in (user.get('watchlist') or [])])
    pref_seen = set([s.lower().strip() for s in (user.get('seen') or [])])

    db = get_db()
    cur = db.execute(f"SELECT * FROM {MOVIES_TABLE}")
    candidates = [row_to_dict(r) for r in cur.fetchall()]

    def score_movie(m):
        s = 0.0
        title = (m.get('movie_title') or '').strip().lower()
        if title in pref_movies:
            s += 6.0
        director = (m.get('director_name') or '').strip().lower()
        if director and director in pref_directors:
            s += 5.0
        # actors
        actors = set()
        for col in ('actor_1_name', 'actor_2_name', 'actor_3_name'):
            actors.update(split_field(m.get(col, '')))
        s += 3.0 * len(actors.intersection(pref_actors))
        # genres
        genres = set(split_field(m.get('genres', '')))
        s += 1.0 * len(genres.intersection(pref_genres))
        return s

    scored = []
    for m in candidates:
        title = (m.get('movie_title') or '').strip().lower()
        # skip user's favorite movies, seen movies, and items on their watchlist
        if title in pref_movies or title in pref_seen or title in pref_watchlist:
            continue
        sc = score_movie(m)
        if sc > 0:
            scored.append((sc, m.get('movie_title')))

    scored_sorted = sorted(scored, key=lambda x: (-x[0], x[1] or ''))
    titles = [t for _, t in scored_sorted[:top_n]]
    return jsonify({'recommendations': titles})


@app.route('/reports', methods=['POST'])
def create_report():
    data = request.get_json() or {}
    report = {
        'id': len(bug_reports) + 1,
        'user_id': data.get('user_id'),
        'subject': data.get('subject'),
        'description': data.get('description')
    }
    bug_reports.append(report)
    return jsonify({'status': 'ok', 'report': report})


@app.route('/reports', methods=['GET'])
def list_reports():
    return jsonify({'reports': bug_reports})


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

@app.route('/directors/movies', methods=['GET'])
def director_movies():
    """
    Minimal director search:
      GET /directors/movies?name=<director name>&limit=<n>

    Returns:
      { "director": "<input>", "count": N, "movies": [ {movie row}, ... ] }
    Behavior:
      - tries exact (normalized) match first, then partial LIKE match
      - does not modify any existing data or endpoints
    """
    name_raw = (request.args.get('name') or '').strip()
    if not name_raw:
        return jsonify({'error': 'Missing "name" query parameter'}), 400

    name_normalized = name_raw.lower()
    limit = int(request.args.get('limit', 200))

    db = get_db()

    # 1) Try exact normalized match (fast & precise)
    rows = db.execute(
        f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(TRIM(director_name)) = ? LIMIT ?",
        (name_normalized, limit)
    ).fetchall()

    # 2) If no exact match, try a partial match (case-insensitive)
    if not rows:
        rows = db.execute(
            f"SELECT * FROM {MOVIES_TABLE} WHERE LOWER(director_name) LIKE ? LIMIT ?",
            (f"%{name_normalized}%", limit)
        ).fetchall()

    movies = [row_to_dict(r) for r in rows]
    return jsonify({'director': name_raw, 'count': len(movies), 'movies': movies})


if __name__ == "__main__":
    app.run(debug=True)

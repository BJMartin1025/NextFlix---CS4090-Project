# server.py  (replacement - removes similarity.pkl & pandas)
from flask import Flask, request, jsonify, g
from flask_cors import CORS
import sqlite3
from pathlib import Path
import re
import os
import json
import time
import requests
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# -----------------------
# CONFIG
# -----------------------
DATABASE = "movies.db"      # path to your sqlite database file
# Synopsis API
SYNOPSIS_API = os.getenv('SYNOPSIS_API_URL', 'http://www.omdbapi.com/')
SYNOPSIS_API_KEY = os.getenv('SYNOPSIS_API_KEY', '4a6314f4')
MOVIES_TABLE = "movies_flat"

RATINGS_API = SYNOPSIS_API
RATINGS_API_KEY = SYNOPSIS_API_KEY

WATCHMODE_API_KEY = os.getenv("WATCHMODE_API_KEY", 'GXKqlpArRvRxohWux2fVGLIGeTMbOLSsOipWtRiG')
WATCHMODE_SEARCH_URL = "https://api.watchmode.com/v1/search/"
WATCHMODE_SOURCES_URL = "https://api.watchmode.com/v1/title/{id}/sources/"

MAX_RETRIES = 2
INITIAL_DELAY = 1.0  # seconds

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
# Kafka producer (event stream)
# -----------------------
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
producer = None
if KAFKA_BOOTSTRAP:
    try:
        from kafka import KafkaProducer
        producer = KafkaProducer(
            bootstrap_servers=[h.strip() for h in KAFKA_BOOTSTRAP.split(',')],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print('Kafka producer initialized')
    except Exception as e:
        print('Failed to initialize Kafka producer:', e)


def publish_event(event_type, payload):
    """Publish an event to Kafka, or log it if producer is not initialized."""
    event = {
        'type': event_type,
        'payload': payload,
        'timestamp': time.time()
    }
    if producer:
        try:
            producer.send('nextflix-events', event)
            producer.flush()
            logger.info("Kafka event sent: %s", event_type)
        except Exception as e:
            logger.error("Kafka send error for event '%s': %s", event_type, e)
    else:
        # fallback logging when Kafka is not initialized
        logger.info("Kafka producer not initialized. Event: %s", event)

def fetch_streaming_platforms(title):
    """
    Fetch streaming platform availability for a movie using the Watchmode API.
    Steps:
      1. Search for the movie → get title_id
      2. Fetch streaming sources for that title_id
    Returns:
        list[str]: A deduplicated list of platform names (e.g., ["Netflix", "Hulu"])
    """

    print(f"fetch_streaming_platforms: title='{title}'")

    # No API key → skip
    if not WATCHMODE_API_KEY:
        print("fetch_streaming_platforms: WATCHMODE_API_KEY missing.")
        return []

    # -------------------------------
    # Step 1: SEARCH for movie title
    # -------------------------------
    movie_id = None

    for attempt in range(MAX_RETRIES):
        try:
            params = {
                "apiKey": WATCHMODE_API_KEY,
                "search_field": "name",
                "search_value": title,
                "type": "movie"
            }

            print(f"Search Attempt {attempt + 1}: {WATCHMODE_SEARCH_URL} {params}")
            resp = requests.get(WATCHMODE_SEARCH_URL, params=params, timeout=6)
            resp.raise_for_status()

            data = resp.json()
            results = data.get("title_results", [])

            if not results:
                print(f"No Watchmode results found for '{title}'")
                return []
            
            # Pick best match = first
            movie_id = results[0]["id"]

            if not movie_id:
                print("Watchmode search result missing ID.")
                return []

            print(f"Found Watchmode movie_id={movie_id} for '{title}'")
            break

        except Exception as e:
            print(f"Watchmode Search Error attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(INITIAL_DELAY * (2 ** attempt))
            else:
                return []
            
    if not movie_id:
        return []

    # ----------------------------------------------
    # Step 2: FETCH streaming sources using title_id
    # ----------------------------------------------
    for attempt in range(MAX_RETRIES):
        try:
            params = {
                "apiKey": WATCHMODE_API_KEY,
                "regions": "US"  # or change per your site
            }

            url = WATCHMODE_SOURCES_URL.format(id=movie_id)
            print(f"Sources Attempt {attempt + 1}: {url} {params}")

            resp = requests.get(url, params=params, timeout=6)
            resp.raise_for_status()

            sources = resp.json()
            if not isinstance(sources, list):
                print("Sources result not a list:", sources)
                return []

            platform_names = set()

            for src in sources:
                # type = "sub" (subscription), "buy", "rent", "free"
                # name = "Netflix", "Hulu", etc.
                name = src.get("name")
                if name:
                    platform_names.add(name)

            platforms_list = sorted(platform_names)
            print(f"Platforms found for '{title}': {platforms_list}")
            return platforms_list

        except Exception as e:
            print(f"Watchmode Sources Error attempt {attempt+1}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(INITIAL_DELAY * (2 ** attempt))
            else:
                return []

    return []


def fetch_synopsis(title):
    """Fetch synopsis/plot for a title using a configured synopsis API (e.g., OMDB).
    Supports OMDB-style `t` param + apikey returning `Plot` in JSON. Returns empty string on failure.
    """
    # Try configured synopsis API first (OMDB-style), then TMDB fallback
    import requests
    # 1) Configured/SYNOPSIS_API (e.g., OMDB)
    if SYNOPSIS_API:
        try:
            params = {'t': title}
            if SYNOPSIS_API_KEY:
                params['apikey'] = SYNOPSIS_API_KEY
            resp = requests.get(SYNOPSIS_API, params=params, timeout=6)
            print(f"fetch_synopsis: SYNOPSIS_API request to {SYNOPSIS_API} returned {resp.status_code}")
            if resp.ok:
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if data:
                    # OMDB returns 'Plot'
                    plot = data.get('Plot') or data.get('plot') or data.get('overview')
                    if plot:
                        return plot
                    # some APIs return description under summary/abstract
                    return data.get('description') or data.get('summary') or ''
            else:
                # show response body for debugging (e.g., OMDB returns 401 with JSON error)
                try:
                    print('fetch_synopsis: SYNOPSIS_API response body:', resp.text)
                except Exception:
                    pass
                if resp.status_code == 401:
                    print('fetch_synopsis: SYNOPSIS_API returned 401 Unauthorized — likely invalid or missing API key')
        except Exception as e:
            print('Synopsis API error:', e)

    return ''

def fetch_ratings(title):
    """
    Fetches IMDb, Rotten Tomatoes, and Metacritic ratings for a movie using the OMDB API.
    
    Args:
        title (str): The title of the movie to search for.
        
    Returns:
        dict: Dictionary containing imdb_score, rotten_tomatoes_score, and metacritic_score.
    """

    params = {
        't': title, # Search by title
        'apikey': RATINGS_API_KEY,
        'plot': 'short', # Get a short synopsis
        'r': 'json'
    }

    for attempt in range(MAX_RETRIES):
        try:
            print(f"OMDB Fetch Attempt {attempt + 1}/{MAX_RETRIES}: Calling OMDB for title={title}")
            
            # Use the dedicated RATINGS_API URL
            response = requests.get(RATINGS_API, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()

            if data.get('Response') == 'True':
                # Initialize scores
                ratings = {
                    "imdb_score": data.get("imdbRating", "N/A"),
                    "rotten_tomatoes_score": "N/A",
                    "metacritic_score": data.get("Metascore", "N/A")
                }
                
                # Extract Rotten Tomatoes and refine Metacritic/IMDb if possible
                for rating in data.get('Ratings', []):
                    source = rating.get('Source')
                    value = rating.get('Value')
                    
                    if source == "Rotten Tomatoes":
                        ratings["rotten_tomatoes_score"] = value
                    
                    # Overwrite based on specific array entry if available
                    if source == "Internet Movie Database":
                        ratings["imdb_score"] = value.split('/')[0] # Usually 7.6/10 -> 7.6
                    
                    if source == "Metacritic":
                         # Metacritic can sometimes be included in the array as well (e.g., 67/100 -> 67)
                        ratings["metacritic_score"] = value.split('/')[0] 

                print(f"OMDB Success: Found ratings for '{title}'.")
                return ratings

            else:
                print(f"OMDB API response failure: {data.get('Error', 'Unknown Error')}")
                return {}

        except requests.exceptions.RequestException as e:
            print(f"OMDB Request Error on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = INITIAL_DELAY * (2 ** attempt)
                print(f"Retrying OMDB call in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Failed to fetch OMDB data for '{title}' after max retries.")
                return {}
        except Exception as e:
            print(f"OMDB General Error: {e}")
            return {}
            
    return {}

def enrich_movie_info(movie):
    """Given a movie dict from the DB, add `synopsis` and `platforms` keys if possible.
    This function is best-effort and will not raise.
    """
    try:
        title = (movie.get('movie_title') or movie.get('title') or '').strip()
        # synopsis: prefer DB fields if present
        for key in ('overview', 'synopsis', 'description', 'plot'):
            if movie.get(key):
                movie['synopsis'] = movie.get(key)
                break
        else:
            # fetch external synopsis if configured
            s = fetch_synopsis(title)
            if s:
                movie['synopsis'] = s
            else:
                movie.setdefault('synopsis', '')

        # streaming platforms
        if 'platforms' not in movie:
            plats = fetch_streaming_platforms(title)
            movie['platforms'] = plats

        # Rotten Tomatoes ratings
        omdb_data = fetch_ratings(title)

        if omdb_data:
            movie['imdb_score'] = omdb_data.get('imdb_score', 'N/A')
            movie['rotten_tomatoes_score'] = omdb_data.get('rotten_tomatoes_score', 'N/A')
            movie['metacritic_score'] = omdb_data.get('metacritic_score', 'N/A')
        else:
            # Ensure the frontend fields are present even if OMDB fails
            movie['imdb_score'] = 'N/A'
            movie['rotten_tomatoes_score'] = 'N/A'
            movie['metacritic_score'] = 'N/A'

        if 'rating' in movie:
            del movie['rating']  # remove old rating field if present

        return movie
    except Exception as e:
        print('enrich_movie_info error:', e)
        movie.setdefault('synopsis', '')
        movie.setdefault('platforms', [])
        movie.setdefault('imdb_score', 'N/A')
        movie.setdefault('rotten_tomatoes_score', 'N/A')
        movie.setdefault('metacritic_score', 'N/A')
        return movie

# -----------------------
# Initialize application DB schema for user-related tables if missing
# -----------------------
def init_db_schema():
    db = get_db()
    cur = db.cursor()
    # Users basic table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_basic (
            user_id TEXT PRIMARY KEY,
            display_name TEXT,
            auth_token TEXT,
            created_at REAL
        )
    ''')
    # User preferences (stores JSON blob)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_preferences (
            user_id TEXT PRIMARY KEY,
            preferences_json TEXT,
            updated_at REAL
        )
    ''')
    # Feedbacks
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            movie_rowid INTEGER,
            movie_title TEXT,
            rating REAL,
            text TEXT,
            created_at REAL
        )
    ''')
    # Watchlists
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users_watchlist (
            list_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            name TEXT,
            created_at REAL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_watchlist_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER,
            movie_rowid INTEGER,
            added_at REAL
        )
    ''')
    # Recommendation records
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            generated_at REAL,
            recommendations_json TEXT
        )
    ''')
    # Persistent Bug Reports
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bug_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at REAL
        )
    ''')

    db.commit()


# Initialize schema at startup
try:
    with app.app_context():
        init_db_schema()
except Exception as e:
    print('Warning: init_db_schema failed:', e)

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
    # enrich results with synopsis/platforms (best-effort)
    enriched = [enrich_movie_info(dict(r)) for r in results]
    publish_event('search_performed', {'title': title, 'genre': genre, 'director': director, 'actor': actor, 'limit': limit})
    return jsonify({"count": len(enriched), "results": enriched})

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

    # Enrich top results with synopsis/platforms
    enriched_top = [enrich_movie_info(dict(r)) for r in top_results]

    publish_event('similar_movies_requested', {'target_title': target.get('movie_title'), 'top_n': top_n, 'user_id': user_id_param})
    return jsonify({
        "target": {"movie_title": target.get("movie_title")},
        "count_candidates": len(candidates),
        "recommendations": enriched_top
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
    # Overwrite stored preferences with the submitted set.
    # This ensures removals (emptying a list or omitting items) persist.
    user = user_profiles.setdefault(user_id, {})
    # normalize to ensure keys exist
    normalized = {
        'movies': prefs.get('movies') or [],
        'genres': prefs.get('genres') or [],
        'directors': prefs.get('directors') or [],
        'actors': prefs.get('actors') or []
    }
    user['preferences'] = normalized

    # persist to DB users_preferences table as JSON for durability
    try:
        db = get_db()
        db.execute(
            'INSERT INTO users_preferences (user_id, preferences_json, updated_at) VALUES (?, ?, ?) '
            'ON CONFLICT(user_id) DO UPDATE SET preferences_json=excluded.preferences_json, updated_at=excluded.updated_at',
            (user_id, json.dumps(normalized), time.time())
        )
        db.commit()
        publish_event('preferences_saved', {'user_id': user_id, 'preferences': normalized})
    except Exception as e:
        print('Failed to persist user preferences to DB:', e)

    return jsonify({'status': 'ok', 'user_id': user_id, 'preferences': normalized})


@app.route('/user/preferences/<user_id>', methods=['GET'])
def get_preferences(user_id):
    # Prefer DB-backed preferences if available
    try:
        prefs = get_user_preferences(user_id)
        return jsonify({'user_id': user_id, 'preferences': prefs})
    except Exception:
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
    publish_event('feedback_created', {'user_id': user_id, 'movie': movie, 'rating': rating})
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

    publish_event('watchlist_movie_added', {'user_id': user_id, 'movie': movie})
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
    publish_event('watchlist_movie_removed', {'user_id': user_id, 'movie': movie})
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
    # Load existing preferences from DB (preferred) or in-memory
    prefs = get_user_preferences(user_id) or user.setdefault('preferences', {})
    # ensure the movies list exists and merge (dedupe)
    movies = prefs.get('movies') or []
    low_movies = {m.strip().lower() for m in movies if m}
    if movie.strip().lower() not in low_movies:
        movies.append(movie)
    prefs['movies'] = movies

    # favorites list (stored inside preferences under key 'favorites')
    favs = prefs.get('favorites') or []
    low_favs = {f.strip().lower() for f in favs if f}
    if movie.strip().lower() not in low_favs:
        favs.append(movie)
    prefs['favorites'] = favs

    # Update in-memory representation as well
    user['preferences'] = prefs
    user['favorites'] = favs

    # Persist back to DB (upsert into users_preferences)
    try:
        db = get_db()
        db.execute(
            'INSERT INTO users_preferences (user_id, preferences_json, updated_at) VALUES (?, ?, ?) '
            'ON CONFLICT(user_id) DO UPDATE SET preferences_json=excluded.preferences_json, updated_at=excluded.updated_at',
            (user_id, json.dumps(prefs), time.time())
        )
        db.commit()
    except Exception as e:
        logger.error('Failed to persist favorites to DB for user %s: %s', user_id, e)

    publish_event('favorite_added', {'user_id': user_id, 'movie': movie})
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
    publish_event('movie_seen', {'user_id': user_id, 'movie': movie})
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
    publish_event('recommendations_generated', {'user_id': user_id, 'count': len(titles)})
    return jsonify({'recommendations': titles})


@app.route('/reports', methods=['POST'])
def create_report():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    subject = data.get('subject')
    description = data.get('description')

    if not subject or not description:
        return jsonify({'error': 'subject and description required'}), 400

    db = get_db()
    now = time.time()
    cur = db.execute(
        'INSERT INTO bug_reports (user_id, subject, description, created_at) VALUES (?, ?, ?, ?)',
        (user_id, subject, description, now)
    )
    db.commit()

    report_id = cur.lastrowid
    report = {
        'id': report_id,
        'user_id': user_id,
        'subject': subject,
        'description': description
    }

    publish_event('bug_report_created', {'report_id': report_id, 'user_id': user_id})
    return jsonify({'status': 'ok', 'report': report})



@app.route('/reports', methods=['GET'])
def list_reports():
    db = get_db()
    rows = db.execute('SELECT report_id, user_id, subject, description FROM bug_reports ORDER BY created_at DESC').fetchall()
    reports = [dict(row) for row in rows]
    return jsonify({'reports': reports})



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
    movie = row_to_dict(row)
    movie = enrich_movie_info(movie)
    return jsonify(movie)

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
    # enrich with synopsis/platforms
    enriched = [enrich_movie_info(dict(m)) for m in movies]
    return jsonify({'director': name_raw, 'count': len(enriched), 'movies': enriched})


# -----------------------
# New APIs for use-case implementation
# -----------------------
def get_user_basic(user_id):
    db = get_db()
    row = db.execute('SELECT * FROM users_basic WHERE user_id = ?', (user_id,)).fetchone()
    if row:
        return dict(row)
    # fallback to in-memory
    return user_profiles.get(user_id)


def get_user_preferences(user_id):
    db = get_db()
    row = db.execute('SELECT preferences_json FROM users_preferences WHERE user_id = ?', (user_id,)).fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except Exception:
            return {}
    # fallback
    u = user_profiles.get(user_id, {})
    return u.get('preferences', {})


def get_user_watchlist_set(user_id):
    db = get_db()
    rows = db.execute('SELECT movie_rowid FROM user_watchlist_map m JOIN users_watchlist w ON m.list_id = w.list_id WHERE w.user_id = ?', (user_id,)).fetchall()
    return set([str(r[0]) for r in rows])


def get_user_seen_set(user_id):
    db = get_db()
    rows = db.execute('SELECT movie_rowid FROM users_feedback WHERE user_id = ? AND rating IS NOT NULL', (user_id,)).fetchall()
    return set([str(r[0]) for r in rows])


def get_user_favorites_set(user_id):
    # favorites were stored in-memory previously; try DB users_preferences -> favorites key
    prefs = get_user_preferences(user_id)
    favs = prefs.get('favorites') if isinstance(prefs, dict) else None
    if favs:
        return set([f.strip().lower() for f in favs if f])
    # fallback: in-memory
    u = user_profiles.get(user_id, {})
    return set([f.strip().lower() for f in (u.get('favorites') or [])])


def compute_recommendations_for_user(user_id, top_n=10):
    db = get_db()
    prefs = get_user_preferences(user_id) or {}
    pref_movies = set([m.lower().strip() for m in (prefs.get('movies') or [])])
    pref_directors = set([d.lower().strip() for d in (prefs.get('directors') or [])])
    pref_actors = set([a.lower().strip() for a in (prefs.get('actors') or [])])
    pref_genres = set([g.lower().strip() for g in (prefs.get('genres') or [])])

    # load all movies
    cur = db.execute(f"SELECT rowid as movie_id, * FROM {MOVIES_TABLE}")
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

    watched = get_user_seen_set(user_id)
    watchlist_ids = get_user_watchlist_set(user_id)

    scored = []
    for m in candidates:
        mid = str(m.get('movie_id'))
        title = (m.get('movie_title') or '').strip().lower()
        if mid in watchlist_ids or mid in watched:
            continue
        sc = score_movie(m)
        if sc > 0:
            scored.append((sc, m))

    scored_sorted = sorted(scored, key=lambda x: (-x[0], x[1].get('movie_title','')))
    top = [item for _, item in scored_sorted[:top_n]]

    # persist recommendation record
    try:
        db.execute('INSERT INTO recommendation_records (user_id, generated_at, recommendations_json) VALUES (?, ?, ?)',
                   (user_id, time.time(), json.dumps([r.get('movie_id') for r in top])))
        db.commit()
    except Exception as e:
        print('Failed to persist recommendation record:', e)

    return top


@app.route('/recommendations/<user_id>', methods=['GET'])
def api_recommendations(user_id):
    # verify user exists
    ub = get_user_basic(user_id)
    if not ub:
        return jsonify({'error': 'User not found'}), 404
    top_n = int(request.args.get('top', 10))
    recs = compute_recommendations_for_user(user_id, top_n=top_n)
    # enrich each movie with synopsis and streaming platforms (best-effort)
    enriched = [enrich_movie_info(dict(r)) for r in recs]
    return jsonify({'user_id': user_id, 'count': len(enriched), 'recommendations': enriched})


@app.route('/movies/<int:movie_id>', methods=['GET'])
def api_movie_by_id(movie_id):
    db = get_db()
    cur = db.execute(f"SELECT rowid as movie_id, * FROM {MOVIES_TABLE} WHERE rowid = ? LIMIT 1", (movie_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'error': 'Movie not found'}), 404
    movie = row_to_dict(row)
    # Enrich with synopsis and platforms
    movie = enrich_movie_info(movie)
    return jsonify(movie)


@app.route('/movies/search', methods=['GET'])
def api_movies_search():
    # params: query, director, mood (tag), exclude_mainstream (bool), user_id (optional)
    query = (request.args.get('query') or '').strip()
    director = (request.args.get('director') or '').strip()
    mood = (request.args.get('mood') or '').strip()
    exclude_mainstream = request.args.get('exclude_mainstream') in ('1','true','True','yes')
    user_id = request.args.get('user_id')

    db = get_db()
    where = []
    params = []
    if query:
        where.append('LOWER(movie_title) LIKE ?')
        params.append(f"%{query.lower()}%")
    if director:
        where.append('LOWER(director_name) LIKE ?')
        params.append(f"%{director.lower()}%")
    if mood:
        where.append('LOWER(tags) LIKE ?')
        params.append(f"%{mood.lower()}%")

    sql = f"SELECT * FROM {MOVIES_TABLE}"
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' LIMIT 200'
    rows = db.execute(sql, params).fetchall()
    results = [row_to_dict(r) for r in rows]
    # apply mainstream exclusion if requested and user provided
    if exclude_mainstream and user_id:
        prefs = get_user_preferences(user_id)
        exclude_list = prefs.get('exclude', []) if isinstance(prefs, dict) else []
        # simple heuristic: remove movies whose title/director in exclude_list
        exset = set([e.strip().lower() for e in exclude_list])
        results = [r for r in results if (r.get('movie_title') or '').strip().lower() not in exset and (r.get('director_name') or '').strip().lower() not in exset]

    # enrich results with synopsis/platforms
    enriched = [enrich_movie_info(dict(r)) for r in results]
    return jsonify({'count': len(enriched), 'results': enriched})


@app.route('/movies/<int:movie_id>/feedback', methods=['POST','PUT'])
def api_movie_feedback(movie_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    rating = data.get('rating')
    text = data.get('text')
    # authenticate: basic check user exists
    if not user_id or not get_user_basic(user_id):
        return jsonify({'error': 'user_id required and must exist'}), 400
    db = get_db()
    cur = db.execute(f"SELECT rowid as movie_id, * FROM {MOVIES_TABLE} WHERE rowid = ? LIMIT 1", (movie_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'error': 'Movie not found'}), 404
    movie = row_to_dict(row)

    now = time.time()
    # check existing feedback by same user and movie
    existing = db.execute('SELECT feedback_id FROM users_feedback WHERE user_id = ? AND movie_rowid = ? LIMIT 1', (user_id, movie_id)).fetchone()
    if existing:
        fid = existing[0]
        db.execute('UPDATE users_feedback SET rating = ?, text = ?, created_at = ? WHERE feedback_id = ?', (rating, text, now, fid))
    else:
        db.execute('INSERT INTO users_feedback (user_id, movie_rowid, movie_title, rating, text, created_at) VALUES (?, ?, ?, ?, ?, ?)', (user_id, movie_id, movie.get('movie_title'), rating, text, now))
    db.commit()

    # publish event
    publish_event('feedback_created', {'user_id': user_id, 'movie_id': movie_id, 'rating': rating})

    return jsonify({'status': 'ok'})


@app.route('/users/<user_id>/watchlists', methods=['POST'])
def api_create_watchlist(user_id):
    data = request.get_json() or {}
    name = data.get('name') or 'My Watchlist'
    # verify user exists
    if not get_user_basic(user_id):
        return jsonify({'error': 'User not found'}), 404
    db = get_db()
    cur = db.execute('INSERT INTO users_watchlist (user_id, name, created_at) VALUES (?, ?, ?)', (user_id, name, time.time()))
    db.commit()
    list_id = cur.lastrowid
    publish_event('watchlist_created', {'user_id': user_id, 'list_id': list_id})
    return jsonify({'status': 'ok', 'list_id': list_id})


@app.route('/watchlists/<int:list_id>/movies', methods=['POST'])
def api_add_movie_to_watchlist(list_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    movie_id = data.get('movie_id')
    if not user_id or not movie_id:
        return jsonify({'error': 'user_id and movie_id required'}), 400
    db = get_db()
    # verify list ownership
    lst = db.execute('SELECT user_id FROM users_watchlist WHERE list_id = ? LIMIT 1', (list_id,)).fetchone()
    if not lst:
        return jsonify({'error': 'watchlist not found'}), 404
    if lst[0] != user_id:
        return jsonify({'error': 'user not owner of this watchlist'}), 403
    # verify movie exists
    m = db.execute(f"SELECT rowid FROM {MOVIES_TABLE} WHERE rowid = ? LIMIT 1", (movie_id,)).fetchone()
    if not m:
        return jsonify({'error': 'movie not found'}), 404
    db.execute('INSERT INTO user_watchlist_map (list_id, movie_rowid, added_at) VALUES (?, ?, ?)', (list_id, movie_id, time.time()))
    db.commit()
    publish_event('watchlist_movie_added', {'user_id': user_id, 'list_id': list_id, 'movie_id': movie_id})
    return jsonify({'status': 'ok'})


@app.route('/users/<user_id>/settings', methods=['PUT'])
def api_update_user_settings(user_id):
    data = request.get_json() or {}
    if not get_user_basic(user_id):
        return jsonify({'error': 'User not found'}), 404
    prefs_json = json.dumps(data)
    db = get_db()
    db.execute('INSERT INTO users_preferences (user_id, preferences_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET preferences_json=excluded.preferences_json, updated_at=excluded.updated_at', (user_id, prefs_json, time.time()))
    db.commit()
    publish_event('settings_updated', {'user_id': user_id})
    return jsonify({'status': 'ok'})


if __name__ == "__main__":
    app.run(debug=True)

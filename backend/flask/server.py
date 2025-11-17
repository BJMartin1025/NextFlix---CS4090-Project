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

if __name__ == "__main__":
    app.run(debug=True)

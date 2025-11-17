from flask import Flask, request, jsonify
from flask_cors import CORS
import pickle
import pandas as pd
import numpy as np

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

# Load the movie dataset
final_data = pd.read_csv('movie_dataset.csv')
# Normalize the movie titles once
final_data['movie_title'] = final_data['movie_title'].str.strip().str.lower()

# Load the CountVectorizer and Similarity Matrix
with open('similarity.pkl', 'rb') as file:
    similarity = pickle.load(file)

# In-memory store for user profiles (preferences). Replace with DB later.
user_profiles = {}
# In-memory store for bug/issue reports. Persist to DB later.
bug_reports = []

@app.route("/")
def home():
    return {"message": "Hello from the recommendation backend"}

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
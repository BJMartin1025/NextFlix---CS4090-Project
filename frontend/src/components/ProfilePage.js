import React, { useEffect, useState } from 'react';
import API_BASE from '../api';
import '../styles/UserPreferenceInputForm.css';

function ProfilePage({ onBack }) {
  const [userId, setUserId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState({
    movies: [],
    genres: [],
    directors: [],
    actors: []
  });
  const [options, setOptions] = useState({ movies: [], directors: [], actors: [], genres: [] });
  const [movieInput, setMovieInput] = useState('');
  const [directorInput, setDirectorInput] = useState('');
  const [actorInput, setActorInput] = useState('');
  const [feedback, setFeedback] = useState([]);

  useEffect(() => {
    const id = localStorage.getItem('nextflix_user_id');
    if (!id) {
      setLoading(false);
      setUserId(null);
      return;
    }
    setUserId(id);
    fetchProfile(id);
    // fetch catalog options for constrained inputs
    const fetchOptions = async () => {
      try {
        const res = await fetch(`${API_BASE}/catalog/options`);
        if (!res.ok) return;
        const data = await res.json();
        setOptions(data);
      } catch (err) {
        console.error('Failed to load catalog options', err);
      }
    };
    fetchOptions();
  }, []);

  const fetchProfile = async (id) => {
    setLoading(true);
    try {
      const [prefRes, fbRes] = await Promise.all([
        fetch(`${API_BASE}/user/preferences/${id}`),
        fetch(`${API_BASE}/user/feedback/${id}`),
      ]);

      if (prefRes.ok) {
        const prefData = await prefRes.json();
        const prefs = prefData.preferences || {};
        setPreferences({
          movies: prefs.movies || [],
          genres: prefs.genres || [],
          directors: prefs.directors || [],
          actors: prefs.actors || [],
        });
      } else {
        setPreferences({ movies: [], genres: [], directors: [], actors: [] });
      }

      if (fbRes.ok) {
        const fbData = await fbRes.json();
        setFeedback(fbData.feedback || []);
      } else {
        setFeedback([]);
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value, multiple, options } = e.target;
    if (multiple) {
      const values = Array.from(options).filter(o => o.selected).map(o => o.value);
      setPreferences(prev => ({ ...prev, [name]: values }));
    } else {
      setPreferences(prev => ({ ...prev, [name]: value }));
    }
  };

  const parseCsvToArray = (s) => {
    if (!s) return [];
    return s.split(',').map(x => x.trim()).filter(Boolean);
  };

  const addUnique = (arr, value) => {
    if (!value) return arr;
    const trimmed = value.trim();
    if (!trimmed) return arr;
    if (arr.find(a => a.toLowerCase() === trimmed.toLowerCase())) return arr;
    return [...arr, trimmed];
  };

  const removeAt = (arr, idx) => arr.filter((_, i) => i !== idx);

  const addMovie = () => {
    if (!movieInput) return;
    const match = options.movies.find(m => m.toLowerCase() === movieInput.trim().toLowerCase());
    if (!match) {
      alert('Please select a movie from the suggestions.');
      return;
    }
    setPreferences(prev => ({ ...prev, movies: addUnique(prev.movies, match) }));
    setMovieInput('');
  };

  const addDirector = () => {
    if (!directorInput) return;
    const match = options.directors.find(d => d.toLowerCase() === directorInput.trim().toLowerCase());
    if (!match) {
      alert('Please select a director from the suggestions.');
      return;
    }
    setPreferences(prev => ({ ...prev, directors: addUnique(prev.directors, match) }));
    setDirectorInput('');
  };

  const addActor = () => {
    if (!actorInput) return;
    const match = options.actors.find(a => a.toLowerCase() === actorInput.trim().toLowerCase());
    if (!match) {
      alert('Please select an actor from the suggestions.');
      return;
    }
    setPreferences(prev => ({ ...prev, actors: addUnique(prev.actors, match) }));
    setActorInput('');
  };

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    if (!userId) {
      alert('No user profile found in this browser. Preferences cannot be saved.');
      return;
    }

    const payload = {
      user_id: userId,
      preferences: {
        movies: preferences.movies,
        genres: preferences.genres,
        directors: preferences.directors,
        actors: preferences.actors,
      }
    };

    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/user/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error('Save failed', data);
        alert('Failed to save preferences.');
      } else {
        alert('Preferences saved.');
        fetchProfile(userId);
      }
    } catch (err) {
      console.error(err);
      alert('Error saving preferences. See console.');
    } finally {
      setSaving(false);
    }
  };

  // Allow adding new feedback entries from profile page
  const [newFeedback, setNewFeedback] = useState({ movie: '', rating: 0, text: '' });

  const handleNewFeedbackChange = (e) => {
    const { name, value } = e.target;
    setNewFeedback(prev => ({ ...prev, [name]: value }));
  };

  const submitNewFeedback = async (e) => {
    e.preventDefault();
    if (!userId) {
      alert('No user profile available.');
      return;
    }
    if (!newFeedback.movie) {
      alert('Please specify a movie title.');
      return;
    }

    const payload = {
      user_id: userId,
      movie: newFeedback.movie,
      rating: Number(newFeedback.rating) || 0,
      text: newFeedback.text || ''
    };

    try {
      const res = await fetch(`${API_BASE}/user/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error('Feedback save failed', data);
        alert('Failed to save feedback.');
      } else {
        alert('Feedback added.');
        setNewFeedback({ movie: '', rating: 0, text: '' });
        fetchProfile(userId);
      }
    } catch (err) {
      console.error(err);
      alert('Error adding feedback.');
    }
  };

  if (loading) return <div>Loading profile...</div>;
  if (!userId) return (
    <div className="input-form-container">
      <h2>No Profile Found</h2>
      <p>We couldn't find a user profile in this browser. To create one, submit your preferences from the preferences form first.</p>
      <button onClick={onBack} className="back-button">← Back</button>
    </div>
  );

  return (
    <div className="input-form-container">
      <h2>Your Profile</h2>
      <p><strong>User ID:</strong> {userId}</p>

      <form onSubmit={handleSavePreferences}>
        <div className="input-group">
          <label htmlFor="movieInput">Favorite Movies:</label>
          <div className="inline-add">
            <input
              id="movieInput"
              list="movies-datalist"
              placeholder="Start typing and select a movie"
              value={movieInput}
              onChange={(e) => setMovieInput(e.target.value)}
            />
            <datalist id="movies-datalist">
              {options.movies && options.movies.map((m, i) => (
                <option key={i} value={m} />
              ))}
            </datalist>
            <button type="button" onClick={addMovie} className="add-button">Add</button>
          </div>

          <div className="chips">
            {preferences.movies.map((m, i) => (
              <span key={i} className="chip">
                {m}
                <button type="button" className="chip-remove" onClick={() => setPreferences(prev => ({ ...prev, movies: removeAt(prev.movies, i) }))}>×</button>
              </span>
            ))}
          </div>
        </div>

        <div className="custom-select-container">
          <label htmlFor="genres">Preferred Genres:</label>
          <select id="genres" name="genres" multiple value={preferences.genres} onChange={handleChange} className="h-48">
            {options.genres && options.genres.map((g, idx) => (
              <option key={idx} value={g}>{g}</option>
            ))}
          </select>
        </div>

        <div className="input-group">
          <label htmlFor="directorInput">Favorite Directors:</label>
          <div className="inline-add">
            <input
              id="directorInput"
              list="directors-datalist"
              placeholder="Type and select a director"
              value={directorInput}
              onChange={(e) => setDirectorInput(e.target.value)}
            />
            <datalist id="directors-datalist">
              {options.directors && options.directors.map((d, i) => (
                <option key={i} value={d} />
              ))}
            </datalist>
            <button type="button" onClick={addDirector} className="add-button">Add</button>
          </div>

          <div className="chips">
            {preferences.directors.map((d, i) => (
              <span key={i} className="chip">
                {d}
                <button type="button" className="chip-remove" onClick={() => setPreferences(prev => ({ ...prev, directors: removeAt(prev.directors, i) }))}>×</button>
              </span>
            ))}
          </div>
        </div>

        <div className="input-group">
          <label htmlFor="actorInput">Favorite Actors/Actresses:</label>
          <div className="inline-add">
            <input
              id="actorInput"
              list="actors-datalist"
              placeholder="Type and select an actor"
              value={actorInput}
              onChange={(e) => setActorInput(e.target.value)}
            />
            <datalist id="actors-datalist">
              {options.actors && options.actors.map((a, i) => (
                <option key={i} value={a} />
              ))}
            </datalist>
            <button type="button" onClick={addActor} className="add-button">Add</button>
          </div>

          <div className="chips">
            {preferences.actors.map((a, i) => (
              <span key={i} className="chip">
                {a}
                <button type="button" className="chip-remove" onClick={() => setPreferences(prev => ({ ...prev, actors: removeAt(prev.actors, i) }))}>×</button>
              </span>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="submit" className="submit-button" disabled={saving}>{saving ? 'Saving...' : 'Save Preferences'}</button>
          <button type="button" className="back-button" onClick={onBack}>← Back</button>
        </div>
      </form>

      <hr />

      <section>
        <h3>Your Feedback</h3>
        {feedback.length === 0 && <p>No feedback saved yet.</p>}
        <ul>
          {feedback.map((f, i) => (
            <li key={i} style={{ marginBottom: '8px' }}>
              <strong>{f.movie}</strong> — Rating: {f.rating}
              {f.text ? <div style={{ marginTop: '4px' }}>{f.text}</div> : null}
            </li>
          ))}
        </ul>

        <h4>Add New Feedback</h4>
        <form onSubmit={submitNewFeedback}>
          <div className="input-group">
            <label htmlFor="nf_movie">Movie Title:</label>
            <input id="nf_movie" name="movie" value={newFeedback.movie} onChange={handleNewFeedbackChange} />
          </div>
          <div className="input-group">
            <label htmlFor="nf_rating">Rating (1-5):</label>
            <input id="nf_rating" name="rating" type="number" min="0" max="5" value={newFeedback.rating} onChange={handleNewFeedbackChange} />
          </div>
          <div className="input-group">
            <label htmlFor="nf_text">Text (optional):</label>
            <textarea id="nf_text" name="text" value={newFeedback.text} onChange={handleNewFeedbackChange} rows="2" />
          </div>
          <button type="submit" className="submit-button">Add Feedback</button>
        </form>
      </section>
    </div>
  );
}

export default ProfilePage;

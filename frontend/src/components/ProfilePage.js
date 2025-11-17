import React, { useEffect, useState } from 'react';
import '../styles/UserPreferenceInputForm.css';

function ProfilePage({ onBack }) {
  const [userId, setUserId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState({
    movies: '',
    genres: [],
    directors: '',
    actors: ''
  });
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
  }, []);

  const fetchProfile = async (id) => {
    setLoading(true);
    try {
      const [prefRes, fbRes] = await Promise.all([
        fetch(`http://localhost:5000/user/preferences/${id}`),
        fetch(`http://localhost:5000/user/feedback/${id}`),
      ]);

      if (prefRes.ok) {
        const prefData = await prefRes.json();
        const prefs = prefData.preferences || {};
        setPreferences({
          movies: (prefs.movies || []).join(', '),
          genres: prefs.genres || [],
          directors: (prefs.directors || []).join(', '),
          actors: (prefs.actors || []).join(', '),
        });
      } else {
        setPreferences({ movies: '', genres: [], directors: '', actors: '' });
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

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    if (!userId) {
      alert('No user profile found in this browser. Preferences cannot be saved.');
      return;
    }

    const payload = {
      user_id: userId,
      preferences: {
        movies: parseCsvToArray(preferences.movies),
        genres: preferences.genres,
        directors: parseCsvToArray(preferences.directors),
        actors: parseCsvToArray(preferences.actors),
      }
    };

    setSaving(true);
    try {
      const res = await fetch('http://localhost:5000/user/preferences', {
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
      const res = await fetch('http://localhost:5000/user/feedback', {
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
          <label htmlFor="movies">Favorite Movies:</label>
          <textarea id="movies" name="movies" value={preferences.movies} onChange={handleChange} rows="3" />
        </div>

        <div className="custom-select-container">
          <label htmlFor="genres">Preferred Genres:</label>
          <select id="genres" name="genres" multiple value={preferences.genres} onChange={handleChange} className="h-48">
            <option value="Action">Action</option>
            <option value="Adventure">Adventure</option>
            <option value="Animation">Animation</option>
            <option value="Comedy">Comedy</option>
            <option value="Crime">Crime</option>
            <option value="Documentary">Documentary</option>
            <option value="Drama">Drama</option>
            <option value="Fantasy">Fantasy</option>
            <option value="Horror">Horror</option>
            <option value="Musical">Musical</option>
            <option value="Mystery">Mystery</option>
            <option value="Romance">Romance</option>
            <option value="Sci-Fi">Sci-Fi</option>
            <option value="Thriller">Thriller</option>
          </select>
        </div>

        <div className="input-group">
          <label htmlFor="directors">Favorite Directors:</label>
          <input id="directors" name="directors" type="text" value={preferences.directors} onChange={handleChange} />
        </div>

        <div className="input-group">
          <label htmlFor="actors">Favorite Actors/Actresses:</label>
          <input id="actors" name="actors" type="text" value={preferences.actors} onChange={handleChange} />
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

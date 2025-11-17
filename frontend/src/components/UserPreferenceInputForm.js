import React, { useState, useEffect } from 'react';
// CORRECT PATH: Go up one level (to src), then into the styles folder
import '../styles/UserPreferenceInputForm.css';

/**
 * A form for users to input their movie preferences, including
 * favorite movies, genres, directors, and actors.
 * @param {object} props - Component props
 * @param {function} props.onBackClick - Function to handle navigation back (e.g., hiding the form).
 */
function UserPreferenceInputForm({ onBackClick }) {
  const [preferences, setPreferences] = useState({
    movies: [],
    genres: [],
    directors: [],
    actors: [],
  });
  const [options, setOptions] = useState({ movies: [], directors: [], actors: [], genres: [] });

  // temporary inputs for adding single items
  const [movieInput, setMovieInput] = useState('');
  const [directorInput, setDirectorInput] = useState('');
  const [actorInput, setActorInput] = useState('');
  const [userId, setUserId] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // Ensure a persistent user id exists for tying preferences to a profile
    let id = localStorage.getItem('nextflix_user_id');
    if (!id) {
      id = 'user_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
      localStorage.setItem('nextflix_user_id', id);
    }
    setUserId(id);
  }, []);

  useEffect(() => {
    // fetch available options (movies, directors, actors, genres) from backend CSV
    const fetchOptions = async () => {
      try {
        const res = await fetch('http://localhost:5000/catalog/options');
        if (!res.ok) return;
        const data = await res.json();
        setOptions(data);
      } catch (err) {
        console.error('Failed to load catalog options', err);
      }
    };
    fetchOptions();
  }, []);

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
    // only allow if the input matches an available movie (exact match ignoring case)
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

  const handleSubmit = async (e) => {
    e.preventDefault();

    const payload = {
      user_id: userId,
      preferences: {
        movies: preferences.movies,
        genres: preferences.genres,
        directors: preferences.directors,
        actors: preferences.actors
      }
    };

    console.log('Submitting Preferences:', payload);
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
        alert('Failed to save preferences: ' + (data.error || res.statusText));
      } else {
        console.log('Preferences saved', data);
        alert('Preferences saved to your profile.');
      }
    } catch (err) {
      console.error('Error saving preferences', err);
      alert('Error saving preferences. See console for details.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="input-form-container">
      <h2>Tell Us Your Taste</h2>
      <p>Enter your preferences, separated by commas (e.g., *The Matrix, Inception*).</p>
      
      <form onSubmit={handleSubmit}>
        
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
          <label htmlFor="genres" className="block text-sm font-medium text-gray-700 mb-2">Preferred Genres (Select all that apply):</label>
          <select
            id="genres"
            name="genres"
            multiple
            value={preferences.genres}
            onChange={handleChange}
            className="w-full px-4 px-3 rounded-lg bg-white border border-gray-300 text-gray-900 focus:border-red-500 focus:ring-red-200 transition duration-150 ease-in-out shadow-inner h-48"
          >
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
        
        <button type="submit" className="submit-button" disabled={saving}>
          {saving ? 'Saving...' : 'Save Preferences'}
        </button>

        {/* New Back Button */}
        {onBackClick && (
          <button 
            type="button" 
            onClick={onBackClick} 
            className="back-button"
          >
            ← Back to Home
          </button>
        )}
      </form>
    </div>
  );
}

export default UserPreferenceInputForm;
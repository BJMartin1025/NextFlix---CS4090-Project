import React, { useState } from 'react';
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
    movies: '',
    genres: '',
    directors: '',
    actors: '',
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setPreferences(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log('Submitted Preferences:', preferences);
    // TODO: In a later stage, this data will be sent to the backend
    // for processing by the movie recommendation engine.
    // NOTE: alert() is used here but generally discouraged in modern React apps.
    alert('Preferences submitted! Check the console for data.'); 
  };

  return (
    <div className="input-form-container">
      <h2>Tell Us Your Taste</h2>
      <p>Enter your preferences, separated by commas (e.g., *The Matrix, Inception*).</p>
      
      <form onSubmit={handleSubmit}>
        
        <div className="input-group">
          <label htmlFor="movies">Favorite Movies:</label>
          <textarea
            id="movies"
            name="movies"
            value={preferences.movies}
            onChange={handleChange}
            placeholder="e.g., Pulp Fiction, Parasite, Alien"
            rows="3"
            required
          />
        </div>

        <div class="custom-select-container">
          <label for="genres" class="block text-sm font-medium test-gray-700 mb-2">Preferred Genres (Select all that apply:):</label>
          <select
            id="genres"
            name="genres"
            multiple
            class="w-full px-4 px-3 rounded-lg bg-white border border-gray-300 text-gray-900 focus:border-red-500 focus:ring-red-200 transition duration-150 ease-in-out shadow-inner h-48"
            required
          >
            <option value="" disabled>-- Hold Ctrl/Cmd to select multiple --</option>
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
          <input
            id="directors"
            name="directors"
            type="text"
            value={preferences.directors}
            onChange={handleChange}
            placeholder="e.g., Christopher Nolan, Greta Gerwig, Bong Joon-ho"
          />
        </div>

        <div className="input-group">
          <label htmlFor="actors">Favorite Actors/Actresses:</label>
          <input
            id="actors"
            name="actors"
            type="text"
            value={preferences.actors}
            onChange={handleChange}
            placeholder="e.g., Tom Hanks, Emma Stone, Denzel Washington"
          />
        </div>
        
        <button type="submit" className="submit-button">
          Get Recommendations
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
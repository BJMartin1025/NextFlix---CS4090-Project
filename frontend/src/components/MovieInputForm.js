// src/components/MovieInputForm.js
import React, { useState } from 'react';
import './MovieInputForm.css'; // For styling

function MovieInputForm({ onSubmit, loading }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !loading) {
      onSubmit(input);
    }
  };

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <label htmlFor="movie-name">Enter a movie you like:</label>
      <input
        id="movie-name"
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="e.g., The Dark Knight"
        disabled={loading}
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Loading...' : 'Get Recommendations'}
      </button>
    </form>
  );
}

export default MovieInputForm;
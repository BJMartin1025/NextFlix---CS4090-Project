// src/components/MovieInputForm.js
import React, { useState } from 'react';
import '../styles/MovieInputForm.css';

function MovieInputForm({ onSubmit, loading }) {
  const [input, setInput] = useState('');
  const [searchType, setSearchType] = useState('title'); // NEW

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !loading) {
      onSubmit(input, searchType); // pass both values
    }
  };

  return (
    <form className="input-form" onSubmit={handleSubmit}>
      <label htmlFor="movie-name">Find recommendations by:</label>

      <div className="search-row">
        {/* NEW DROPDOWN */}
        <select
          value={searchType}
          onChange={(e) => setSearchType(e.target.value)}
          disabled={loading}
          className="search-type-select"
        >
          <option value="title">Title</option>
          <option value="director">Director</option>
          <option value="actor">Actor</option>
          <option value="genre">Genre</option>
        </select>

        {/* SEARCH BOX */}
        <input
          id="movie-name"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter your search..."
          disabled={loading}
        />
      </div>

      <button type="submit" disabled={loading}>
        {loading ? 'Loading...' : 'Get Recommendations'}
      </button>
    </form>
  );
}

export default MovieInputForm;

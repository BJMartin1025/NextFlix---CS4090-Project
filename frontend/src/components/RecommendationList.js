// src/components/RecommendationList.js
import React, { useState } from 'react';
import StarRating from './StarRating';
import '../styles/RecommendationList.css'; // For styling

function RecommendationList({ movieName, recommendations, onFeedbackSubmit }) {
  // Track which movie is selected to view details
  const [selectedMovie, setSelectedMovie] = useState(null);
  const [movieDetails, setMovieDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  // Local feedback state for currently viewed movie
  const [localFeedback, setLocalFeedback] = useState({ rating: 0, text: '' });

  const openMovie = async (movie) => {
    setSelectedMovie(movie);
    setMovieDetails(null);
    setLocalFeedback({ rating: 0, text: '' });
    setLoadingDetails(true);
    try {
      const res = await fetch('http://localhost:5000/movie?title=' + encodeURIComponent(movie));
      if (!res.ok) {
        setMovieDetails({ error: 'Details not found' });
      } else {
        const data = await res.json();
        setMovieDetails(data.details || null);
      }
    } catch (err) {
      console.error('Error fetching movie details', err);
      setMovieDetails({ error: 'Error fetching details' });
    } finally {
      setLoadingDetails(false);
    }
  };

  const closeDetails = () => {
    setSelectedMovie(null);
    setMovieDetails(null);
    setLocalFeedback({ rating: 0, text: '' });
  };

  const handleRate = (rating) => {
    setLocalFeedback(prev => ({ ...prev, rating }));
  };

  const handleFeedbackChange = (text) => {
    setLocalFeedback(prev => ({ ...prev, text }));
  };

  const submitFeedback = () => {
    if (!selectedMovie) return;
    const { rating = 0, text = '' } = localFeedback;
    onFeedbackSubmit(selectedMovie, rating, text);
    alert(`Thank you for your feedback on "${selectedMovie}"!`);
    // leave the details open; reset local feedback
    setLocalFeedback({ rating: 0, text: '' });
  };

  return (
    <div className="recommendation-list">
      <h2>Top Recommendations for: {movieName}</h2>
      <ul className="movie-list">
        {recommendations.map((movie, index) => (
          <li key={movie} className="movie-list-item">
            <button className="movie-link" onClick={() => openMovie(movie)}>{index + 1}. {movie}</button>
          </li>
        ))}
      </ul>

      {selectedMovie && (
        <div className="movie-detail-panel">
          <div className="panel-header">
            <h3>{selectedMovie}</h3>
            <button className="back-button" onClick={closeDetails}>Close</button>
          </div>

          {loadingDetails && <p>Loading details...</p>}

          {movieDetails && movieDetails.error && <p>{movieDetails.error}</p>}

          {movieDetails && !movieDetails.error && (
            <div className="movie-info">
              <p><strong>Director:</strong> {movieDetails.director_name || 'N/A'}</p>
              <p><strong>Actors:</strong> {[
                movieDetails.actor_1_name,
                movieDetails.actor_2_name,
                movieDetails.actor_3_name
              ].filter(Boolean).join(', ') || 'N/A'}</p>
              <p><strong>Genres:</strong> {movieDetails.genres || 'N/A'}</p>
              {movieDetails.tags && <p><strong>Tags:</strong> {movieDetails.tags}</p>}
            </div>
          )}

          <div className="feedback-section">
            <h4>Your Rating & Feedback</h4>
            <StarRating onRate={handleRate} />
            <textarea
              placeholder="Tell us what you thought..."
              rows="3"
              value={localFeedback.text}
              onChange={(e) => handleFeedbackChange(e.target.value)}
            />
            <button onClick={submitFeedback} className="feedback-button">Submit Feedback</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RecommendationList;
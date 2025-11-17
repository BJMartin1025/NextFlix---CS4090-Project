// src/components/RecommendationList.js
import React, { useState } from 'react';
import StarRating from './StarRating';
import '../styles/RecommendationList.css';

function RecommendationList({ movieName, recommendations, onFeedbackSubmit }) {
  const [feedback, setFeedback] = useState({});

  const handleRate = (movieTitle, rating) => {
    setFeedback(prev => ({
      ...prev,
      [movieTitle]: { ...prev[movieTitle], rating: rating },
    }));
  };

  const handleFeedbackChange = (movieTitle, text) => {
    setFeedback(prev => ({
      ...prev,
      [movieTitle]: { ...prev[movieTitle], text: text },
    }));
  };

  const submitFeedback = (movieTitle) => {
    const { rating = 0, text = '' } = feedback[movieTitle] || {};
    onFeedbackSubmit(movieTitle, rating, text);
    alert(`Thank you for your feedback on "${movieTitle}"!`);
  };

  return (
    <div className="recommendation-list">
      <h2>Top Recommendations for: {movieName}</h2>
      <ul>
        {recommendations.map((movieObj, index) => (
          <li key={index} className="movie-card">
            <div className="movie-details">
              <p className="movie-title-rec">
                {index + 1}. {movieObj.movie_title} 
                {movieObj.score !== undefined && ` (Score: ${movieObj.score})`}
              </p>
              <p className="movie-director">Director: {movieObj.director_name}</p>
              <p className="movie-genres">Genres: {movieObj.genres}</p>
            </div>

            <div className="feedback-section">
              <StarRating onRate={(rating) => handleRate(movieObj.movie_title, rating)} />
              <textarea
                placeholder="Optional: Tell us what you thought..."
                rows="2"
                value={feedback[movieObj.movie_title]?.text || ''}
                onChange={(e) => handleFeedbackChange(movieObj.movie_title, e.target.value)}
              />
              <button 
                onClick={() => submitFeedback(movieObj.movie_title)}
                className="feedback-button"
              >
                Submit Feedback
              </button>
            </div>
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

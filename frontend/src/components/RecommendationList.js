// src/components/RecommendationList.js
import React, { useState } from 'react';
import StarRating from './StarRating';
import '../styles/RecommendationList.css';

function RecommendationList({ movieName, recommendations, onFeedbackSubmit, watchlist = [], onToggleWatchlist, onAddToFavorites, onMarkSeen }) {
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
    if (onFeedbackSubmit) {
      onFeedbackSubmit(movieTitle, rating, text);
    } else {
      console.warn('No onFeedbackSubmit handler provided');
    }
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

              <div className="api-ratings-container">
                  <span className="rating-badge imdb">IMDb: 
                      <strong>{movieObj.imdb_score || 'N/A'}</strong>
                  </span>
                  <span className="rating-badge rt">Rotten Tomatoes: 
                      <strong>{movieObj.rotten_tomatoes_score || 'N/A'}</strong>
                  </span>
                  <span className="rating-badge mc">Metacritic: 
                      <strong>{movieObj.metacritic_score || 'N/A'}</strong>
                  </span>
              </div>
              
              <p className="movie-director">Director: {movieObj.director_name}</p>
              <p className="movie-actors">Actors: {[
                movieObj.actor_1_name,
                movieObj.actor_2_name,
                movieObj.actor_3_name
              ].filter(Boolean).join(', ')}</p>
              <p className="movie-genres">Genres: {movieObj.genres}</p>
              <p className="movie-synopsis">{movieObj.synopsis && movieObj.synopsis.trim() ? movieObj.synopsis : 'Synopsis: Not available'}</p>
              <p className="movie-platforms">Platforms: {movieObj.platforms && movieObj.platforms.length ? movieObj.platforms.join(', ') : 'Not available'}</p>
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
              <div className="movie-actions">
                {onToggleWatchlist && (
                  <button
                    className={`action-button ${watchlist.map(w=>w.toLowerCase()).includes((movieObj.movie_title||'').toLowerCase()) ? 'in-watchlist' : ''}`}
                    onClick={() => onToggleWatchlist(movieObj.movie_title)}
                  >
                    {watchlist.map(w=>w.toLowerCase()).includes((movieObj.movie_title||'').toLowerCase()) ? '✔ In Watchlist' : '+ To Watchlist'}
                  </button>
                )}
                <button className="action-button" onClick={() => onAddToFavorites && onAddToFavorites(movieObj.movie_title)}>★ Favorite</button>
                <button className="action-button" onClick={() => onMarkSeen && onMarkSeen(movieObj.movie_title)}>✓ Mark Seen</button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default RecommendationList;
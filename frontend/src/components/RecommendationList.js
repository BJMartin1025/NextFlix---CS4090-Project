// src/components/RecommendationList.js
import React, { useState } from 'react';
import StarRating from './StarRating';
import './RecommendationList.css'; // For styling

function RecommendationList({ movieName, recommendations, onFeedbackSubmit }) {
  
  // State to manage feedback for each recommended movie (optional but helpful)
  const [feedback, setFeedback] = useState({});

  const handleRate = (movie, rating) => {
    setFeedback(prev => ({
      ...prev,
      [movie]: { ...prev[movie], rating: rating },
    }));
  };

  const handleFeedbackChange = (movie, text) => {
    setFeedback(prev => ({
      ...prev,
      [movie]: { ...prev[movie], text: text },
    }));
  };
  
  const submitFeedback = (movie) => {
      const { rating = 0, text = '' } = feedback[movie] || {};
      onFeedbackSubmit(movie, rating, text);
      alert(`Thank you for your feedback on "${movie}"!`);
      // Optionally clear feedback for this movie:
      // setFeedback(prev => { delete prev[movie]; return { ...prev }; }); 
  };

  return (
    <div className="recommendation-list">
      <h2>Top Recommendations for: **{movieName}**</h2>
      <ul>
        {recommendations.map((movie, index) => (
          <li key={index} className="movie-card">
            <div className="movie-details">
                <p className="movie-title-rec">{index + 1}. {movie}</p>
            </div>
            
            <div className="feedback-section">
                <StarRating onRate={(rating) => handleRate(movie, rating)} />
                <textarea
                    placeholder="Optional: Tell us what you thought..."
                    rows="2"
                    value={feedback[movie]?.text || ''}
                    onChange={(e) => handleFeedbackChange(movie, e.target.value)}
                />
                <button 
                    onClick={() => submitFeedback(movie)}
                    className="feedback-button"
                >
                    Submit Feedback
                </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default RecommendationList;
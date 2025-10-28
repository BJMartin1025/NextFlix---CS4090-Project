import React, { useState } from 'react';
import MovieInputForm from './components/MovieInputForm';
import RecommendationList from './components/RecommendationList';
import './App.css'; // For basic styling

const FLASK_API_URL = 'http://localhost:3000/recommend'; // Adjust port if needed

function App() {
  const [movieName, setMovieName] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleRecommend = async (inputMovieName) => {
    setLoading(true);
    setError(null);
    setRecommendations([]); // Clear previous recommendations
    
    try {
      const response = await fetch(FLASK_API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ movie_name: inputMovieName }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setRecommendations(data.recommendations);
      setMovieName(inputMovieName); // Store the movie that generated the list

    } catch (e) {
      setError(e.message);
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  // Function to handle user rating/feedback (placeholder for future implementation)
  const handleFeedback = (recommendedMovie, rating, feedbackText) => {
    console.log(`Feedback for ${recommendedMovie}: Rating ${rating}, Text: ${feedbackText}`);
    // In a real application, you would send this to a separate Flask endpoint (e.g., /feedback)
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Movie Recommender 🎬</h1>
      </header>
      
      <MovieInputForm onSubmit={handleRecommend} loading={loading} />

      {loading && <p>Generating recommendations...</p>}
      {error && <p className="error-message">Error: {error}</p>}
      
      {recommendations.length > 0 && (
        <RecommendationList 
          movieName={movieName}
          recommendations={recommendations} 
          onFeedbackSubmit={handleFeedback}
        />
      )}
    </div>
  );
}

export default App;
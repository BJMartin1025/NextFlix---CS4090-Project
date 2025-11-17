import React, { useState } from 'react';
import MovieInputForm from './components/MovieInputForm';
import RecommendationList from './components/RecommendationList';
import './styles/App.css'; // For styling

function App() {
  const [movieName, setMovieName] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Updated handleRecommend for /similar backend (returns objects)
  const handleRecommend = async (inputMovieName) => {
    setLoading(true);
    setError(null);
    setRecommendations([]);

    try {
      const params = new URLSearchParams({ title: inputMovieName, top: 5 });
      const response = await fetch(`http://localhost:5000/similar?${params.toString()}`, {
        method: 'GET',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      // Store full objects, not just titles
      setRecommendations(data.recommendations);
      setMovieName(inputMovieName);

    } catch (e) {
      setError(e.message);
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  // Feedback handler (works with RecommendationList)
  const handleFeedback = (recommendedMovie, rating, feedbackText) => {
    console.log(`Feedback for ${recommendedMovie}: Rating ${rating}, Text: ${feedbackText}`);
    // Future: send to a Flask endpoint (e.g., /feedback)
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

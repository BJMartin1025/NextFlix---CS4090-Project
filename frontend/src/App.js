import React, { useState } from 'react';
import MovieInputForm from './components/MovieInputForm';
import RecommendationList from './components/RecommendationList';
import UserPreferenceInputForm from './components/UserPreferenceInputForm';
import './styles/App.css'; // For basic styling

const FLASK_API_URL = 'http://localhost:5000/recommend'; // Adjust port if needed

function App() {
  const [movieName, setMovieName] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [view, setView] = useState('search');

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
  };

  // Function to handle user preference submission (placeholder)
  const handlePreferenceSubmit = (preferences) => {
    // For now, just log and switch back to the search view
    console.log('User Preferences Submitted:', preferences);
    alert("Preferences received! Engine tuning implementation pending.");
    setView('search'); 
  };

  // Function to render the correct content based on the 'view' state
  const renderContent = () => {
    if (view === 'preferences') {
      // Show the detailed form
      return (
        <UserPreferenceInputForm 
          onSubmit={handlePreferenceSubmit} 
          // FUNCTION FOR THE BACK BUTTON
          onBackClick={() => setView('search')} 
        />
      );
    }

  return (
      <div className="search-view-container">
        {/* Existing MovieInputForm is rendered here */}
        <MovieInputForm onSubmit={handleRecommend} loading={loading} />

        <div className="preference-switch-area">
          <p>— OR —</p>
          {/* BUTTON TO CHANGE VIEW STATE */}
          <button 
            className="switch-to-pref-button" 
            onClick={() => setView('preferences')}
            disabled={loading}
          >
            Enter Detailed Preferences
          </button>
        </div>

        {/* Loading, Error, and Recommendation List remain below the input area */}
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
  };

  return (
    <div className="app-container min-h-screen w-full">
      <header className="app-header">
        <h1>Movie Recommender 🎬</h1>
      </header>
      
      {renderContent()}
    </div>
  );
}

export default App;
import React, { useState } from 'react';
import MovieInputForm from './components/MovieInputForm';
import RecommendationList from './components/RecommendationList';
import UserPreferenceInputForm from './components/UserPreferenceInputForm';
import ProfilePage from './components/ProfilePage';
import AccessibilityMenu from './components/AccessibilityMenu';
import BugReportPage from './components/BugReportPage';
import './styles/App.css'; // For basic styling

const FLASK_API_URL = 'http://localhost:5000/recommend'; // Adjust port if needed

function App() {
  const [movieName, setMovieName] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [view, setView] = useState('search');
  const [showA11y, setShowA11y] = useState(false);
  

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

  const handleRecommendFromProfile = async () => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) {
      alert('No user profile found. Please save preferences first.');
      return;
    }
    setLoading(true);
    setError(null);
    setRecommendations([]);
    try {
      const res = await fetch('http://localhost:5000/recommend/user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, top_n: 10 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to fetch recommendations');
      setRecommendations(data.recommendations || []);
      setMovieName('Preferences-based');
    } catch (e) {
      setError(e.message);
      console.error('Profile recommend error:', e);
    } finally {
      setLoading(false);
    }
  };

  // Feedback handler (works with RecommendationList)
  const handleFeedback = (recommendedMovie, rating, feedbackText) => {
    console.log(`Feedback for ${recommendedMovie}: Rating ${rating}, Text: ${feedbackText}`);
    // Send to backend and store under user's profile (uses persistent localStorage id)
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) {
      console.warn('No user id found in localStorage; feedback not saved');
      alert('No user profile found. Preferences must be created first.');
      return;
    }

    const payload = {
      user_id: userId,
      movie: recommendedMovie,
      rating: rating,
      text: feedbackText || ''
    };

    fetch('http://localhost:5000/user/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    .then(async res => {
      const data = await res.json();
      if (!res.ok) {
        console.error('Failed to save feedback', data);
        alert('Failed to save feedback: ' + (data.error || res.statusText));
      } else {
        console.log('Feedback saved', data);
        alert(`Thanks — your feedback for "${recommendedMovie}" was saved.`);
      }
    })
    .catch(err => {
      console.error('Error sending feedback', err);
      alert('Error sending feedback. See console for details.');
    });
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
    if (view === 'profile') {
      return <ProfilePage onBack={() => setView('search')} />;
    }
    if (view === 'report') {
      return <BugReportPage onBack={() => setView('search')} />;
    }
    // In a real application, you would send this to a separate Flask endpoint (e.g., /feedback)
  };

  return (
      <div className="search-view-container">
        <div className="search-view-top">
          <div className="search-input-wrapper">
            <MovieInputForm onSubmit={handleRecommend} loading={loading} />
          </div>
    <div className="app-container">
      <header className="app-header">
        <h1>Movie Recommender 🎬</h1>
      </header>
      
      <MovieInputForm onSubmit={handleRecommend} loading={loading} />

          <div className="profile-area">
            <button onClick={() => setView('profile')} className="submit-button profile-button">My Profile</button>
            <button onClick={handleRecommendFromProfile} className="submit-button profile-button">Use My Preferences</button>
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
          </div>
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
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', justifyContent: 'flex-end' }}>
          <button aria-label="Accessibility settings" onClick={() => setShowA11y(true)} className="profile-button">Accessibility</button>
          <button aria-label="Report a bug" onClick={() => setView('report')} className="profile-button">Report Bug</button>
        </div>
      </header>
      
      {renderContent()}
      <AccessibilityMenu isOpen={showA11y} onClose={() => setShowA11y(false)} />
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

import React, { useState, useEffect } from 'react';
import MovieInputForm from './components/MovieInputForm';
import RecommendationList from './components/RecommendationList';
import UserPreferenceInputForm from './components/UserPreferenceInputForm';
import ProfilePage from './components/ProfilePage';
import BugReportPage from './components/BugReportPage';
import AccessibilityMenu from './components/AccessibilityMenu';
import ToWatchList from './components/ToWatchList';
import './styles/App.css'; // For basic styling
import API_BASE from './api';

function App() {
  const [movieName, setMovieName] = useState('');
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [view, setView] = useState('search');
  const [userWatchlist, setUserWatchlist] = useState([]);
  const [recommendationCount, setRecommendationCount] = useState(10);

  useEffect(() => {
    // fetch current user's watchlist on mount
    const fetchWatchlist = async () => {
      const userId = localStorage.getItem('nextflix_user_id');
      if (!userId) { setUserWatchlist([]); return; }
      try {
        const res = await fetch(`${API_BASE}/user/watchlist/${userId}`);
        if (res.ok) {
          const d = await res.json();
          setUserWatchlist(d.watchlist || []);
        }
      } catch (e) { console.warn('Failed to fetch watchlist', e); }
    };
    fetchWatchlist();
  }, []);

  // Main recommendation call: uses /similar GET which returns full objects.
  // Request top 10 results.
const handleRecommend = async (query, searchType) => {
  setLoading(true);
  setError(null);
  setRecommendations([]);

  try {
    const q = query.trim();
    if (searchType === 'director') {
      const url = `${API_BASE}/search?director=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Director search failed");
      setRecommendations(json.results);
      setMovieName(`Director: ${q}`);
      return;
    }

    if (searchType === 'actor') {
      const url = `${API_BASE}/search?actor=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Actor search failed");
      setRecommendations(json.results);
      setMovieName(`Actor: ${q}`);
      return;
    }
    if (searchType === 'genre') {
      const url = `${API_BASE}/search?genre=${encodeURIComponent(q)}`;
      const res = await fetch(url);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Genre search failed");
      setRecommendations(json.results);
      setMovieName(`Genre: ${q}`);
      return;
    }

    const params = new URLSearchParams({ title: q, top: recommendationCount });
    const response = await fetch(`${API_BASE}/similar?${params.toString()}`);

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Title search failed");

    // similar returns candidate objects (may not include enriched synopsis/platforms)
    // fetch enriched details per title to ensure synopsis/platforms are available
    const recs = data.recommendations || [];
    const detailed = [];
    for (const r of recs.slice(0, recommendationCount)) {
      try {
        // r may be an object with movie_title or a string title
        const title = (typeof r === 'string') ? r : (r.movie_title || r.title || '');
        if (!title) continue;
        const mres = await fetch(`${API_BASE}/movie?title=${encodeURIComponent(title)}`);
        if (mres.ok) {
          const md = await mres.json();
          detailed.push(md.details || md);
        } else {
          // fallback to original object
          detailed.push(r);
        }
      } catch (err) {
        console.warn('Failed to fetch details for', r, err);
        detailed.push(r);
      }
    }

    setRecommendations(detailed);
    setMovieName(q);

  } catch (e) {
    setError(e.message);
  } finally {
    setLoading(false);
  }
};


  // Recommend using stored user preferences
  const handleRecommendFromProfile = async () => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) return alert('No user profile found. Please save preferences first.');
    setLoading(true);
    setError(null);
    setRecommendations([]);
    try {
      const res = await fetch(`${API_BASE}/recommend/user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, top_n: recommendationCount })
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || `HTTP ${res.status}`);
      }
      const d = await res.json();
      // backend returns a list of titles; fetch details for each to show consistent objects
      const titles = d.recommendations || [];
      const detailed = [];
      for (const t of titles.slice(0, recommendationCount)) {
        try {
          const mres = await fetch(`${API_BASE}/movie?title=${encodeURIComponent(t)}`);
          if (mres.ok) {
            const md = await mres.json();
            // server returns either {details: {...}} or full row
            detailed.push(md.details || md);
          }
        } catch (err) {
          console.warn('Failed to fetch movie details for', t, err);
        }
      }
      setRecommendations(detailed);
      setMovieName('From My Preferences');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Feedback handler: POST to backend /user/feedback
  const handleFeedback = async (recommendedMovie, rating, feedbackText) => {
    try {
      const userId = localStorage.getItem('nextflix_user_id') || null;
      const payload = { user_id: userId, movie: recommendedMovie, rating, text: feedbackText };
      const res = await fetch(`${API_BASE}/user/feedback`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      if (!res.ok) {
        console.error('Failed to submit feedback', await res.text());
      }
    } catch (e) {
      console.error('Error sending feedback', e);
    }
  };

  const addToWatchlist = async (movieTitle) => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) return alert('No user profile found.');
    try {
      const res = await fetch(`${API_BASE}/user/watchlist`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, movie: movieTitle })
      });
      if (res.ok) {
        alert(`Added "${movieTitle}" to your to-watch list.`);
        // remove movie from current recommendations view so it no longer appears
        setRecommendations(prev => prev.filter(m => (m.movie_title || '').trim().toLowerCase() !== (movieTitle || '').trim().toLowerCase()));
        // update local watchlist state
        setUserWatchlist(prev => {
          const low = new Set(prev.map(p => p.trim().toLowerCase()));
          if (!low.has(movieTitle.trim().toLowerCase())) return [...prev, movieTitle];
          return prev;
        });
      }
    } catch (e) { console.error(e); }
  };

  const removeFromWatchlist = async (movieTitle) => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) return alert('No user profile found.');
    try {
      const res = await fetch(`${API_BASE}/user/watchlist/remove`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, movie: movieTitle })
      });
      if (res.ok) {
        setUserWatchlist(prev => prev.filter(m => m.trim().toLowerCase() !== movieTitle.trim().toLowerCase()));
        // optionally re-fetch recommendations or leave as-is
      }
    } catch (e) { console.error(e); }
  };

  const toggleWatchlist = async (movieTitle) => {
    const exists = userWatchlist.map(m => m.trim().toLowerCase()).includes((movieTitle||'').trim().toLowerCase());
    if (exists) {
      await removeFromWatchlist(movieTitle);
      alert(`Removed "${movieTitle}" from your to-watch list.`);
    } else {
      await addToWatchlist(movieTitle);
    }
  };

  const addToFavorites = async (movieTitle) => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) return alert('No user profile found.');
    try {
      const res = await fetch(`${API_BASE}/user/favorites`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, movie: movieTitle })
      });
      if (res.ok) {
        alert(`Added "${movieTitle}" to your favorites.`);
      }
    } catch (e) { console.error(e); }
  };

  const markAsSeen = async (movieTitle) => {
    const userId = localStorage.getItem('nextflix_user_id');
    if (!userId) return alert('No user profile found.');
    try {
      const res = await fetch(`${API_BASE}/user/seen`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: userId, movie: movieTitle })
      });
      if (res.ok) {
        alert(`Marked "${movieTitle}" as seen.`);
      }
    } catch (e) { console.error(e); }
  };

  const openPreferences = () => setView('preferences');
  const openProfile = () => setView('profile');
  const openReport = () => setView('report');
  const backToSearch = () => setView('search');

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>NextFlix: A Movie Recommendation App 🎬</h1>
        <div className="header-actions">
          <button aria-label="Home" onClick={() => setView('search')} className="profile-button">Home</button>
          <button aria-label="My Profile" onClick={openProfile} className="profile-button">My Profile</button>
          <button aria-label="To-Watch" onClick={() => setView('watchlist')} className="profile-button">To-Watch</button>
          <button aria-label="Preferences" onClick={openPreferences} className="profile-button">Preferences</button>
          <button aria-label="Accessibility settings" onClick={() => setView('accessibility')} className="profile-button">Accessibility</button>
          <button aria-label="Report Bug" onClick={openReport} className="profile-button">Report Bug</button>
        </div>
      </header>


      {view === 'search' && (
        <>
          <MovieInputForm onSubmit={handleRecommend} loading={loading} />

          <div className="recommendation-count-control" style={{ margin: '8px 0' }}>
            <label htmlFor="recommendationCount" style={{ marginRight: 8 }}>Number of recommendations:</label>
            <input id="recommendationCount" type="number" min={1} max={50} value={recommendationCount} onChange={e => setRecommendationCount(Number(e.target.value) || 1)} style={{ width: 80 }} />
          </div>

          <div className="preference-action">
            <button onClick={handleRecommendFromProfile} className="use-preferences-button">Use My Preferences</button>
          </div>

          {loading && <p>Generating recommendations...</p>}
          {error && <p className="error-message">Error: {error}</p>}

          {recommendations.length > 0 && (
            <RecommendationList 
              movieName={movieName}
              recommendations={recommendations} 
              onFeedbackSubmit={handleFeedback}
              watchlist={userWatchlist}
              onToggleWatchlist={toggleWatchlist}
              onAddToFavorites={addToFavorites}
              onMarkSeen={markAsSeen}
            />
          )}
        </>
      )}

      {view === 'preferences' && (
        <UserPreferenceInputForm onBackClick={backToSearch} />
      )}

      {view === 'profile' && (
        <ProfilePage onBack={backToSearch} />
      )}

      {view === 'report' && (
        <BugReportPage onBack={backToSearch} />
      )}
      {view === 'accessibility' && (
        <AccessibilityMenu onClose={backToSearch} onBack={backToSearch} />
      )}
      {view === 'watchlist' && (
        <ToWatchList onBack={backToSearch} onFeedbackSubmit={handleFeedback} onAddToFavorites={addToFavorites} onMarkSeen={markAsSeen} watchlist={userWatchlist} onToggleWatchlist={toggleWatchlist} />
      )}
    </div>
  );
}

export default App;
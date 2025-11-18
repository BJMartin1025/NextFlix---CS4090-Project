import React, { useEffect, useState } from 'react';
import '../styles/RecommendationList.css';
import RecommendationList from './RecommendationList';

function ToWatchList({ onBack, onFeedbackSubmit, onAddToFavorites, onMarkSeen, watchlist = [], onToggleWatchlist }) {
  const [detailedList, setDetailedList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    const id = localStorage.getItem('nextflix_user_id');
    setUserId(id);
    if (id) fetchWatchlistDetails(id);
    else setLoading(false);
  }, []);

  // If the watchlist prop changes (items added/removed), refresh details
  useEffect(() => {
    const id = localStorage.getItem('nextflix_user_id');
    if (id) fetchWatchlistDetails(id);
  }, [watchlist]);

  const fetchWatchlistDetails = async (id) => {
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:5000/user/watchlist/${id}`);
      if (!res.ok) {
        setDetailedList([]);
        return;
      }
      const d = await res.json();
      const titles = d.watchlist || [];
      // fetch movie details for each title
      const detailPromises = titles.map(async (t) => {
        try {
          const mres = await fetch(`http://localhost:5000/movie?title=${encodeURIComponent(t)}`);
          if (mres.ok) {
            const md = await mres.json();
            return md.details || md;
          }
        } catch (e) { console.warn('Failed to fetch details for', t, e); }
        return { movie_title: t };
      });
      const detailed = await Promise.all(detailPromises);
      setDetailedList(detailed);
    } catch (e) {
      console.error('Failed to load watchlist', e);
      setDetailedList([]);
    } finally {
      setLoading(false);
    }
  };

  if (!userId) return (
    <div className="input-form-container">
      <h2>To-Watch List</h2>
      <p>No user profile found. Save preferences or create a profile first.</p>
      <button className="back-button" onClick={onBack}>← Back</button>
    </div>
  );

  return (
    <div className="input-form-container">
      <h2>Your To-Watch List</h2>
      {loading && <div>Loading...</div>}
      {!loading && detailedList.length === 0 && <div>No items in your to-watch list.</div>}
      {!loading && detailedList.length > 0 && (
        <RecommendationList
          movieName={'To-Watch List'}
          recommendations={detailedList}
          onFeedbackSubmit={onFeedbackSubmit}
          watchlist={watchlist}
          onToggleWatchlist={onToggleWatchlist}
          onAddToFavorites={onAddToFavorites}
          onMarkSeen={onMarkSeen}
        />
      )}
      <div style={{ marginTop: 12 }}>
        <button className="back-button" onClick={onBack}>← Back</button>
      </div>
    </div>
  );
}

export default ToWatchList;

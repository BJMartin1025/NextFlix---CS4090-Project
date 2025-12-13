import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import RecommendationList from '../components/RecommendationList';

beforeEach(() => {
  window.alert = jest.fn();
});

const sample = [
  {
    movie_title: 'Inception',
    director_name: 'Christopher Nolan',
    actor_1_name: 'Leonardo DiCaprio',
    actor_2_name: '',
    actor_3_name: '',
    genres: 'Sci-Fi',
    synopsis: 'A dream movie',
    platforms: ['Netflix'],
    imdb_score: '8.8',
    rotten_tomatoes_score: '87%',
    metacritic_score: '74',
    score: 9.5
  }
];

test('RecommendationList renders items and calls handlers', () => {
  const onFeedbackSubmit = jest.fn();
  const onToggleWatchlist = jest.fn();
  const onAddToFavorites = jest.fn();
  const onMarkSeen = jest.fn();

  render(<RecommendationList movieName="Test" recommendations={sample} onFeedbackSubmit={onFeedbackSubmit} watchlist={[]} onToggleWatchlist={onToggleWatchlist} onAddToFavorites={onAddToFavorites} onMarkSeen={onMarkSeen} />);

  expect(screen.getByText(/Top Recommendations for/i)).toBeInTheDocument();
  expect(screen.getByText(/Inception/)).toBeInTheDocument();

  // favorite button
  fireEvent.click(screen.getByText(/★ Favorite/i));
  expect(onAddToFavorites).toHaveBeenCalledWith('Inception');

  // mark seen
  fireEvent.click(screen.getByText(/✓ Mark Seen/i));
  expect(onMarkSeen).toHaveBeenCalledWith('Inception');

  // add to watchlist
  fireEvent.click(screen.getByText(/\+ To Watchlist|✔ In Watchlist/));
  expect(onToggleWatchlist).toHaveBeenCalledWith('Inception');

  // submit feedback: type text and click submit
  const textarea = screen.getByPlaceholderText(/Optional: Tell us what you thought/i);
  fireEvent.change(textarea, { target: { value: 'Great!' } });
  const submit = screen.getByText(/Submit Feedback/i);
  fireEvent.click(submit);
  // onFeedbackSubmit is called with (movieTitle, rating, text); rating defaults to 0
  expect(onFeedbackSubmit).toHaveBeenCalledWith('Inception', 0, 'Great!');
});

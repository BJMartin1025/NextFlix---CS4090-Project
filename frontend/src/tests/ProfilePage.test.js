import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ProfilePage from '../components/ProfilePage';

beforeEach(() => {
  // set a user id and mock profile/options fetches
  localStorage.setItem('nextflix_user_id', 'test_user');
  global.fetch = jest.fn((url) => {
    if (url && url.includes('/user/preferences/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ preferences: { movies: ['Inception'] } }) });
    }
    if (url && url.includes('/user/feedback/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ feedback: [] }) });
    }
    if (url && url.endsWith('/catalog/options')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ movies: ['Inception'], directors: ['Christopher Nolan'], actors: [], genres: [] }) });
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
  });
});

test('ProfilePage loads and shows user id and preferences', async () => {
  render(<ProfilePage onBack={jest.fn()} />);
  await waitFor(() => expect(screen.getByText(/Your Profile/i)).toBeInTheDocument());
  expect(screen.getByText(/User ID:/i)).toBeInTheDocument();
  expect(screen.getByText(/Inception/)).toBeInTheDocument();
});

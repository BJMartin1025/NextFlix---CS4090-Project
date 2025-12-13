import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import UserPreferenceInputForm from '../components/UserPreferenceInputForm';

beforeEach(() => {
  // mock catalog/options fetch to return some options
  global.fetch = jest.fn((url) => {
    if (url && url.endsWith('/catalog/options')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ movies: ['Inception'], directors: ['Christopher Nolan'], actors: ['Leonardo DiCaprio'], genres: ['Sci-Fi'] }) });
    }
    if (url && url.endsWith('/user/preferences')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) });
    }
    return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
  });
  window.alert = jest.fn();
});

test('UserPreferenceInputForm adds movie from options and saves', async () => {
  const { container } = render(<UserPreferenceInputForm onBackClick={jest.fn()} />);
  // wait for options to be fetched
  await waitFor(() => expect(global.fetch).toHaveBeenCalled());

  // Scope to the first input group (movies)
  const movieGroup = container.querySelector('.input-group');
  const input = within(movieGroup).getByPlaceholderText(/Start typing and select a movie/i);
  fireEvent.change(input, { target: { value: 'Inception' } });
  // Click the Add button inside the same group
  const addButton = within(movieGroup).getByText(/Add/i);
  fireEvent.click(addButton);

  // Verify the movie appears inside the chips container specifically
  const chipsContainer = movieGroup.querySelector('.chips');
  await waitFor(() => expect(within(chipsContainer).getByText(/Inception/)).toBeInTheDocument());

  fireEvent.click(screen.getByText(/Save Preferences/i));
  await waitFor(() => expect(window.alert).toHaveBeenCalled());
});

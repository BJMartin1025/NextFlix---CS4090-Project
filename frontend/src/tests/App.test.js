import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from '../App';

describe('App (frontend)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('renders header and navigation buttons', () => {
    render(<App />);
    expect(screen.getByText(/NextFlix/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /My Profile/i })).toBeTruthy();
    // match the header Preferences button exactly to avoid matching "Use My Preferences"
    expect(screen.getByRole('button', { name: 'Preferences' })).toBeTruthy();
  });

  test('navigates to Profile and shows no-profile message when no user', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: /My Profile/i }));
    await waitFor(() => expect(screen.getByText(/No Profile Found/i)).toBeTruthy());
    expect(screen.getByRole('button', { name: /← Back/i })).toBeTruthy();
  });
});

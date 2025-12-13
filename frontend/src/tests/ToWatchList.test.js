import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ToWatchList from '../components/ToWatchList';

test('ToWatchList shows message when no user profile', () => {
  localStorage.removeItem('nextflix_user_id');
  const onBack = jest.fn();
  render(<ToWatchList onBack={onBack} watchlist={[]} />);
  expect(screen.getByText(/No user profile found/i)).toBeInTheDocument();
  fireEvent.click(screen.getByText(/← Back/i));
  expect(onBack).toHaveBeenCalled();
});

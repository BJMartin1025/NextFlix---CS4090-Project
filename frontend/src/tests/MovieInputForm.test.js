import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import MovieInputForm from '../components/MovieInputForm';

test('MovieInputForm calls onSubmit with input and search type', () => {
  const handle = jest.fn();
  render(<MovieInputForm onSubmit={handle} loading={false} />);

  const input = screen.getByPlaceholderText(/Enter your search/i);
  fireEvent.change(input, { target: { value: 'Inception' } });

  const select = screen.getByRole('combobox');
  fireEvent.change(select, { target: { value: 'director' } });

  const btn = screen.getByRole('button', { name: /Get Recommendations/i });
  fireEvent.click(btn);

  expect(handle).toHaveBeenCalledTimes(1);
  expect(handle).toHaveBeenCalledWith('Inception', 'director');
});

test('MovieInputForm disables inputs when loading', () => {
  const handle = jest.fn();
  render(<MovieInputForm onSubmit={handle} loading={true} />);
  expect(screen.getByRole('button')).toBeDisabled();
  expect(screen.getByPlaceholderText(/Enter your search/i)).toBeDisabled();
});

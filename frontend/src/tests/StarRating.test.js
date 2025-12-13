import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import StarRating from '../components/StarRating';

test('StarRating calls onRate when a star is clicked', () => {
  const handle = jest.fn();
  render(<StarRating onRate={handle} />);
  const stars = screen.getAllByText('★');
  expect(stars.length).toBeGreaterThanOrEqual(5);
  fireEvent.click(stars[2]); // 3rd star -> rating 3
  expect(handle).toHaveBeenCalledWith(3);
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import AccessibilityMenu from '../components/AccessibilityMenu';

test('AccessibilityMenu toggles settings and saves to localStorage', () => {
  const onClose = jest.fn();
  const onBack = jest.fn();
  render(<AccessibilityMenu onClose={onClose} onBack={onBack} />);

  // toggle dark mode
  const darkCheckbox = screen.getByLabelText(/Enable dark mode/i);
  fireEvent.click(darkCheckbox);
  expect(darkCheckbox.checked).toBe(true);

  // change subtitle size
  const select = screen.getByRole('combobox');
  fireEvent.change(select, { target: { value: 'large' } });

  // save should call onClose and write to localStorage
  fireEvent.click(screen.getByText(/Save/i));
  expect(onClose).toHaveBeenCalled();
  const raw = localStorage.getItem('nextflix_accessibility');
  expect(raw).not.toBeNull();
});

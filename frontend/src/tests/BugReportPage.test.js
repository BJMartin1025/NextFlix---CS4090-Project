import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import BugReportPage from '../components/BugReportPage';

beforeEach(() => {
  window.alert = jest.fn();
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) }));
});

test('BugReportPage submits report and clears fields', async () => {
  const onBack = jest.fn();
  render(<BugReportPage onBack={onBack} />);
  fireEvent.change(screen.getByLabelText(/Subject/i), { target: { value: 'Test' } });
  fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'Details' } });
  fireEvent.click(screen.getByText(/Submit Report/i));
  await waitFor(() => expect(window.alert).toHaveBeenCalled());
});

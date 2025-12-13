import '@testing-library/jest-dom';

// Optionally initialize MSW for tests. Handlers are located in src/tests/mocks.
// This file is executed automatically by Create React App when running tests.

if (process.env.NODE_ENV === 'test') {
  try {
    // eslint-disable-next-line global-require
    const { server } = require('./tests/mocks/server');
    // Start the MSW server for all tests
    server.listen({ onUnhandledRequest: 'warn' });
    // Reset handlers after each test to avoid test bleed
    afterEach(() => server.resetHandlers());
    // Clean up when tests are finished
    afterAll(() => server.close());
  } catch (e) {
    // If MSW isn't installed, tests that don't require it will still run.
    // Silently ignore if require fails.
  }
}

import React from 'react';
import ReactDOM from 'react-dom/client'; // Import the client-specific method for React 18+
import './styles/index.css'; // Optional: for global styles
import App from './App'; // Import your main application component

// Get the root element from public/index.html
const rootElement = document.getElementById('root');

// Create a React root and render the application
// This is the standard way to mount a React application using React 18+
const root = ReactDOM.createRoot(rootElement);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
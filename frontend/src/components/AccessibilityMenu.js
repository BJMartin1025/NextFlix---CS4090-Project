import React, { useEffect, useState } from 'react';
import '../styles/AccessibilityMenu.css';

function AccessibilityMenu({ onClose, onBack }) {
  const defaultSettings = {
    fontSize: 'medium', // small, medium, large
    darkMode: false,
    highContrast: false,
    subtitlesEnabled: false,
    subtitleSize: 'medium' // small, medium, large
  };

  const [settings, setSettings] = useState(defaultSettings);

  useEffect(() => {
    // Load saved settings
    try {
      const raw = localStorage.getItem('nextflix_accessibility');
      if (raw) setSettings(JSON.parse(raw));
    } catch (e) {
      console.error('Failed to load accessibility settings', e);
    }
  }, []);

  useEffect(() => {
    applySettings(settings);
  }, [settings]);

  const applySettings = (s) => {
    // Font size
    const map = { small: '16px', medium: '20px', large: '24px' };
    document.documentElement.style.fontSize = map[s.fontSize] || map.medium;

    // Dark mode
    if (s.darkMode) document.body.classList.add('dark-mode'); else document.body.classList.remove('dark-mode');

    // High contrast
    if (s.highContrast) document.body.classList.add('high-contrast'); else document.body.classList.remove('high-contrast');

    // Subtitles flag (no video here, but store class)
    if (s.subtitlesEnabled) document.body.classList.add('subtitles-enabled'); else document.body.classList.remove('subtitles-enabled');

    // Subtitle size stored as CSS variable
    const sizeMap = { small: '0.9rem', medium: '1.1rem', large: '1.3rem' };
    document.documentElement.style.setProperty('--subtitle-size', sizeMap[s.subtitleSize] || sizeMap.medium);
  };

  const update = (patch) => setSettings(prev => ({ ...prev, ...patch }));

  const handleSave = () => {
    try {
      localStorage.setItem('nextflix_accessibility', JSON.stringify(settings));
    } catch (e) {
      console.error('Failed to save accessibility settings', e);
    }
    onClose && onClose();
  };

  const handleReset = () => {
    setSettings(defaultSettings);
    try { localStorage.removeItem('nextflix_accessibility'); } catch (e) {}
  };

  return (
    <div className="input-form-container accessibility-page">
      <h2>Accessibility Settings</h2>

        <div className="access-row">
          <label>Font Size</label>
          <div className="access-controls">
            <button onClick={() => update({ fontSize: 'small' })} className={settings.fontSize === 'small' ? 'active' : ''}>A-</button>
            <button onClick={() => update({ fontSize: 'medium' })} className={settings.fontSize === 'medium' ? 'active' : ''}>A</button>
            <button onClick={() => update({ fontSize: 'large' })} className={settings.fontSize === 'large' ? 'active' : ''}>A+</button>
          </div>
        </div>

        <div className="access-row">
          <label>Dark Mode</label>
          <div className="access-controls">
            <input id="darkMode" type="checkbox" checked={settings.darkMode} onChange={(e) => update({ darkMode: e.target.checked })} />
            <label htmlFor="darkMode">Enable dark mode</label>
          </div>
        </div>

        <div className="access-row">
          <label>High Contrast</label>
          <div className="access-controls">
            <input id="highContrast" type="checkbox" checked={settings.highContrast} onChange={(e) => update({ highContrast: e.target.checked })} />
            <label htmlFor="highContrast">Increase contrast</label>
          </div>
        </div>

        <div className="access-row">
          <label>Subtitles</label>
          <div className="access-controls">
            <input id="subOn" type="checkbox" checked={settings.subtitlesEnabled} onChange={(e) => update({ subtitlesEnabled: e.target.checked })} />
            <label htmlFor="subOn">Show subtitles (app preference)</label>
            <select value={settings.subtitleSize} onChange={(e) => update({ subtitleSize: e.target.value })}>
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
          </div>
        </div>

        <div className="access-actions">
          <button className="submit-button" onClick={handleSave}>Save</button>
          <button className="btn secondary" onClick={handleReset}>Reset</button>
          <button className="back-button" onClick={() => { onClose && onClose(); onBack && onBack(); }}>← Back</button>
        </div>
    </div>
  );
}

export default AccessibilityMenu;

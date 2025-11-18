import React, { useState, useEffect } from 'react';
import '../styles/UserPreferenceInputForm.css';

function BugReportPage({ onBack }) {
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    const id = localStorage.getItem('nextflix_user_id');
    if (id) setUserId(id);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!subject.trim() || !description.trim()) {
      alert('Please provide both a subject and a description.');
      return;
    }

    const payload = {
      user_id: userId,
      subject: subject.trim(),
      description: description.trim()
    };

    setSubmitting(true);
    try {
      const res = await fetch('http://localhost:5000/reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        console.error('Report failed', data);
        alert('Failed to submit report: ' + (data.error || res.statusText));
      } else {
        alert('Thank you — your report was submitted.');
        setSubject('');
        setDescription('');
      }
    } catch (err) {
      console.error('Error submitting report', err);
      alert('Error submitting report. See console for details.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="input-form-container">
      <h2>Submit a Bug / Issue</h2>
      <p>Please describe the problem you encountered. Include steps to reproduce if possible.</p>

      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="subject">Subject</label>
          <input id="subject" name="subject" value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Short summary" />
        </div>

        <div className="input-group">
          <label htmlFor="description">Description</label>
          <textarea id="description" name="description" value={description} onChange={(e) => setDescription(e.target.value)} rows="6" placeholder="Detailed description, steps to reproduce, expected vs actual" />
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button type="submit" className="submit-button" disabled={submitting}>{submitting ? 'Submitting...' : 'Submit Report'}</button>
          <button type="button" className="back-button" onClick={onBack}>← Back</button>
        </div>
      </form>
    </div>
  );
}

export default BugReportPage;

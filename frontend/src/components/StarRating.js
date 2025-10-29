// src/components/StarRating.js
import React, { useState } from 'react';
import './StarRating.css'; // For star colors/icons

// Assuming you use 5 stars. You can use an icon library like react-icons or simple characters
const MAX_RATING = 5;

function StarRating({ onRate }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const stars = [...Array(MAX_RATING)].map((_, index) => {
    index += 1;
    return (
      <span
        key={index}
        className={index <= (hover || rating) ? 'star-on' : 'star-off'}
        onClick={() => { setRating(index); onRate(index); }}
        onMouseEnter={() => setHover(index)}
        onMouseLeave={() => setHover(rating)}
      >
        ★
      </span>
    );
  });
  
  return <div className="star-rating-container">{stars}</div>;
}

export default StarRating;
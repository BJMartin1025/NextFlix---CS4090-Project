import { rest } from 'msw';

const API_BASE = 'http://localhost:5000';

export const handlers = [
  // catalog options
  rest.get(`${API_BASE}/catalog/options`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ movies: ['Inception'], directors: ['Christopher Nolan'], actors: ['Leonardo DiCaprio'], genres: ['Sci-Fi'] }));
  }),

  // user preferences
  rest.get(`${API_BASE}/user/preferences/:id`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ preferences: { movies: ['Inception'], genres: ['Sci-Fi'], directors: ['Christopher Nolan'], actors: [] } }));
  }),

  // user feedback
  rest.get(`${API_BASE}/user/feedback/:id`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ feedback: [] }));
  }),

  // movie details
  rest.get(`${API_BASE}/movie`, (req, res, ctx) => {
    const title = req.url.searchParams.get('title') || 'Inception';
    return res(ctx.status(200), ctx.json({ movie_title: title, director_name: 'Christopher Nolan', synopsis: 'A dream movie', platforms: ['Netflix'], imdb_score: '8.8', rotten_tomatoes_score: '87%', metacritic_score: '74' }));
  }),

  // user watchlist
  rest.get(`${API_BASE}/user/watchlist/:id`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ watchlist: ['Inception'] }));
  }),

  // recommendations (similar) endpoint
  rest.get(`${API_BASE}/similar`, (req, res, ctx) => {
    // return a simple recommendation list
    const title = req.url.searchParams.get('title') || 'Inception';
    return res(ctx.status(200), ctx.json({ target: { movie_title: title }, recommendations: [{ movie_title: 'The Dark Knight', director_name: 'Christopher Nolan' }] }));
  }),

  // generic POST handlers used by forms
  rest.post(`${API_BASE}/user/preferences`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'ok' }));
  }),
  rest.post(`${API_BASE}/reports`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'ok', report: { id: 1 } }));
  }),
  rest.post(`${API_BASE}/user/watchlist`, (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'ok', watchlist: ['Inception'] }));
  }),
];

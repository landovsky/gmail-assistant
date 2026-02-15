// Main Hono application setup
import { Hono } from 'hono';

export const app = new Hono();

// Health check endpoint
app.get('/api/health', (c) => {
  return c.json({ status: 'ok' });
});

// Root redirect
app.get('/', (c) => {
  return c.redirect('/debug/emails');
});

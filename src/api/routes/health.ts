import { Hono } from 'hono';

export const healthRoutes = new Hono();

// GET /api/health - Health check endpoint (no auth required)
healthRoutes.get('/', (c) => {
  return c.json({ status: 'ok' });
});

// Gmail Assistant v2 - Main Entry Point
import { serve } from '@hono/node-server';
import { app } from './api/app';
import { config } from './lib/config';

const port = config.server.port;

console.log(`🚀 Gmail Assistant v2 starting on http://${config.server.host}:${port}`);

serve({
  fetch: app.fetch,
  port,
  hostname: config.server.host,
});

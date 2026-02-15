import { createMiddleware } from 'hono/factory';
import { appConfig } from '../../config/index.js';

/**
 * HTTP Basic Authentication middleware.
 * If credentials are configured via environment variables, require them.
 * If not configured, all endpoints are public (single-user / trusted environment).
 */
export const basicAuth = createMiddleware(async (c, next) => {
  const creds = appConfig.auth.basicAuth;

  // No auth configured -- everything is public
  if (!creds) {
    return next();
  }

  const authHeader = c.req.header('Authorization');
  if (!authHeader || !authHeader.startsWith('Basic ')) {
    c.header('WWW-Authenticate', 'Basic realm="Gmail Assistant"');
    return c.json({ detail: 'Unauthorized' }, 401);
  }

  const encoded = authHeader.slice('Basic '.length);
  const decoded = Buffer.from(encoded, 'base64').toString('utf-8');
  const [username, password] = decoded.split(':');

  if (username !== creds.username || password !== creds.password) {
    c.header('WWW-Authenticate', 'Basic realm="Gmail Assistant"');
    return c.json({ detail: 'Unauthorized' }, 401);
  }

  return next();
});

import { describe, it, expect } from 'bun:test';
import { app } from '../src/api/app';

describe('API Health Check', () => {
  it('should return ok status', async () => {
    const res = await app.request('/api/health');
    expect(res.status).toBe(200);

    const data = await res.json();
    expect(data).toEqual({ status: 'ok' });
  });

  it('should redirect root to debug page', async () => {
    const res = await app.request('/');
    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe('/debug/emails');
  });
});

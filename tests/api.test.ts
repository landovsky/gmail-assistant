import { describe, it } from 'node:test';
import assert from 'node:assert';
import { app } from '../src/api/app';

describe('API Health Check', () => {
  it('should return ok status', async () => {
    const res = await app.request('/api/health');
    assert.strictEqual(res.status, 200);

    const data = await res.json();
    assert.deepStrictEqual(data, { status: 'ok' });
  });

  it('should redirect root to debug page', async () => {
    const res = await app.request('/');
    assert.strictEqual(res.status, 302);
    assert.strictEqual(res.headers.get('location'), '/debug/emails');
  });
});

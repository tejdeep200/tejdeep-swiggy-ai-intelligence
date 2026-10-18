import assert from 'node:assert/strict';
import test from 'node:test';
import { isSameOrigin } from '../lib/request-origin.ts';

test('accepts browser localhost origin when Docker binds to 0.0.0.0', () => {
  assert.equal(isSameOrigin('http://localhost:3000', 'localhost:3000', 'http://0.0.0.0:3000/api/ask'), true);
  assert.equal(isSameOrigin('http://127.0.0.1:3000', '127.0.0.1:3000', 'http://0.0.0.0:3000/api/ask'), true);
});
test('rejects other hosts, ports, protocols and malformed origins', () => {
  for (const origin of ['http://evil.example:3000', 'http://localhost:4000', 'https://localhost:3000', 'null', 'invalid']) {
    assert.equal(isSameOrigin(origin, 'localhost:3000', 'http://0.0.0.0:3000/api/ask'), false);
  }
  assert.equal(isSameOrigin('http://localhost:3000', null, 'http://0.0.0.0:3000/api/ask'), false);
});

test('accepts the Vercel HTTPS origin while the internal transport uses HTTP', () => {
  assert.equal(isSameOrigin('https://swiggy.vercel.app', 'swiggy.vercel.app', 'http://swiggy.vercel.app/api/ask', 'https:'), true);
  assert.equal(isSameOrigin('http://swiggy.vercel.app', 'swiggy.vercel.app', 'http://swiggy.vercel.app/api/ask', 'https:'), false);
});

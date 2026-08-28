import { describe, it, expect, afterEach } from 'vitest';
import { loadTwelveDataApiKey } from './env';

// index.test.ts mocks this module out wholesale (vi.mock('./env')), so the real
// throw-if-missing validation below was never actually executed by any test -- the one place
// the whole app decides whether it has credentials at all.
describe('loadTwelveDataApiKey', () => {
  const saved = process.env.TWELVE_DATA_API_KEY;

  afterEach(() => {
    if (saved === undefined) {
      delete process.env.TWELVE_DATA_API_KEY;
    } else {
      process.env.TWELVE_DATA_API_KEY = saved;
    }
  });

  it('returns the key when it is set', () => {
    process.env.TWELVE_DATA_API_KEY = 'test-key-123';
    expect(loadTwelveDataApiKey()).toBe('test-key-123');
  });

  it('throws a message pointing at .env.example when the key is missing', () => {
    delete process.env.TWELVE_DATA_API_KEY;
    expect(() => loadTwelveDataApiKey()).toThrow(/TWELVE_DATA_API_KEY is not set/);
    expect(() => loadTwelveDataApiKey()).toThrow(/\.env\.example/);
  });

  it('treats an empty-string key as missing rather than as a usable credential', () => {
    // `!key` catches '' as well as undefined -- an empty value in .env is a misconfiguration,
    // not a key, and must fail loudly here instead of producing 401s deeper in client.ts.
    process.env.TWELVE_DATA_API_KEY = '';
    expect(() => loadTwelveDataApiKey()).toThrow(/TWELVE_DATA_API_KEY is not set/);
  });
});

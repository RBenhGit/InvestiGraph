import 'dotenv/config';

// Single read point for TWELVE_DATA_API_KEY — nothing else in the codebase should read
// process.env.TWELVE_DATA_API_KEY directly.
export function loadTwelveDataApiKey(): string {
  const key = process.env.TWELVE_DATA_API_KEY;
  if (!key) {
    throw new Error(
      'TWELVE_DATA_API_KEY is not set — copy .env.example to .env and fill in your key',
    );
  }
  return key;
}

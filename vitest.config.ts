import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/investigraph/web/static/**/*.test.js'],
  },
});

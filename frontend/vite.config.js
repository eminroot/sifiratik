import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Where the dev server sends /api. Override when 8000 is taken, e.g.
// GUS_API_URL=http://127.0.0.1:8001 npm run dev
const apiTarget = process.env.GUS_API_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
});

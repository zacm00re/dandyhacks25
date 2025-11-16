import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src/frontend'),
    },
  },
  root: '.',
  publicDir: 'public',
  build: {
    outDir: 'dist',
  },
  server: {
    port: 5173,
  },
});

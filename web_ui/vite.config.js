import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/rpc': {
        target: 'ws://127.0.0.1:8765',
        ws: true,
      },
    },
  },
});

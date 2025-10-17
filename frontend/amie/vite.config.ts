import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      // send any API call to your FastAPI (default http://127.0.0.1:8000)
      '^/(upload-file|invoke|state|debug_state|debug)': {
        target: process.env.VITE_API_BASE || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});

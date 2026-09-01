import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // The demo is shared through a temporary Cloudflare Tunnel. Restrict the
  // preview host allow-list to that tunnel's domain instead of disabling the
  // host check globally.
  preview: {
    allowedHosts: ['.trycloudflare.com'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    }
  }
})

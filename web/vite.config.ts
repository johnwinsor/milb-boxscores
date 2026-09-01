import { copyFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

/**
 * GitHub Pages serves static files with no SPA rewrite, so a deep link like
 * /player/829045 -- a shared URL, or just a refresh -- hits a path with no file
 * and gets GitHub's 404. Pages does serve a repo's own 404.html for any
 * unmatched path, so shipping a copy of index.html under that name lets the
 * router take over and render the right route.
 */
function spaFallback() {
  return {
    name: 'spa-fallback-404',
    closeBundle() {
      const dist = resolve(__dirname, 'dist')
      copyFileSync(resolve(dist, 'index.html'), resolve(dist, '404.html'))
    },
  }
}

// The site is served from https://<user>.github.io/milb-boxscores/, so every
// asset URL needs that prefix. BASE_PATH lets the Action override it (a custom
// domain or a user-page repo serves from '/').
export default defineConfig({
  base: process.env.BASE_PATH ?? '/milb-boxscores/',
  plugins: [react(), tailwindcss(), spaFallback()],
  build: { outDir: 'dist', sourcemap: false },
})

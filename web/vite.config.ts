import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The site is served from https://<user>.github.io/milb-boxscores/, so every
// asset URL needs that prefix. BASE_PATH lets the Action override it (a custom
// domain or a user-page repo serves from '/').
export default defineConfig({
  base: process.env.BASE_PATH ?? '/milb-boxscores/',
  plugins: [react(), tailwindcss()],
  build: { outDir: 'dist', sourcemap: false },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite runs the app while developing (npm run dev, on port 5173)
// and builds the files that get deployed (npm run build, into dist/)
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.NIVAARAN_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true, proxy: { "/api": { target: api, changeOrigin: true } } },
  preview: { port: 4173, proxy: { "/api": { target: api, changeOrigin: true } } },
  // The largest chunk is the landing page's lazily loaded 3D scene (three.js); it is fetched only on that page.
  build: { chunkSizeWarningLimit: 950 },
});

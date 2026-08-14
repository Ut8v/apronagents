import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the FastAPI backend runs separately; proxy API and websocket
// traffic to it so the dashboard only ever talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:4650",
      "/ws": { target: "ws://127.0.0.1:4650", ws: true },
    },
  },
  build: {
    outDir: "dist",
  },
});

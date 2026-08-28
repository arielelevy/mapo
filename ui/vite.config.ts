import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El motor corre aparte (FastAPI, puerto 8000). El proxy evita CORS en desarrollo y
// deja que `fetch("/v1/answer")` funcione igual en dev y detrás del reverse proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // SSE: sin buffering, o los eventos llegan todos juntos al final.
        configure: (proxy) => {
          proxy.on("proxyRes", (res) => {
            res.headers["cache-control"] = "no-cache, no-transform";
          });
        },
      },
    },
  },
});

// vite.config.js — Athena Console frontend bundle for the Tauri shell.
// Builds to ../dist (matches src-tauri/tauri.conf.json:frontendDist).
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: path.resolve(__dirname, "../dist"),
    emptyOutDir: true,
    target: "esnext",
    sourcemap: false,
    minify: "esbuild",
  },
  server: {
    port: 1420,
    strictPort: true,
  },
});

//以后不用每次改 vite.config.ts，只改 .env.development 就行
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());

  return {
    plugins: [vue()],

    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },

    server: {
      host: "0.0.0.0",
      port: 5173,
      open: true,

      proxy: {
        "/api": {
          target: env.VITE_API_TARGET || "http://192.168.0.105:8000",   //"http://127.0.0.1:8000", 
          changeOrigin: true,
        },
      },
    },
  };
});
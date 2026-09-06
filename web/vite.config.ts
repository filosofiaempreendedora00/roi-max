import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// O backend serve o build final; em dev o proxy evita CORS e mantém
// o mesmo caminho de API nas duas situações.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // expõe na rede local -> dá para abrir no celular em dev
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});

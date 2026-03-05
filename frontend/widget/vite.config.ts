import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  if (mode === "widget") {
    return {
      plugins: [react()],
      build: {
        lib: {
          entry: "src/embed.tsx",
          name: "EcomChatWidget",
          fileName: "ecom-chat-widget",
          formats: ["iife"],
        },
        rollupOptions: {
          output: {
            inlineDynamicImports: true,
          },
        },
      },
      define: {
        "process.env.NODE_ENV": '"production"',
      },
    };
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
    },
  };
});

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./v2/src/test/setup.ts"],
    include: ["v2/src/**/*.test.{ts,tsx}"],
  },
});

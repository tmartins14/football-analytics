import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/footballd3/components/**/*.test.js"],
  },
});

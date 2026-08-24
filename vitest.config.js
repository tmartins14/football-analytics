import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["libs/footballd3/components/**/*.test.js"],
  },
});

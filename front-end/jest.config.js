// Jest config via next/jest — wires up the Next SWC transform, CSS-module
// mocking, and module aliases so components compile exactly as the app builds
// them. Tests run in jsdom (a simulated DOM in Node) — no real browser needed.
const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

/** @type {import('jest').Config} */
const customJestConfig = {
  testEnvironment: "jest-environment-jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testMatch: ["<rootDir>/__tests__/**/*.test.js"],
};

module.exports = createJestConfig(customJestConfig);

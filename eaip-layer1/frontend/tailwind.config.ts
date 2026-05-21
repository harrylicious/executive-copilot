import type { Config } from "tailwindcss";

/**
 * Tailwind CSS v4 uses CSS-based configuration via @theme in src/index.css.
 * This config file provides content paths for class detection.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
};

export default config;

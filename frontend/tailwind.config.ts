import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        surface: "#13131a",
        border: "#ffffff10",
        primary: {
          DEFAULT: "#f59e0b",
          hover: "#d97706",
        },
        text: {
          primary: "#f8fafc",
          muted: "#94a3b8",
        },
        live: "#22c55e",
        deal: "#3b82f6",
      },
      fontFamily: {
        sans: ["var(--font-inter)"],
        display: ["var(--font-playfair)", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
export default config;

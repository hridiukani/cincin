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
        // Matched to the Lovable landing design's .dark palette
        // (converted precisely from its oklch values, not eyeballed).
        background: "#1a120c",
        surface: "#261d16",
        border: "#ffffff24",
        primary: {
          DEFAULT: "#f99549",
          hover: "#d67523",
        },
        text: {
          primary: "#f2eee4",
          muted: "#aba397",
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

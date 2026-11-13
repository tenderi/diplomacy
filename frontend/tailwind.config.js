/**
 * A colour held in a CSS variable (an oklch() value), usable with Tailwind's
 * opacity modifier (`bg-destructive/10`, `ring-ring/50`). Tailwind v3 cannot
 * apply an alpha to a bare `var()`, so it silently drops those classes; with an
 * alpha we mix the variable with transparent instead.
 */
const v = (name, fallback) => {
  const colour = fallback ? `var(${name}, ${fallback})` : `var(${name})`
  return ({ opacityValue }) =>
    opacityValue === undefined || opacityValue.startsWith("var(")
      ? colour
      : `color-mix(in oklch, ${colour} ${Number(opacityValue) * 100}%, transparent)`
}

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: v("--border"),
        input: v("--input"),
        ring: v("--ring"),
        background: v("--background"),
        foreground: v("--foreground"),
        primary: {
          DEFAULT: v("--primary"),
          foreground: v("--primary-foreground"),
        },
        secondary: {
          DEFAULT: v("--secondary"),
          foreground: v("--secondary-foreground"),
        },
        destructive: {
          DEFAULT: v("--destructive"),
          foreground: v("--destructive-foreground", "var(--foreground)"),
        },
        muted: {
          DEFAULT: v("--muted"),
          foreground: v("--muted-foreground"),
        },
        accent: {
          DEFAULT: v("--accent"),
          foreground: v("--accent-foreground"),
        },
        popover: {
          DEFAULT: v("--popover"),
          foreground: v("--popover-foreground"),
        },
        card: {
          DEFAULT: v("--card"),
          foreground: v("--card-foreground"),
        },
      },
      borderRadius: {
        lg: v("--radius"),
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
}

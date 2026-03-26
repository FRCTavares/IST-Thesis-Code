var config = {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                card: "hsl(var(--card))",
                "card-foreground": "hsl(var(--card-foreground))",
                muted: "hsl(var(--muted))",
                "muted-foreground": "hsl(var(--muted-foreground))",
                border: "hsl(var(--border))",
                accent: "hsl(var(--accent))",
                "accent-foreground": "hsl(var(--accent-foreground))",
                danger: "hsl(var(--danger))",
            },
            borderRadius: {
                lg: "0.9rem",
                md: "0.7rem",
                sm: "0.5rem",
            },
            fontFamily: {
                sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
                mono: ["IBM Plex Mono", "Cascadia Code", "monospace"],
            },
            boxShadow: {
                panel: "0 10px 26px rgba(22, 37, 58, 0.08)",
            },
        },
    },
    plugins: [],
};
export default config;

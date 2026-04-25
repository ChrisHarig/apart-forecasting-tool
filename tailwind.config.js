var config = {
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                ink: {
                    950: "#080808",
                    900: "#111111",
                    850: "#171717",
                    800: "#242424",
                    700: "#333333"
                }
            },
            boxShadow: {
                glow: "0 0 0 1px rgba(255, 255, 255, 0.08), 0 18px 48px rgba(0, 0, 0, 0.34)"
            },
            fontFamily: {
                sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Arial", "sans-serif"],
                mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "monospace"]
            }
        }
    },
    plugins: []
};
export default config;

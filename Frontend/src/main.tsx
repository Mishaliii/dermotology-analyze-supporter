import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// If the tab is restored from the browser's back/forward cache,
// force a reload so stale in-memory JS is replaced with the latest build.
window.addEventListener("pageshow", (event: PageTransitionEvent) => {
	if (event.persisted) {
		window.location.reload();
	}
});

const navEntries = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
if (navEntries[0]?.type === "back_forward") {
	window.location.reload();
}

createRoot(document.getElementById("root")!).render(<App />);

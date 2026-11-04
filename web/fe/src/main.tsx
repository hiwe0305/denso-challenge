import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./index.css";

// VITE_API_MODE=real turns MSW off and sends /api to the backend (§6.4).
const apiMode = import.meta.env.VITE_API_MODE === "real" ? "real" : "mock";

async function start() {
  if (apiMode === "mock") {
    const { worker } = await import("./mocks/browser");
    await worker.start({ onUnhandledRequest: "bypass" });
  }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
  });
  createRoot(document.getElementById("root") as HTMLElement).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <App apiMode={apiMode} />
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}

void start();

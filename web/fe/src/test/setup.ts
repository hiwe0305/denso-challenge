import { cleanup } from "@testing-library/react";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";
import { loadMockData } from "../mocks/data";
import { createHandlers } from "../mocks/handlers";
import { MockViews } from "../mocks/views";

/** Tests run on demo day, so the holdout sealed until 20/11 stays sealed whenever CI runs. */
export const DEMO_DAY = new Date("2026-11-17T09:00:00Z");

// jsdom has no ResizeObserver; Recharts' ResponsiveContainer needs one to mount.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// jsdom's fetch needs absolute URLs; the app calls relative `/api/...`.
const origin = "http://localhost";
const realFetch = globalThis.fetch;
globalThis.fetch = (input: RequestInfo | URL, init?: RequestInit) =>
  realFetch(typeof input === "string" && input.startsWith("/") ? origin + input : input, init);

export const server = setupServer(
  ...createHandlers(new MockViews(loadMockData(), () => DEMO_DAY)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

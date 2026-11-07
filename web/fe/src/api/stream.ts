// SSE `fw_changed` (DESIGN.md §6.4): after each import the API says "something
// changed" and every screen re-reads. Only against the real API: MSW 2.6 has no
// SSE, so in mock mode the bell keeps polling every 10 s and nothing is lost.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { API_BASE } from "./client";

export const STREAM_PATH = `${API_BASE}/notifications/stream`;

export function useChangeStream(enabled: boolean) {
  const client = useQueryClient();
  useEffect(() => {
    if (!enabled || typeof EventSource === "undefined") return undefined;
    const source = new EventSource(STREAM_PATH);
    const onChange = () => void client.invalidateQueries();
    source.addEventListener("fw_changed", onChange);
    return () => {
      source.removeEventListener("fw_changed", onChange);
      source.close();
    };
  }, [enabled, client]);
}

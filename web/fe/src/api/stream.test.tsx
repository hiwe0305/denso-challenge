// The FE side of SSE: open the stream only against the real API, re-read
// everything on `fw_changed`, close it on unmount.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { STREAM_PATH, useChangeStream } from "./stream";

class FakeSource extends EventTarget {
  static last: FakeSource | null = null;
  closed = false;
  constructor(readonly url: string) {
    super();
    FakeSource.last = this;
  }
  close() {
    this.closed = true;
  }
}

function Probe({ enabled }: { enabled: boolean }) {
  useChangeStream(enabled);
  return null;
}

function mount(enabled: boolean) {
  const client = new QueryClient();
  const spy = vi.spyOn(client, "invalidateQueries");
  const view = render(<QueryClientProvider client={client}><Probe enabled={enabled} /></QueryClientProvider>);
  return { spy, view };
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeSource.last = null;
});

describe("change stream", () => {
  it("re-reads every query on fw_changed and closes on unmount", () => {
    vi.stubGlobal("EventSource", FakeSource);
    const { spy, view } = mount(true);
    expect(FakeSource.last?.url).toBe(STREAM_PATH);
    FakeSource.last?.dispatchEvent(new Event("fw_changed"));
    expect(spy).toHaveBeenCalledTimes(1);
    const source = FakeSource.last!;
    view.unmount();
    expect(source.closed).toBe(true);
  });

  it("stays off in mock mode", () => {
    vi.stubGlobal("EventSource", FakeSource);
    mount(false);
    expect(FakeSource.last).toBeNull();
  });
});

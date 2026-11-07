// M3 renders DA-31's bench result from MSW: the "on injected defects" banner
// first, code and agent side by side, the false alarm as an upper bound, and
// a rate with nothing to divide by shown as "—", never 0%.
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/renderApp";
import { fmtRate } from "./AgentQa";

describe("M3 screen", () => {
  it("says the numbers are on injected defects before anything else", async () => {
    renderApp("/agent-qa");
    const banner = await screen.findByTestId("bench-banner");
    expect(banner.textContent).toContain("không phải tỉ lệ trên lỗi tự nhiên");
    expect(banner.textContent).toContain("cận trên");
  });

  it("tells what code caught and what the agent adds", async () => {
    renderApp("/agent-qa");
    const summary = await screen.findByTestId("bench-summary");
    expect(summary.textContent).toBe("Code bắt 6/10 lỗi cấy; agent bắt thêm 2; cùng nhau 8/10.");
    const kinds = screen.getByTestId("kinds-data");
    const labelSwap = within(kinds).getAllByRole("row").find((r) => r.textContent?.includes("label_swap"));
    expect(labelSwap?.textContent).toContain("+1");
  });

  it("shows both groups, each with its clean twin and its false alarm", async () => {
    renderApp("/agent-qa");
    expect(await screen.findByTestId("bench-group-data")).toBeTruthy();
    expect(screen.getByTestId("bench-group-logs")).toBeTruthy();
    expect(screen.getByTestId("false-alarm-data").textContent).toContain("Agent: 1/10 · 10% đơn vị");
    expect(screen.getByTestId("false-alarm-data").textContent).toContain("D4 trên ep_bench_09");
  });

  it("shows a code nobody reported as a dash, not as 0%", async () => {
    renderApp("/agent-qa");
    const codes = await screen.findByTestId("codes-data");
    const d5 = within(codes).getAllByRole("row").find((r) => r.textContent?.startsWith("D5"));
    expect(d5?.textContent).toBe("D5——");
    const d2 = within(codes).getAllByRole("row").find((r) => r.textContent?.startsWith("D2"));
    expect(d2?.textContent).toContain("1/2 · 50%");
  });

  it("lists the agent's findings with the engineer's review", async () => {
    renderApp("/agent-qa");
    const findings = await screen.findByTestId("findings-data");
    expect(findings.textContent).toContain("báo sai");
    expect(findings.textContent).toContain("kỹ sư bác");
    expect(screen.getByTestId("ranking-data").textContent).toContain("4/6 · 67%");
    expect(screen.getByTestId("ranking-logs").textContent).toContain("—");
  });

  it("formats rates", () => {
    expect(fmtRate({ hit: 0, total: 0, value: null })).toBe("—");
    expect(fmtRate({ hit: 0, total: 3, value: 0 })).toBe("0/3 · 0%");
  });
});

// M8 renders from MSW: branch cost with the BR-05 data share, human minutes
// and GPU hours apart, the reversal visible, four price books, and the
// indicators that have no data behind them saying so instead of showing 0.
import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BranchComparisonRow, CostByBranch } from "../api/types";
import { renderApp } from "../test/renderApp";
import { branchCosts, perPoint } from "./Cost";

describe("M8 screen", () => {
  it("shows each branch with its data share and its own demo count", async () => {
    renderApp("/chi-phi");
    const table = await screen.findByTestId("branch-cost");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(5); // header + A, A_07, B, B_FAIL
    const a07 = rows.find((r) => r.textContent?.startsWith("A_07"));
    expect(a07?.textContent).toContain("66");
  });

  it("keeps the reversal and the entry it reverses visible", async () => {
    renderApp("/chi-phi");
    const reversal = await screen.findByTestId("ledger-led_train_A_dup_rev");
    expect(reversal.textContent).toContain("đảo led_train_A_dup");
    expect(screen.getByTestId("ledger-led_train_A_dup").textContent).toContain("đã bị đảo");
  });

  it("shows an estimate and its measurement as two entries, linked (R5)", async () => {
    renderApp("/chi-phi");
    const measured = await screen.findByTestId("ledger-led_train_A");
    expect(screen.getByTestId("ledger-led_train_A_est")).toBeTruthy();
    expect(within(measured).getByTestId("measures-led_train_A").textContent).toBe("đo led_train_A_est");
  });

  it("says which indicators have no data instead of showing 0", async () => {
    renderApp("/chi-phi");
    await waitFor(() => expect(screen.getByTestId("ind-demos").textContent).toContain("N = 20"));
    // Every measured job of the mock has its estimate row, so the error is known.
    expect(screen.getByTestId("ind-forecast").textContent).toContain("cặp ước tính → thực đo");
    expect(screen.getByTestId("ind-c-vs-b").textContent).toContain("nhánh C chưa có");
    expect(screen.getByTestId("ind-minutes").textContent).not.toContain("chưa có");
  });

  it("reprices under four price books", async () => {
    renderApp("/chi-phi");
    const sens = await screen.findByTestId("sensitivity");
    expect(within(sens).getAllByRole("row")).toHaveLength(5);
  });
});

describe("branchCosts", () => {
  const cost = {
    rows: [
      { branch: "A", task_id: "two_table", measured_usd: 20, measured_human_minutes: null, measured_gpu_hours: 10 },
      { branch: null, task_id: null, measured_usd: 200, measured_human_minutes: 240, measured_gpu_hours: 4 },
    ],
    r_demo: [{ task_id: "two_table", branch: "A", human_root_episodes: 94 }],
    data_allocation: [
      { branch: "A", task_id: "two_table", hypothesis: "HT", allocated_usd: 100, allocated_human_minutes: 180, allocated_gpu_hours: 2 },
      { branch: "C", task_id: "two_table", hypothesis: "HE", allocated_usd: 50, allocated_human_minutes: 30, allocated_gpu_hours: 0 },
    ],
  } as unknown as CostByBranch;
  const rates = [{ branch: "A", sim_success_rate: 0.6 }] as BranchComparisonRow[];

  it("adds the BR-05 share to the direct cost and leaves HE points out", () => {
    const [a, ...rest] = branchCosts(cost, rates, "two_table");
    expect(rest).toHaveLength(0);
    expect(a).toMatchObject({ branch: "A", direct_usd: 20, data_usd: 100, total_usd: 120, human_minutes: 180, gpu_hours: 12, human_demos: 94 });
    expect(perPoint(a?.total_usd ?? null, a?.rate ?? null)).toBeCloseTo(2);
  });

  it("gives no per-point figure without a rate", () => {
    expect(perPoint(100, null)).toBeNull();
    expect(perPoint(null, 0.5)).toBeNull();
  });
});

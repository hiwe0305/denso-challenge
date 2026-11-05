// M9 renders from MSW: branches with their task and cost, Level 1 and 2
// against 70%, and curves nobody ran shown as EmptyState, not as 0%.
import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvalEpisodeRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { n50, wilson } from "./HeCurve";
import { ratesByLevel } from "./Results";

describe("M9 screen", () => {
  it("compares the branches with a dev evaluation, rate beside cost", async () => {
    renderApp("/ket-qua");
    const table = await screen.findByTestId("branch-table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(5); // header + A, B, A_07, B_FAIL; HE points are not branches
    expect(table.textContent).not.toMatch(/\bC\b.*HE/);
    expect(table.textContent).toContain("69,3%");
    expect(table.textContent).toContain("24");
  });

  it("reports levels against the 70% bar", async () => {
    renderApp("/ket-qua");
    await waitFor(() => expect(screen.getByTestId("level-B-1")).toBeTruthy());
    expect(screen.getByTestId("level-B-0").textContent).toContain("không xét");
    expect(screen.getByTestId("level-B-2").textContent).toMatch(/đạt|chưa đạt/);
  });

  it("draws the HE curve per variant with N50, and E1 as not run", async () => {
    renderApp("/ket-qua");
    const curves = await screen.findByTestId("curves");
    await waitFor(() => expect(curves.textContent).toContain("E1 chưa chạy"));
    const table = await screen.findByTestId("he-table");
    expect(within(table).getAllByRole("row")).toHaveLength(4); // header + 3 variants
    expect(screen.getByTestId("n50-V_EGO").textContent).toBe("20");
    expect(screen.getByTestId("n50-V_NOEGO").textContent).toBe("40");
  });
});

describe("HE helpers", () => {
  it("gives a Wilson interval that contains the rate and stays in [0, 1]", () => {
    const ci = wilson(0.5, 89);
    expect(ci?.[0]).toBeLessThan(0.5);
    expect(ci?.[1]).toBeGreaterThan(0.5);
    expect(wilson(1, 10)?.[1]).toBeLessThanOrEqual(1);
    expect(wilson(null, 10)).toBeNull();
  });

  it("finds the smallest N that reaches 50%", () => {
    const p = (n: number, r: number | null) => ({ n_demos: n, sim_success_rate: r }) as never;
    expect(n50([p(10, 0.3), p(20, 0.52), p(40, 0.6)])).toBe(20);
    expect(n50([p(10, 0.3), p(20, null)])).toBeNull();
  });
});

describe("ratesByLevel", () => {
  const ep = (level: number, infra: string, success: boolean | null) =>
    ({ level, infra_status: infra, sim_success: success }) as EvalEpisodeRow;

  it("drops infra failures from the denominator", () => {
    const [l1] = ratesByLevel([ep(1, "ok", true), ep(1, "ok", false), ep(1, "timeout", null)]);
    expect(l1).toMatchObject({ level: 1, scored: 2, success: 1, rate: 0.5 });
  });
});

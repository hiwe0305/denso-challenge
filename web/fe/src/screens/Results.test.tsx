// M9 renders from MSW: branches with their task and cost, Level 1 and 2
// against 70%, and curves nobody ran shown as EmptyState, not as 0%.
import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvalEpisodeRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { ratesByLevel } from "./Results";

describe("M9 screen", () => {
  it("compares the branches with a dev evaluation, rate beside cost", async () => {
    renderApp("/ket-qua");
    const table = await screen.findByTestId("branch-table");
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3); // header + A + B
    expect(table.textContent).toContain("69,3%");
    expect(table.textContent).toContain("24");
  });

  it("reports levels against the 70% bar", async () => {
    renderApp("/ket-qua");
    await waitFor(() => expect(screen.getByTestId("level-B-1")).toBeTruthy());
    expect(screen.getByTestId("level-B-0").textContent).toContain("không xét");
    expect(screen.getByTestId("level-B-2").textContent).toMatch(/đạt|chưa đạt/);
  });

  it("shows curves nobody ran as not run", async () => {
    renderApp("/ket-qua");
    const curves = await screen.findByTestId("curves");
    await waitFor(() => expect(curves.textContent).toContain("E1 chưa chạy"));
    expect(curves.textContent).toContain("HE chưa có điểm nào");
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

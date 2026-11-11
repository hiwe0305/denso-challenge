// M4 renders from MSW: the lineage, the draft v2 held back by the split
// guard (two dev episodes slipped in), the frozen v1 with its hash and its
// two excluded items, and the freeze request refused while the guard fails.
import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ReleaseRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { lineage } from "./Release";

describe("M4 screen", () => {
  it("opens the draft and shows why it cannot be frozen", async () => {
    renderApp("/release");
    const guard = await screen.findByTestId("guard-split");
    expect(guard.textContent).toContain("không qua");
    expect(guard.textContent).toContain("ep_psi_064");
    expect(screen.getByTestId("freeze-blocked")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Yêu cầu đóng băng" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByTestId("export").textContent).toContain("chưa có");
  });

  it("draws v2 and A_07 under v1 in the lineage", async () => {
    renderApp("/release");
    const table = await screen.findByTestId("lineage");
    const rows = within(table).getAllByRole("row").map((r) => r.textContent ?? "");
    const v1 = rows.findIndex((t) => t.includes("rel_two_table_v1"));
    expect(rows[v1 + 1]).toContain("└");
    expect(screen.getByTestId("guard-line-rel_two_table_v2").textContent).toContain("chưa qua");
  });

  it("shows the frozen v1 with its hash, its users and the two excluded items", async () => {
    renderApp("/release");
    fireEvent.click(await screen.findByRole("button", { name: "two_table v1" }));
    const card = await screen.findByTestId("manifest-card");
    expect(card.textContent).toContain("164 giữ, 2 loại");
    expect(card.textContent).toContain("exp_A");
    expect((await screen.findByTestId("excluded")).textContent).toContain("QA quarantine");
    expect(screen.queryByRole("button", { name: "Yêu cầu đóng băng" })).toBeNull();
  });

  it("orders a forest root first and indents children", () => {
    const r = (id: string, parent: string | null) => ({ release_id: id, parent_release_id: parent }) as ReleaseRow;
    expect(lineage([r("b", "a"), r("a", null), r("c", "missing")]).map((x) => `${x.row.release_id}${x.depth}`))
      .toEqual(["a0", "b1", "c0"]);
  });
});

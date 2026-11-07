// M4 on the FE: approve on M7, see the action PENDING on M10, run one sync
// pass as ADMIN, see it APPLIED; only ADMIN and LEAD may run it; the bell.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { setRole } from "../api/role";
import type { ActionStatusRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { LATE_MINUTES, notices } from "../ui/Bell";

afterEach(() => setRole("ML_ENGINEER"));

describe("M10 and the write loop", () => {
  it("cannot run a sync pass as ML_ENGINEER", async () => {
    renderApp("/kiem-toan");
    const button = await screen.findByRole("button", { name: "Chạy đồng bộ" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("closes the loop: approve, PENDING, sync as ADMIN, APPLIED", async () => {
    setRole("ADMIN");
    renderApp("/failure-to-data");
    const approve = await screen.findByRole("button", { name: "Duyệt" });
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(approve);
    expect((await screen.findByTestId("action-status")).textContent).toContain("Đang chờ xuất");

    fireEvent.click(screen.getByRole("link", { name: /Kiểm toán/ }));
    const log = await screen.findByTestId("action-log");
    expect(log.textContent).toContain("Đang chờ xuất");

    fireEvent.click(screen.getByRole("button", { name: "Chạy đồng bộ" }));
    await waitFor(() => expect(screen.getByTestId("last-sync").textContent).toContain("áp dụng 1"));
    await waitFor(() => expect(screen.getByTestId("action-log").textContent).toContain("Lõi đã áp dụng"));
    expect(within(await screen.findByTestId("sync-runs")).getAllByRole("row")).toHaveLength(2);
  });

  it("lists the decisions loaded from the core", async () => {
    renderApp("/kiem-toan");
    const decisions = await screen.findByTestId("decisions");
    expect(decisions.textContent).toContain("FORCE_CONTINUE");
  });

  it("rings for the review waiting, the paused dataset and the open repair ticket", async () => {
    renderApp("/failure-to-data");
    await waitFor(() => expect(screen.getByTestId("bell-count").textContent).toBe("3"));
    fireEvent.click(screen.getByRole("button", { name: /thông báo/ }));
    const panel = screen.getByTestId("bell-panel");
    expect(panel.textContent).toContain("chờ duyệt");
    expect(panel.textContent).toContain("bench_kbd_teleop");
    expect(panel.textContent).toContain("Phiếu sửa mới");
  });
});

describe("notices", () => {
  const action = (status: ActionStatusRow["sync_status"], exportedMinutesAgo: number | null): ActionStatusRow => ({
    action_id: "act_1", action_kind: "RECOMMENDATION_DECISION", target_kind: "x", target_id: "y",
    sync_status: status, reason: null, reject_reason: status === "REJECTED" ? "BR-07" : null,
    created_at: "2026-11-17T08:00:00Z",
    exported_at: exportedMinutesAgo === null ? null : new Date(Date.UTC(2026, 10, 17, 9) - exportedMinutesAgo * 60_000).toISOString(),
    applied_at: null,
  });
  const at = (actions: ActionStatusRow[]) =>
    notices({ recommendations: [], datasets: [], tickets: [], actions, now: new Date("2026-11-17T09:00:00Z") });

  it("flags an action exported too long ago as late, not a fresh one", () => {
    expect(at([action("EXPORTED", LATE_MINUTES + 1)])[0]?.text).toContain("Đồng bộ trễ");
    expect(at([action("EXPORTED", 5)])).toHaveLength(0);
  });

  it("reports a rejection with its reason", () => {
    expect(at([action("REJECTED", 1)])[0]).toMatchObject({ tone: "bad" });
    expect(at([action("REJECTED", 1)])[0]?.text).toContain("BR-07");
  });
});

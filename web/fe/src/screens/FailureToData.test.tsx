// M7 renders from MSW with nothing blank: four clusters, the free-cluster
// sentence of the demo, the skipped codes with reasons, and a decision that
// ends in an action status rather than an optimistic update.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Recommendation } from "../api/types";
import { renderApp as renderAt } from "../test/renderApp";
import { liveBudget } from "./FailureToData";

const renderApp = (path = "/failure-to-data") => renderAt(path);

describe("M7 screen", () => {
  it("shows four clusters and says two of them cost no data", async () => {
    renderApp();
    const board = await screen.findByTestId("cluster-board");
    expect(within(board).getAllByTestId("diagnosis-chip")).toHaveLength(4);
    expect(screen.getByTestId("free-clusters-note").textContent).toContain("2 cụm");
    expect(await screen.findByText("thu dữ liệu và đo lại")).toBeTruthy();
    expect(await screen.findByTestId("repair-tickets")).toBeTruthy();
    expect(screen.getByText(/phải đo lại baseline/)).toBeTruthy();
  });

  it("opens an evidence card that lists the codes it could not score", async () => {
    renderApp();
    fireEvent.click(await screen.findByTestId("cluster-clu_3"));
    const card = await screen.findByTestId("evidence-card");
    const skipped = within(card).getByTestId("skipped-list");
    expect(skipped.textContent).toContain("R1");
    expect(skipped.textContent).toContain("rtc.jsonl");
    expect(within(card).getAllByText("chưa chấm được").length).toBeGreaterThan(0);
  });

  it("approves, then shows the action status instead of the result", async () => {
    renderApp();
    const approve = await screen.findByRole("button", { name: "Duyệt" });
    await waitFor(() => expect((approve as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(approve);
    const status = await screen.findByTestId("action-status");
    expect(status.textContent).toContain("Đang chờ xuất");
  });

  it("disables plain approval once a quantity is edited", async () => {
    renderApp();
    const input = await screen.findByLabelText("số lượng iv_2");
    fireEvent.change(input, { target: { value: "4" } });
    expect((screen.getByRole("button", { name: "Duyệt" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("labels screens that are not built with their milestone", () => {
    renderApp("/chi-phi");
    expect(screen.getByText(/M8 · Chi phí chưa dựng/)).toBeTruthy();
  });
});

describe("liveBudget", () => {
  it("scales the proposal with the edited quantity and drops rejected items", () => {
    const rec = {
      budget: [{ resource: "usd", cap: 100, used: 10, proposed: 60, remaining: 30 }],
      interventions: [
        { id: "a", target_quantity: 10, estimated_usd: 40, estimated_human_minutes: 0, estimated_gpu_hours: 0 },
        { id: "b", target_quantity: 2, estimated_usd: 20, estimated_human_minutes: 0, estimated_gpu_hours: 0 },
      ],
    } as unknown as Recommendation;
    const [usd] = liveBudget(rec, { a: { quantity: 5, rejected: false }, b: { quantity: 2, rejected: true } });
    expect(usd).toMatchObject({ proposed: 20, remaining: 70 });
  });
});

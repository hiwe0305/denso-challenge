// M5 renders from MSW: the experiments with their diagnosis state, the
// RunPlan card, the loss chart with the T3 mark, the twelve codes with the
// skipped one and its reason, and "not run" never shown as "no fault".
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TrainingMetricRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { diagnosisLine, lossSeries } from "./Training";

describe("M5 screen", () => {
  it("lists every experiment and says which have no diagnosis yet", async () => {
    renderApp("/huan-luyen");
    const table = await screen.findByTestId("experiments");
    expect(within(table).getAllByRole("row")).toHaveLength(17); // header + 16
    expect(screen.getByTestId("diag-line-exp_BFAIL").textContent).toBe("1 nổ · 1 bỏ qua");
    expect(screen.getByTestId("diag-line-exp_B").textContent).toBe("chưa chạy chẩn đoán");
  });

  it("opens the first experiment with telemetry: RunPlan card, loss chart, group loss", async () => {
    renderApp("/huan-luyen");
    const card = await screen.findByTestId("runplan-card");
    expect(card.textContent).toContain("rp_A");
    expect(card.textContent).toContain("branch_train");
    expect(await screen.findByTestId("loss-chart")).toBeTruthy();
    expect((await screen.findByTestId("group-loss")).textContent).toContain("hand");
    expect(screen.getByTestId("resources").textContent).toContain("chưa đo");
  });

  it("shows T3 fired on B_FAIL and T7 skipped with its reason", async () => {
    renderApp("/huan-luyen");
    fireEvent.click(await screen.findByRole("button", { name: "exp_BFAIL" }));
    const t3 = await screen.findByTestId("diag-T3");
    expect(t3.textContent).toContain("nổ");
    expect(t3.textContent).toContain("từ step 1400");
    const t7 = screen.getByTestId("diag-T7");
    expect(t7.textContent).toContain("bỏ qua");
    expect(t7.textContent).toContain("không có checkpoint cha");
    expect(screen.getByTestId("diag-O1").textContent).toContain("không thấy lỗi");
  });

  it("never paints a code green when no diagnosis ran", async () => {
    renderApp("/huan-luyen");
    fireEvent.click(await screen.findByRole("button", { name: "exp_B" }));
    expect(await screen.findByTestId("diag-not-run")).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("diag-T1").textContent).toContain("chưa chạy"));
    expect(screen.getByTestId("diag-table").textContent).not.toContain("không thấy lỗi");
    expect(screen.getByTestId("probes").textContent).toContain("so với checkpoint cha ckpt_A");
  });

  it("says when an experiment has no telemetry instead of drawing an empty chart", async () => {
    renderApp("/huan-luyen");
    fireEvent.click(await screen.findByRole("button", { name: "exp_B" }));
    expect(await screen.findByText("Chưa có telemetry")).toBeTruthy();
  });

  it("pairs train and val by step and keeps a missing val as null", () => {
    const row = (step: number, split: "train" | "val", loss: number): TrainingMetricRow => ({
      step, split, attempt: 0, epoch: 0, loss, loss_nonfinite: null, lr: 1e-4, loss_by_group: {},
      grad_norm_vlm: null, grad_norm_action: null, vram_gb: null, throughput: null, wall_time_s: 0,
    });
    expect(lossSeries([row(0, "train", 1), row(0, "val", 1.2), row(100, "train", 0.9)])).toEqual([
      { step: 0, train: 1, val: 1.2, lr: 1e-4 },
      { step: 100, train: 0.9, val: null, lr: 1e-4 },
    ]);
    expect(diagnosisLine(null)).toBe("chưa chạy chẩn đoán");
  });
});

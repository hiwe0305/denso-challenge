// M6 renders from MSW: the task's six steps, the simulator flag beside the
// scorer, infra failures out of the denominator, and a failure family nobody
// produced shown as "chưa chạy" rather than as zero faults (BR-12).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FunnelRow } from "../api/types";
import { renderApp } from "../test/renderApp";
import { funnelSteps } from "./Evaluation";

describe("M6 screen", () => {
  it("lists only unsealed evaluations of the task and opens the first", async () => {
    renderApp("/danh-gia");
    const picker = (await screen.findByTestId("evaluation-picker")) as HTMLSelectElement;
    const ids = [...picker.options].map((o) => o.value);
    expect(ids).toContain("ev_A_dev");
    expect(ids).toContain("ev_BFAIL_dev");
    expect(ids).not.toContain("ev_B_holdout");
    const headline = await screen.findByTestId("eval-headline");
    expect(headline.textContent).toContain("60,2%");
  });

  it("has exactly the six steps of the two-table task", async () => {
    renderApp("/danh-gia");
    const funnel = await screen.findByTestId("step-funnel");
    expect(within(funnel).getAllByRole("row")).toHaveLength(7); // header + 6 steps
    expect(funnel.textContent).toContain("nhả và ổn định");
  });

  it("shows a family nobody produced as not run, and skipped system codes with reasons", async () => {
    renderApp("/danh-gia");
    fireEvent.change(await screen.findByTestId("evaluation-picker"), { target: { value: "ev_B_dev" } });
    await waitFor(() => expect(screen.getByTestId("eval-headline").textContent).toContain("69,3%"));
    const train = await screen.findByTestId("family-F-TRAIN");
    expect(train.textContent).toContain("chưa chạy");
    const sys = await screen.findByTestId("family-F-SYS");
    expect(sys.textContent).toContain("R3 × 6");
    expect(within(sys).getByTestId("skipped-list").textContent).toContain("rtc.jsonl");
  });

  it("keeps infra failures out and shows the system check of a failed episode", async () => {
    renderApp("/danh-gia");
    fireEvent.change(await screen.findByTestId("evaluation-picker"), { target: { value: "ev_B_dev" } });
    expect((await screen.findByTestId("infra-excluded")).textContent).toContain("2 episode");
    const table = await screen.findByTestId("failed-episodes");
    fireEvent.click(within(table).getByText("ee_B_dev_30"));
    const detail = await screen.findByTestId("episode-detail");
    expect(detail.textContent).toContain("R3");
    expect(detail.textContent).toContain("thân trên");
  });

  it("shows R1, R2 of a sync rollout as recorded, apart from a clean verdict", async () => {
    // Decision (a) of 5/11/2026 (DESIGN.md 0.5): the latency is shown, not counted.
    renderApp("/danh-gia");
    fireEvent.change(await screen.findByTestId("evaluation-picker"), { target: { value: "ev_B_dev" } });
    const table = await screen.findByTestId("failed-episodes");
    fireEvent.click(within(table).getByText("ee_B_dev_38"));
    const detail = await screen.findByTestId("episode-detail");
    expect(within(detail).getByTestId("rollout-timing").textContent).toContain("đồng bộ");
    const recorded = within(detail).getByTestId("recorded-checks");
    expect(recorded.textContent).toContain("không quy lỗi");
    expect(recorded.textContent).toContain("R1");
    expect(recorded.textContent).toContain("R2");
    expect(within(detail).queryByTestId("skipped-list")).toBeNull();
  });

  it("says the mode was unknown and shows no recorded block when timing is null", async () => {
    renderApp("/danh-gia");
    fireEvent.change(await screen.findByTestId("evaluation-picker"), { target: { value: "ev_B_dev" } });
    const table = await screen.findByTestId("failed-episodes");
    fireEvent.click(within(table).getByText("ee_B_dev_36"));
    const detail = await screen.findByTestId("episode-detail");
    expect(within(detail).getByTestId("rollout-timing").textContent).toContain("không rõ chế độ");
    expect(within(detail).queryByTestId("recorded-checks")).toBeNull();
  });
});

describe("funnelSteps", () => {
  const row = (level: number, step: number, pass: number, fail: number, unknown = 0): FunnelRow => ({
    evaluation_id: "e", task_id: "two_table", split: "dev", eval_level: null, renderer: "mujoco",
    eval_mode: "sync", episode_level: level, step_no: step, reached_or_beyond: 10,
    step_pass: pass, step_fail: fail, step_not_attempted: 10 - pass - fail - unknown,
    step_unknown: unknown, is_sealed: false, origin: "mock",
  });

  it("splits absolute from conditional and keeps unknown out of both", () => {
    const steps = funnelSteps([row(0, 1, 8, 1, 1), row(0, 2, 4, 4)], null);
    expect(steps[0]).toMatchObject({ pass: 8, fail: 1, unknown: 1, absolute: 0.8 });
    expect(steps[0]?.conditional).toBeCloseTo(8 / 9);
    expect(steps[1]).toMatchObject({ absolute: 0.4, conditional: 0.5 });
  });

  it("filters by level", () => {
    const steps = funnelSteps([row(0, 1, 8, 2), row(1, 1, 2, 8)], [1]);
    expect(steps[0]?.absolute).toBe(0.2);
  });
});

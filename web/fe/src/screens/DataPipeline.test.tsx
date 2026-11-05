// M2 renders from MSW: five datasets, a stepper with code and agent labels
// side by side, the retried stage, QA-not-run kept apart from pass, and the
// raw-egocentric lock (BR-09).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/renderApp";

const open = async (code: string) => {
  const list = await screen.findByTestId("dataset-list");
  fireEvent.click(within(list).getByText(code));
};

describe("M2 screen", () => {
  it("lists five datasets and flags the seeded copy", async () => {
    renderApp("/du-lieu");
    const list = await screen.findByTestId("dataset-list");
    expect(within(list).getAllByRole("row")).toHaveLength(6);
    expect(within(list).getByText("có lỗi cấy")).toBeTruthy();
  });

  it("shows the code verdict and the agent verdict on the QA stage", async () => {
    renderApp("/du-lieu");
    const qa = await screen.findByTestId("stage-4");
    await waitFor(() => expect(qa.textContent).toContain("kỹ sư cho qua"));
    expect(qa.textContent).toContain("code: flag");
    expect(qa.textContent).toContain("agent: WARNING");
  });

  it("shows the retry of stage 4 and keeps the old attempt", async () => {
    renderApp("/du-lieu");
    await open("ds_kbd_teleop");
    await waitFor(() => expect(screen.getByTestId("stage-4").textContent).toContain("lần 2"));
    const history = screen.getByTestId("attempt-history");
    expect(history.textContent).toContain("hỏng");
  });

  it("stops the seeded copy at stage 4 for review", async () => {
    renderApp("/du-lieu");
    await open("bench_kbd_teleop");
    await waitFor(() => expect(screen.getByTestId("stage-4").textContent).toContain("dừng chờ duyệt"));
    expect(screen.getByTestId("stage-5").textContent).toContain("chờ");
  });

  it("locks splitting while egocentric episodes are raw, and counts them as not scored", async () => {
    renderApp("/du-lieu");
    await open("ds_egodex");
    const report = await screen.findByTestId("dataset-report");
    await waitFor(() => expect(report.textContent).toContain("10 episode egocentric còn raw"));
    const list = await screen.findByTestId("episode-list");
    expect(within(list).getAllByText("chưa chấm")).toHaveLength(10);
  });
});

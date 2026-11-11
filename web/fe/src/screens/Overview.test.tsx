// M1 renders from MSW: six cards in demo order, each with an honest status
// (part 1 has no data in the mock and says so), the summary line, the strip.
import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/renderApp";
import { summaryLine } from "./Overview";

describe("M1 screen", () => {
  it("shows the six parts of the 17/11 demo, each linking to its screen", async () => {
    renderApp("/tong-quan");
    for (const no of [1, 2, 3, 4, 5, 6]) expect(await screen.findByTestId(`part-${no}`)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Mở Agent QA/QC →" }).getAttribute("href")).toBe("/agent-qa");
  });

  it("says part 1 has nothing behind it instead of showing a zero", async () => {
    renderApp("/tong-quan");
    await waitFor(() => expect(screen.getByTestId("status-1").textContent).toContain("chưa có"));
    expect(screen.getByTestId("part-1").textContent).toContain("7/5/6 chưa có");
  });

  it("carries the key number of each part from its own screen's endpoint", async () => {
    renderApp("/tong-quan");
    expect((await screen.findByTestId("qa-line")).textContent).toContain("code bắt 6/10, agent thêm 2");
    expect((await screen.findByTestId("he-line")).textContent).toContain("V_EGO: N₅₀ = 20");
    const fd = await screen.findByTestId("fd-line");
    await waitFor(() => expect(fd.textContent).toContain("4 cụm lỗi"));
    expect(fd.textContent).toContain("2 cụm không tốn ngân sách dữ liệu");
    expect(screen.getByTestId("sealed").textContent).toContain("chỉ ADMIN thấy");
    await waitFor(() => expect(screen.getByTestId("summary").textContent).toBe("5/6 phần có số đo · 1 chưa có"));
  });

  it("summarises statuses", () => {
    expect(summaryLine(["ok", "partial", "none", "ok"])).toBe("2/4 phần có số đo · 1 một phần · 1 chưa có");
  });
});

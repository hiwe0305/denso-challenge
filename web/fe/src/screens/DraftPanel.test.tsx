// The M5 draft form on MSW: save a draft, see BR-01 refuse a submit with no
// release, then submit one with a frozen release and see the action wait for
// the core.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/renderApp";

async function saveDraft(withRelease: boolean) {
  renderApp("/huan-luyen");
  const form = await screen.findByRole("form", { name: "bản nháp" });
  if (withRelease) {
    const box = await within(form).findByRole("checkbox", { name: "rel_two_table_v1" });
    fireEvent.click(box);
  }
  fireEvent.click(within(form).getByRole("button", { name: "Lưu nháp" }));
  return screen.findByTestId("drafts");
}

describe("M5 draft form", () => {
  it("saves a draft and refuses to submit it without a release (BR-01)", async () => {
    const list = await saveDraft(false);
    expect(list.textContent).toContain("release: chưa chọn");
    const submit = within(list).getAllByRole("button", { name: /^Nộp / })[0]!;
    fireEvent.click(submit);
    expect((await screen.findByRole("alert")).textContent).toContain("BR-01: chưa chọn release nào");
  });

  it("submits a draft with a frozen release and waits for the core", async () => {
    const list = await saveDraft(true);
    await waitFor(() => expect(list.textContent).toContain("release: rel_two_table_v1"));
    const item = within(list).getAllByRole("listitem").find((li) => li.textContent?.includes("rel_two_table_v1"))!;
    fireEvent.click(within(item).getByRole("button", { name: /^Nộp / }));
    expect((await within(item).findByTestId("action-status")).textContent).toContain("Đang chờ xuất");
  });

  it("only offers the branches of the chosen task", async () => {
    renderApp("/huan-luyen");
    const form = await screen.findByRole("form", { name: "bản nháp" });
    fireEvent.change(within(form).getByLabelText("task"), { target: { value: "tray" } });
    const options = within(within(form).getByLabelText("nhánh")).getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("TRAY_C");
    expect(options).not.toContain("B_PLUS");
  });
});

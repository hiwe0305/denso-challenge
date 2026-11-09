// The chat pane, read-only minimum: it knows the open screen and the selected
// record, keeps one session per context, shows what a turn loaded, and offers
// no action button under an answer.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/renderApp";

async function openChat() {
  fireEvent.click(await screen.findByRole("button", { name: "mở ngăn chat" }));
  return screen.findByRole("complementary", { name: "ngăn chat" });
}

async function ask(pane: HTMLElement, question: string) {
  fireEvent.change(within(pane).getByRole("textbox", { name: "câu hỏi" }), { target: { value: question } });
  fireEvent.click(within(pane).getByRole("button", { name: "Hỏi" }));
  await within(pane).findByText(question);
}

describe("chat pane", () => {
  it("asks about the selected evaluation and shows what the turn loaded", async () => {
    renderApp("/danh-gia");
    const pane = await openChat();
    await waitFor(() => expect(within(pane).getByTestId("chat-context").textContent).toMatch(/^M6 · lượt eval ev_/));
    const evaluation = within(pane).getByTestId("chat-context").textContent!.split("lượt eval ")[1]!;

    await ask(pane, "Lượt này hỏng ở bước nào?");
    expect(await within(pane).findByText(new RegExp(`API thật sẽ đọc M6: evaluation ${evaluation}`))).toBeTruthy();
    const provenance = within(pane).getByTestId("chat-provenance");
    expect(provenance.textContent).toContain("msw-mock");
    expect(provenance.textContent).toContain("nạp 1 bản ghi");
    expect(provenance.textContent).toContain("prompt");
  });

  it("offers no action under an answer", async () => {
    renderApp("/chi-phi");
    const pane = await openChat();
    await ask(pane, "Nhánh nào rẻ nhất?");
    await within(pane).findByTestId("chat-provenance");
    const buttons = within(pane).getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? b.textContent);
    // Close, ask, and the hash badge: nothing that approves, submits or runs.
    expect(buttons.filter((b) => b !== "đóng ngăn chat" && b !== "Hỏi")).toHaveLength(1);
    expect(within(pane).getByTestId("chat-context").textContent).toBe("M8");
  });

  it("adds the open cluster to the context on M7", async () => {
    renderApp("/failure-to-data");
    const pane = await openChat();
    await waitFor(() => expect(within(pane).getByTestId("chat-context").textContent).toContain("đề xuất rec_round1"));
    expect(within(pane).getByTestId("chat-context").textContent).not.toContain("cụm");
    fireEvent.click(await screen.findByTestId("cluster-clu_3"));
    await waitFor(() => expect(within(pane).getByTestId("chat-context").textContent).toContain("cụm clu_3"));
  });

  it("starts a new conversation when the context changes", async () => {
    renderApp("/chi-phi");
    const pane = await openChat();
    await ask(pane, "Câu trên M8");
    fireEvent.click(screen.getByRole("link", { name: /Kết quả/ }));
    await waitFor(() => expect(within(pane).getByTestId("chat-context").textContent).toBe("M9"));
    expect(within(pane).queryByText("Câu trên M8")).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: /Chi phí/ }));
    expect(await within(pane).findByText("Câu trên M8")).toBeTruthy();
  });
});

// The chat pane, read-only minimum (DESIGN.md §5.4, §6.2). It asks about the
// screen that is open and the record selected on it; the API loads that record
// as `agent_ro` (no group S, no sealed eval, nothing that is not public) and
// keeps only ids and the prompt's sha256. It proposes no action: there is no
// button under an answer, by design of the minimum.
import { useState } from "react";
import { apiWrite } from "../api/client";
import { useCurrentFocus } from "../api/focus";
import type { ChatFocus, ChatMessage, ChatSession, ChatTurn } from "../api/types";
import { ErrorBox, HashBadge } from "./components";

const FOCUS_LABEL: Record<keyof ChatFocus, string> = {
  dataset_id: "lô",
  experiment_id: "thí nghiệm",
  evaluation_id: "lượt eval",
  recommendation_id: "đề xuất",
  cluster_id: "cụm",
};

function contextLine(screen: string, focus: ChatFocus): string {
  const parts = (Object.keys(FOCUS_LABEL) as Array<keyof ChatFocus>)
    .filter((k) => focus[k])
    .map((k) => `${FOCUS_LABEL[k]} ${focus[k]}`);
  return [screen, ...parts].join(" · ");
}

function Provenance({ message }: { message: ChatMessage }) {
  const s = message.context_snapshot;
  const loaded = s.loaded?.length ?? 0;
  const withheld = s.withheld?.length ?? 0;
  const missing = s.missing?.length ?? 0;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-slate-500" data-testid="chat-provenance">
      <span>{message.model}</span>
      <span title={(s.loaded ?? []).map((x) => `${x.kind} ${x.id ?? ""}`).join("\n")}>nạp {loaded} bản ghi</span>
      {withheld ? <span className="text-amber-700" title="data_class không phải public (R6)">giữ lại {withheld}</span> : null}
      {missing ? (
        <span className="text-amber-700" title={(s.missing ?? []).map((x) => `${x.kind} ${x.id ?? ""}`).join("\n")}>
          không thấy {missing}
        </span>
      ) : null}
      {s.truncated ? <span className="text-amber-700">ngữ cảnh bị cắt</span> : null}
      {message.prompt_sha256 ? (
        <span>
          prompt <HashBadge value={message.prompt_sha256} />
        </span>
      ) : null}
    </div>
  );
}

export function ChatPane({ screen, onClose }: { screen: string; onClose: () => void }) {
  const focus = useCurrentFocus();
  const key = `${screen} ${JSON.stringify(focus, Object.keys(focus).sort())}`;
  const [sessions, setSessions] = useState<Record<string, string>>({});
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  // One session per context (§5.4 point 1: the session's context columns are fixed).
  const sessionId = sessions[key] ?? null;
  const shown = sessionId ? messages[sessionId] ?? [] : [];

  async function send() {
    const content = draft.trim();
    if (!content || pending) return;
    setPending(true);
    setError(null);
    try {
      let id = sessionId;
      if (!id) {
        const created = await apiWrite<ChatSession>("/chat/sessions", { screen, focus });
        id = created.id;
        const newId = id;
        setSessions((prev) => ({ ...prev, [key]: newId }));
      }
      const turn = await apiWrite<ChatTurn>(`/chat/sessions/${id}/messages`, { content });
      const sid = id;
      setMessages((prev) => ({ ...prev, [sid]: [...(prev[sid] ?? []), turn.user, turn.assistant] }));
      setDraft("");
    } catch (e) {
      setError(e);
    } finally {
      setPending(false);
    }
  }

  return (
    <aside aria-label="ngăn chat"
      className="fixed bottom-0 right-0 top-[49px] z-20 flex w-full max-w-sm flex-col border-l border-slate-200 bg-white shadow-lg">
      <header className="flex items-start justify-between gap-2 border-b border-slate-200 px-3 py-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold">
            Hỏi agent <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-normal text-slate-600">chỉ đọc</span>
          </p>
          <p className="truncate text-xs text-slate-500" data-testid="chat-context" title="Màn hình và bản ghi agent sẽ đọc">
            {contextLine(screen, focus)}
          </p>
        </div>
        <button type="button" className="text-slate-500 hover:text-slate-800" aria-label="đóng ngăn chat" onClick={onClose}>
          ✕
        </button>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-2 text-sm" data-testid="chat-log">
        {shown.length === 0 ? (
          <p className="text-xs text-slate-500">
            Hỏi về màn hình và bản ghi đang chọn. Agent không duyệt, không nộp, không chạy gì; không đọc bản sao có lỗi
            cấy, lượt eval đang niêm phong, hay dữ liệu không public.
          </p>
        ) : null}
        {shown.map((m) => (
          <div key={m.id} className={m.role === "user" ? "ml-6 rounded bg-slate-900 px-2 py-1.5 text-white" : "mr-2"}>
            <p className="whitespace-pre-wrap">{m.content}</p>
            {m.role === "assistant" ? <Provenance message={m} /> : null}
          </div>
        ))}
        {pending ? <p className="text-xs text-slate-400">Đang hỏi model…</p> : null}
        {error ? <ErrorBox error={error} /> : null}
      </div>
      <form className="flex gap-2 border-t border-slate-200 p-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}>
        <textarea aria-label="câu hỏi" rows={2} value={draft} maxLength={4000}
          className="min-w-0 flex-1 resize-none rounded border border-slate-300 px-2 py-1 text-sm"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }} />
        <button type="submit" disabled={pending || !draft.trim()}
          className="self-end rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-40">
          Hỏi
        </button>
      </form>
    </aside>
  );
}

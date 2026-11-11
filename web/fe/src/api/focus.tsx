// Which record the open screen has selected, for the chat pane (DESIGN.md §6.2:
// "Ngăn chat bên phải tự nhận màn hình đang mở và bản ghi đang chọn").
// Screens keep their selection in local state; each one reports it with
// `useFocus`, and the pane reads the merged result with `useCurrentFocus`.
import { createContext, useContext, useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import type { ChatFocus } from "./types";

const FocusValue = createContext<ChatFocus>({});
// The setter lives in its own context: it never changes, so a screen's effect
// does not re-run every time another screen's focus does.
const FocusSetter = createContext<Dispatch<SetStateAction<ChatFocus>> | null>(null);

export function FocusProvider({ children }: { children: ReactNode }) {
  const [focus, setFocus] = useState<ChatFocus>({});
  return (
    <FocusSetter.Provider value={setFocus}>
      <FocusValue.Provider value={focus}>{children}</FocusValue.Provider>
    </FocusSetter.Provider>
  );
}

/**
 * Report the selection of a screen. Keys merge, so a screen and a panel inside
 * it (M7's recommendation and its open cluster) can each report their own;
 * the keys are removed when the component unmounts.
 */
export function useFocus(focus: ChatFocus) {
  const setFocus = useContext(FocusSetter);
  const key = JSON.stringify(focus);
  useEffect(() => {
    if (!setFocus) return;
    const value = JSON.parse(key) as ChatFocus;
    setFocus((prev) => ({ ...prev, ...value }));
    return () =>
      setFocus((prev) => {
        const next = { ...prev };
        for (const k of Object.keys(value)) delete next[k as keyof ChatFocus];
        return next;
      });
  }, [key, setFocus]);
}

/** The merged selection, without empty keys. */
export function useCurrentFocus(): ChatFocus {
  const focus = useContext(FocusValue);
  return Object.fromEntries(Object.entries(focus).filter(([, v]) => v)) as ChatFocus;
}

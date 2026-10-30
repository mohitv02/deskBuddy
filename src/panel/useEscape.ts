import { useEffect, useRef } from "react";

/**
 * Close a sheet on Escape no matter where focus is (it can leave the sheet,
 * e.g. when a button disables itself while busy). Runs in the capture phase
 * and stops the event so the panel's own "Esc hides the panel" doesn't fire.
 */
export function useEscape(onEscape: () => void, enabled = true) {
  const handler = useRef(onEscape);
  handler.current = onEscape;
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      e.preventDefault();
      handler.current();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [enabled]);
}

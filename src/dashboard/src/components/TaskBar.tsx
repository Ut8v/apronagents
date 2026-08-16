import { useEffect, useRef, useState } from "react";
import { api, PlanningState } from "../api/client";

export default function TaskBar({ planning }: { planning?: PlanningState }) {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [echo, setEcho] = useState<string | null>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const wasActive = useRef(false);

  const active = planning?.active ?? false;
  const notes = active ? planning?.notes ?? [] : [];

  // Clear the echoed prompt once planning finishes — the issues appearing
  // on the board take over as the feedback from there.
  useEffect(() => {
    if (wasActive.current && !active) setEcho(null);
    wasActive.current = active;
  }, [active]);

  const submit = async () => {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      await api.submitTask(prompt.trim());
      setEcho(prompt.trim());
      setPrompt("");
      if (areaRef.current) areaRef.current.style.height = "auto";
    } finally {
      setBusy(false);
    }
  };

  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setPrompt(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 176) + "px";
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div
      className="rounded-xl border border-[oklch(0.29_0.014_255)] p-3"
      style={{
        background: "linear-gradient(oklch(0.205 0.012 255), oklch(0.185 0.011 255))",
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="h-[5px] w-[5px] rounded-full bg-[oklch(0.75_0.1_205)]" />
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[oklch(0.6_0.012_255)]">
          dispatch
        </span>
        <button
          onClick={submit}
          disabled={busy || !prompt.trim()}
          className="ml-auto rounded-lg border border-[oklch(0.6_0.09_205/0.5)] bg-[oklch(0.3_0.05_205)] px-4 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[oklch(0.92_0.05_205)] transition-colors duration-[140ms] hover:bg-[oklch(0.38_0.07_205)] disabled:opacity-50"
        >
          start
        </button>
      </div>
      <div className="flex items-start gap-2.5 rounded-lg border border-[oklch(0.3_0.014_255)] bg-rail px-3 py-2.5 font-mono transition-colors focus-within:border-[oklch(0.6_0.09_205)] focus-within:shadow-[0_0_0_3px_oklch(0.6_0.09_205/0.15)]">
        <span className="select-none pt-px text-[13px] text-[oklch(0.75_0.1_205)]">$</span>
        <textarea
          ref={areaRef}
          value={prompt}
          onChange={onChange}
          onKeyDown={onKeyDown}
          rows={2}
          spellCheck={false}
          placeholder={'describe the task to split across agents…'}
          className="max-h-44 min-h-[44px] flex-1 resize-none bg-transparent text-[12.5px] leading-[1.7] text-[oklch(0.9_0.008_255)] outline-none placeholder:text-[oklch(0.5_0.012_255)]"
        />
      </div>
      {(echo !== null || active) && (
        <div className="mt-2 rounded-lg border border-[oklch(0.3_0.014_255)] bg-rail px-3 py-2 font-mono text-[11px] leading-[1.9]">
          {echo && (
            <div className="truncate text-[oklch(0.62_0.012_255)]">
              <span className="text-[oklch(0.75_0.1_205)]">$</span> {echo}
            </div>
          )}
          {notes.map((note, index) => (
            <div key={index} className="truncate text-[oklch(0.68_0.012_255)]">
              <span className="text-[oklch(0.6_0.05_205)]">▸</span> {note}
            </div>
          ))}
          <div className="animate-pulse text-[oklch(0.78_0.05_205)]">
            <span>▸</span> planner is thinking…
            <span className="ml-1 inline-block">▍</span>
          </div>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 font-mono text-[10px] text-[oklch(0.5_0.012_255)]">
        <span>enter dispatches · shift+enter for a new line</span>
        <span className="ml-auto">
          prefer your terminal? <span className="text-[oklch(0.66_0.05_205)]">apron task "…"</span>
        </span>
      </div>
    </div>
  );
}

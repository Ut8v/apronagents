import { useState } from "react";
import { api } from "../api/client";

export default function TaskBar() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      await api.submitTask(prompt.trim());
      setPrompt("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="flex items-stretch gap-2.5 rounded-xl border border-[oklch(0.29_0.014_255)] p-3"
      style={{
        background: "linear-gradient(oklch(0.205 0.012 255), oklch(0.185 0.011 255))",
      }}
    >
      <span className="flex items-center gap-2 pl-1 pr-1.5">
        <span className="h-[5px] w-[5px] rounded-full bg-[oklch(0.75_0.1_205)]" />
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[oklch(0.6_0.012_255)]">
          dispatch
        </span>
      </span>
      <input
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Describe the task to split across agents…"
        className="h-[38px] flex-1 rounded-lg border border-[oklch(0.3_0.014_255)] bg-rail px-3 text-[13px] outline-none transition-colors focus:border-[oklch(0.6_0.09_205)] focus:shadow-[0_0_0_3px_oklch(0.6_0.09_205/0.15)]"
      />
      <button
        type="submit"
        disabled={busy || !prompt.trim()}
        className="h-[38px] rounded-lg border border-[oklch(0.6_0.09_205/0.5)] bg-[oklch(0.3_0.05_205)] px-5 font-mono text-[11px] uppercase tracking-[0.12em] text-[oklch(0.92_0.05_205)] transition-colors duration-[140ms] hover:bg-[oklch(0.38_0.07_205)] disabled:opacity-50"
      >
        start
      </button>
    </form>
  );
}

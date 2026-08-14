import { useState } from "react";
import { api } from "../api/client";

export default function TaskBar() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      await api.submitTask(prompt.trim());
      setPrompt("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex gap-2">
      <input
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="Describe the task to split across agents…"
        className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
      />
      <button
        onClick={submit}
        disabled={busy || !prompt.trim()}
        className="rounded bg-sky-700 px-4 py-2 text-sm font-medium hover:bg-sky-600 disabled:opacity-50"
      >
        Start
      </button>
    </div>
  );
}

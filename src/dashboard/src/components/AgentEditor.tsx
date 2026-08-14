import { useEffect, useState } from "react";
import { AgentInfo } from "../api/client";

interface Props {
  agent: AgentInfo;
  onSave: (
    name: string,
    edited: Omit<AgentInfo, "name" | "source" | "overridden">,
  ) => Promise<void>;
}

export default function AgentEditor({ agent, onSave }: Props) {
  const [description, setDescription] = useState(agent.description);
  const [model, setModel] = useState(agent.model ?? "");
  const [tools, setTools] = useState(agent.tools.join(", "));
  const [prompt, setPrompt] = useState(agent.prompt);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    setDescription(agent.description);
    setModel(agent.model ?? "");
    setTools(agent.tools.join(", "));
    setPrompt(agent.prompt);
    setStatus("idle");
  }, [agent]);

  const save = async () => {
    setStatus("saving");
    try {
      await onSave(agent.name, {
        description,
        role: agent.role,
        model: model.trim() || null,
        tools: tools.split(",").map((t) => t.trim()).filter(Boolean),
        prompt,
      });
      setStatus("saved");
    } catch {
      setStatus("error");
    }
  };

  const field = "w-full rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm";
  return (
    <div className="space-y-3">
      <label className="block text-sm">
        <span className="text-slate-400">Description</span>
        <input className={field} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="text-slate-400">Model</span>
          <input className={field} value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="text-slate-400">Tools (comma-separated)</span>
          <input className={field} value={tools} onChange={(e) => setTools(e.target.value)} />
        </label>
      </div>
      <label className="block text-sm">
        <span className="text-slate-400">Prompt</span>
        <textarea
          className={`${field} min-h-56 font-mono text-xs leading-5`}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </label>
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={status === "saving" || !prompt.trim()}
          className="rounded bg-sky-700 px-3 py-1.5 text-sm font-medium hover:bg-sky-600 disabled:opacity-50"
        >
          Save to .apron overlay
        </button>
        {status === "saved" && (
          <span className="text-sm text-emerald-400">saved — applies to the next issue</span>
        )}
        {status === "error" && <span className="text-sm text-red-400">save failed</span>}
      </div>
    </div>
  );
}

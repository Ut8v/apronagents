import { useEffect, useState } from "react";
import { AgentInfo } from "../api/client";
import { SourceBadge } from "./Badges";

interface Props {
  agent: AgentInfo;
  onSave: (
    name: string,
    edited: Omit<AgentInfo, "name" | "source" | "overridden">,
  ) => Promise<void>;
}

function resolvedPath(agent: AgentInfo): string {
  switch (agent.source) {
    case "project": return `.apron/agents/${agent.name}.md`;
    case "user": return `~/.apron/agents/${agent.name}.md`;
    case "claude-user": return `~/.claude/agents/${agent.name}.md`;
    case "claude-project": return `.claude/agents/${agent.name}.md`;
    default: return "shipped default";
  }
}

const FIELD = "h-9 w-full rounded-lg border border-[oklch(0.29_0.014_255)] bg-[oklch(0.185_0.011_255)] px-[11px] outline-none transition-colors focus:border-[oklch(0.6_0.09_205)]";
const LABEL = "mb-1.5 block font-mono text-[10px] uppercase tracking-[0.14em] text-[oklch(0.6_0.012_255)]";

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

  return (
    <div className="flex h-full flex-col gap-[18px] p-6">
      <div className="flex items-center gap-3">
        <h2 className="text-xl font-[650] tracking-[-0.015em] text-ink">{agent.name}</h2>
        <SourceBadge source={agent.source} />
        <span className="ml-auto font-mono text-[11px] text-[oklch(0.52_0.012_255)]">
          {resolvedPath(agent)}
        </span>
      </div>
      <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
        <label className="block">
          <span className={LABEL}>description</span>
          <input
            className={`${FIELD} text-[13px]`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <label className="block">
          <span className={LABEL}>model</span>
          <input
            className={`${FIELD} font-mono text-[12.5px]`}
            value={model}
            placeholder="inherit from session"
            onChange={(e) => setModel(e.target.value)}
          />
        </label>
        <label className="block">
          <span className={LABEL}>tools</span>
          <input
            className={`${FIELD} font-mono text-[12.5px]`}
            value={tools}
            onChange={(e) => setTools(e.target.value)}
          />
        </label>
      </div>
      <label className="flex min-h-0 flex-1 flex-col">
        <span className={LABEL}>prompt</span>
        <textarea
          spellCheck={false}
          className="min-h-[300px] flex-1 resize-y rounded-[10px] border border-[oklch(0.29_0.014_255)] bg-rail p-3.5 font-mono text-[12.5px] leading-[1.7] outline-none transition-colors focus:border-[oklch(0.6_0.09_205)]"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </label>
      <div className="flex items-center gap-3.5">
        <button
          onClick={save}
          disabled={status === "saving" || !prompt.trim()}
          className="h-9 rounded-lg border border-[oklch(0.6_0.09_205/0.5)] bg-[oklch(0.3_0.05_205)] px-[18px] font-mono text-[11px] uppercase tracking-[0.12em] text-[oklch(0.92_0.05_205)] transition-colors duration-[140ms] hover:bg-[oklch(0.38_0.07_205)] disabled:opacity-50"
        >
          save to .apron overlay
        </button>
        {status === "saved" && (
          <span className="flex items-center gap-2 font-mono text-[11px] text-[oklch(0.76_0.1_152)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[oklch(0.7_0.11_152)]" />
            saved — applies to the next issue
          </span>
        )}
        {status === "error" && (
          <span className="flex items-center gap-2 font-mono text-[11px] text-[oklch(0.72_0.13_25)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[oklch(0.65_0.16_25)]" />
            save failed
          </span>
        )}
      </div>
    </div>
  );
}

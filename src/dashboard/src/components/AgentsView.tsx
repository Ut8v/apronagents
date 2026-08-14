import { useState } from "react";
import { useAgents } from "../hooks/useAgents";
import { SourceBadge } from "./Badges";
import AgentEditor from "./AgentEditor";

export default function AgentsView() {
  const { agents, error, save } = useAgents();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const selected = agents.find((a) => a.name === selectedName) ?? agents[0];

  if (error) {
    return (
      <p className="p-6 font-mono text-[12px] text-[oklch(0.7_0.13_25)]">
        failed to load agents: {error}
      </p>
    );
  }

  return (
    <div className="grid min-h-[calc(100vh-56px)] gap-px bg-line lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="flex flex-col gap-2 bg-rail px-3 py-4">
        <span className="px-1 pb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.6_0.012_255)]">
          resolved agents
        </span>
        {agents.map((agent) => {
          const isSelected = selected?.name === agent.name;
          return (
            <button
              key={agent.name}
              onClick={() => setSelectedName(agent.name)}
              className={`rounded-[9px] border px-3 py-[11px] text-left transition-colors ${
                isSelected
                  ? "border-[oklch(0.36_0.04_205)] bg-[oklch(0.23_0.02_205)]"
                  : "border-[oklch(0.24_0.012_255)] bg-[oklch(0.185_0.011_255)]"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="truncate text-[13px] font-semibold text-[oklch(0.92_0.008_255)]">
                  {agent.name}
                </span>
                <span className="ml-auto">
                  <SourceBadge source={agent.source} />
                </span>
              </div>
              <div className="mt-[5px] flex items-center gap-2">
                <span className="text-[11.5px] text-[oklch(0.6_0.012_255)]">{agent.role}</span>
                {agent.overridden && (
                  <span className="rounded-[4px] border border-[oklch(0.78_0.11_78/0.38)] bg-[oklch(0.78_0.11_78/0.14)] px-1.5 py-[1px] font-mono text-[9.5px] uppercase text-[oklch(0.84_0.1_78)]">
                    overridden
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <div className="bg-base">
        {selected && <AgentEditor agent={selected} onSave={save} />}
      </div>
    </div>
  );
}

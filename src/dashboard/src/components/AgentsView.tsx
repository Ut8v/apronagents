import { useState } from "react";
import { useAgents } from "../hooks/useAgents";
import { SourceBadge } from "./Badges";
import AgentEditor from "./AgentEditor";

export default function AgentsView() {
  const { agents, error, save } = useAgents();
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const selected = agents.find((a) => a.name === selectedName) ?? agents[0];

  if (error) {
    return <p className="text-sm text-red-400">failed to load agents: {error}</p>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
      <ul className="space-y-1">
        {agents.map((agent) => (
          <li key={agent.name}>
            <button
              onClick={() => setSelectedName(agent.name)}
              className={`w-full rounded px-3 py-2 text-left text-sm hover:bg-slate-800 ${
                selected?.name === agent.name ? "bg-slate-800" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-medium">{agent.name}</span>
                <SourceBadge source={agent.source} />
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-500">
                <span>{agent.role}</span>
                {agent.overridden && (
                  <span className="rounded bg-emerald-950 px-1.5 text-emerald-400">
                    overridden
                  </span>
                )}
              </div>
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="font-medium">{selected.name}</h3>
            <SourceBadge source={selected.source} />
          </div>
          <AgentEditor agent={selected} onSave={save} />
        </div>
      )}
    </div>
  );
}

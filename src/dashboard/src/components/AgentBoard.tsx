import { AppState, Issue, WorkerInfo } from "../api/client";
import { SourceBadge, StateChip } from "./Badges";

const ACTIVE_STATES = new Set(["claimed", "in_progress", "in_review", "merging"]);

function currentIssue(worker: WorkerInfo, issues: Issue[]): Issue | undefined {
  return issues.find(
    (issue) => issue.worker_id === worker.id && ACTIVE_STATES.has(issue.state),
  );
}

function WorkerCard({ worker, issues }: { worker: WorkerInfo; issues: Issue[] }) {
  const issue = currentIssue(worker, issues);
  const busy = !worker.idle;
  return (
    <div
      className={`rounded-[11px] border px-3.5 py-3 transition-colors duration-200 ${
        busy ? "border-line-strong" : "border-[oklch(0.26_0.013_255)]"
      }`}
      style={{
        background: busy
          ? "linear-gradient(oklch(0.215 0.013 255), oklch(0.195 0.011 255))"
          : "oklch(0.175 0.01 255)",
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-[7px] w-[7px] rounded-full ${busy ? "animate-pulse-dot" : ""}`}
          style={{
            background: busy ? "oklch(0.75 0.1 205)" : "oklch(0.38 0.012 255)",
            boxShadow: busy ? "0 0 10px oklch(0.75 0.1 205 / 0.6)" : "none",
          }}
        />
        <span className="font-mono text-xs tracking-[0.04em] text-[oklch(0.9_0.008_255)]">
          {worker.id}
        </span>
        <span className="ml-auto">
          <SourceBadge source={worker.agent_source} />
        </span>
      </div>
      <div className="mt-2.5 flex items-baseline gap-2">
        <span className="text-[13px] font-semibold">{worker.agent_name}</span>
        <span className="text-[11px] text-dim">worker</span>
      </div>
      <div className="mt-2.5 flex min-h-16 items-center border-t border-[oklch(0.25_0.012_255)] pt-2.5">
        {issue ? (
          <div className="min-w-0">
            <StateChip state={issue.state} />
            <div className="mt-1.5 truncate text-[12.5px] text-[oklch(0.88_0.008_255)]">
              {issue.title}
            </div>
            {issue.branch && (
              <div className="mt-0.5 truncate font-mono text-[11px] text-[oklch(0.6_0.03_205)]">
                {issue.branch}
              </div>
            )}
            {issue.state === "in_progress" && issue.last_activity && (
              <div
                className="mt-1.5 truncate border-t border-[oklch(0.25_0.012_255)] pt-1.5 font-mono text-[10.5px] text-[oklch(0.74_0.06_205)]"
                title={issue.last_activity}
              >
                ▸ {issue.last_activity}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2.5">
            <span className="h-px w-3.5 bg-[oklch(0.4_0.012_255)]" />
            <span className="font-mono text-[11px] tracking-[0.06em] text-[oklch(0.5_0.012_255)]">
              waiting for an issue
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AgentBoard({ state }: { state: AppState }) {
  const working = state.workers.filter((w) => !w.idle).length;
  return (
    <section>
      <div className="mb-2.5 flex items-center gap-3">
        <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.66_0.012_255)]">
          apron — {state.workers.length} agents
        </span>
        <span className="h-px flex-1 bg-[oklch(0.26_0.013_255)]" />
        <span className="font-mono text-[10px] text-[oklch(0.55_0.012_255)]">
          {working} working
        </span>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(272px, 1fr))" }}>
        {state.workers.map((worker) => (
          <WorkerCard key={worker.id} worker={worker} issues={state.issues} />
        ))}
      </div>
    </section>
  );
}

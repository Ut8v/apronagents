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
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">{worker.id}</span>
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            worker.idle ? "bg-slate-600" : "bg-emerald-400 animate-pulse"
          }`}
          title={worker.idle ? "idle" : "working"}
        />
      </div>
      <div className="mt-1 flex items-center gap-2 text-sm text-slate-400">
        <span>{worker.agent_name}</span>
        <SourceBadge source={worker.agent_source} />
      </div>
      {issue ? (
        <div className="mt-3 rounded bg-slate-800 p-2 text-sm">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate">{issue.title}</span>
            <StateChip state={issue.state} />
          </div>
          {issue.branch && (
            <div className="mt-1 font-mono text-xs text-slate-500">{issue.branch}</div>
          )}
        </div>
      ) : (
        <div className="mt-3 text-sm text-slate-600">waiting for an issue</div>
      )}
    </div>
  );
}

export default function AgentBoard({ state }: { state: AppState }) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Agents
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {state.workers.map((worker) => (
          <WorkerCard key={worker.id} worker={worker} issues={state.issues} />
        ))}
      </div>
    </section>
  );
}

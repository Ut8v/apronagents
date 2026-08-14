import { AppState, Issue } from "../api/client";
import { StateChip } from "./Badges";

const QUEUE_ORDER = ["merging", "approved", "test_failed", "merged"] as const;

function QueueRow({ issue }: { issue: Issue }) {
  return (
    <li className="flex items-center justify-between gap-2 rounded bg-slate-900 px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-sm">{issue.title}</div>
        {issue.branch && (
          <div className="truncate font-mono text-xs text-slate-500">{issue.branch}</div>
        )}
      </div>
      <StateChip state={issue.state} />
    </li>
  );
}

export default function MergeQueue({ state }: { state: AppState }) {
  const inQueue = QUEUE_ORDER.flatMap((queueState) =>
    state.issues.filter((issue) => issue.state === queueState),
  );
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Merge queue
      </h2>
      {inQueue.length === 0 ? (
        <p className="text-sm text-slate-600">nothing approved yet</p>
      ) : (
        <ul className="space-y-2">
          {inQueue.map((issue) => (
            <QueueRow key={issue.issue_id} issue={issue} />
          ))}
        </ul>
      )}
    </section>
  );
}

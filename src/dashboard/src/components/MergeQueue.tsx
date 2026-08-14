import { AppState, Issue } from "../api/client";
import { stateColor, StateChip } from "./Badges";

const QUEUE_ORDER = ["merging", "approved", "test_failed", "merged"] as const;

function QueueRow({ issue }: { issue: Issue }) {
  return (
    <li
      className={`flex items-center gap-[11px] border-b border-line-dim px-[11px] py-2.5 last:border-b-0 ${
        issue.state === "merged" ? "opacity-[0.62]" : ""
      }`}
    >
      <span
        className="w-[2px] self-stretch rounded-[2px]"
        style={{ background: stateColor(issue.state) }}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[12.5px] text-[oklch(0.89_0.008_255)]">
          {issue.title}
        </div>
        {issue.branch && (
          <div className="truncate font-mono text-[10.5px] text-[oklch(0.54_0.02_205)]">
            {issue.branch}
          </div>
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
      <div className="mb-2.5 flex items-center gap-3">
        <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.66_0.012_255)]">
          merge queue
        </span>
        <span className="h-px flex-1 bg-[oklch(0.26_0.013_255)]" />
      </div>
      {inQueue.length === 0 ? (
        <div className="flex items-center gap-3 rounded-[10px] border border-dashed border-[oklch(0.3_0.013_255)] p-4">
          <span className="h-2 w-2 rounded-full border border-[oklch(0.4_0.012_255)]" />
          <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[oklch(0.55_0.012_255)]">
            nothing approved yet
          </span>
        </div>
      ) : (
        <ul className="overflow-hidden rounded-[10px] border border-line bg-[oklch(0.19_0.011_255)]">
          {inQueue.map((issue) => (
            <QueueRow key={issue.issue_id} issue={issue} />
          ))}
        </ul>
      )}
    </section>
  );
}

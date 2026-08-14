import { IssueState } from "../api/client";

const STATE_STYLES: Record<IssueState, string> = {
  queued: "bg-slate-700 text-slate-200",
  claimed: "bg-sky-900 text-sky-200",
  in_progress: "bg-sky-800 text-sky-100",
  in_review: "bg-amber-800 text-amber-100",
  changes_requested: "bg-orange-900 text-orange-200",
  approved: "bg-emerald-900 text-emerald-200",
  merging: "bg-violet-900 text-violet-200",
  test_failed: "bg-red-900 text-red-200",
  merged: "bg-emerald-800 text-emerald-100",
};

export function StateChip({ state }: { state: IssueState }) {
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${STATE_STYLES[state]}`}
    >
      {state.replace("_", " ")}
    </span>
  );
}

const SOURCE_STYLES: Record<string, string> = {
  shipped: "border-slate-500 text-slate-300",
  user: "border-sky-500 text-sky-300",
  project: "border-emerald-500 text-emerald-300",
  "claude-user": "border-violet-500 text-violet-300",
  "claude-project": "border-violet-400 text-violet-200",
};

export function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null;
  const style = SOURCE_STYLES[source] ?? "border-slate-500 text-slate-300";
  return (
    <span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${style}`}>
      {source}
    </span>
  );
}

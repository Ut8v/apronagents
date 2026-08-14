import { useEffect, useState } from "react";
import { api, Issue, IssueDiff } from "../api/client";
import { StateChip } from "./Badges";
import DiffView from "./DiffView";

interface Props {
  issue: Issue;
  onAction: () => void;
}

export default function ReviewCard({ issue, onAction }: Props) {
  const [diff, setDiff] = useState<IssueDiff | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getDiff(issue.issue_id).then(setDiff).catch(() => setDiff(null));
  }, [issue.issue_id, issue.updated_at]);

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      onAction();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-900/60 bg-slate-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium">{issue.title}</h3>
          <p className="mt-0.5 text-sm text-slate-400">{issue.description}</p>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            {issue.branch && <span className="font-mono">{issue.branch}</span>}
            {issue.worker_id && <span>by {issue.worker_id}</span>}
          </div>
        </div>
        <StateChip state={issue.state} />
      </div>

      {diff && (
        <div className="mt-3">
          <div className="mb-2 flex flex-wrap gap-2">
            {diff.files.map((file) => (
              <span
                key={file.path}
                className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300"
              >
                <span className="mr-1 text-sky-400">{file.status}</span>
                {file.path}
              </span>
            ))}
          </div>
          <DiffView diff={diff.diff} />
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          disabled={busy}
          onClick={() => act(() => api.approve(issue.issue_id))}
          className="rounded bg-emerald-700 px-3 py-1.5 text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"
        >
          Approve &amp; merge
        </button>
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="what should change?"
          className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm"
        />
        <button
          disabled={busy}
          onClick={() => act(() => api.sendBack(issue.issue_id, reason))}
          className="rounded bg-orange-800 px-3 py-1.5 text-sm font-medium hover:bg-orange-700 disabled:opacity-50"
        >
          Send back
        </button>
      </div>
    </div>
  );
}

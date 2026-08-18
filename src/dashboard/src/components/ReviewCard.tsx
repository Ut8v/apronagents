import { useEffect, useState } from "react";
import { api, DiffAnnotation, Issue, IssueDiff } from "../api/client";
import { FileStatusSquare, StateChip } from "./Badges";
import DiffView from "./DiffView";

interface Props {
  issue: Issue;
  armed: boolean;
  onArm: () => void;
  onDisarm: () => void;
  onAction: () => void;
}

function heldFor(updatedAt: number): string {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - updatedAt));
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `held ${minutes}m ${seconds % 60}s` : `held ${seconds}s`;
}

const MONO_BTN = "font-mono text-[11px] uppercase tracking-[0.1em] transition-colors duration-[140ms] rounded-[7px]";

export default function ReviewCard({ issue, armed, onArm, onDisarm, onAction }: Props) {
  const [diff, setDiff] = useState<IssueDiff | null>(null);
  const [reason, setReason] = useState("");
  const [annotations, setAnnotations] = useState<DiffAnnotation[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getDiff(issue.issue_id).then(setDiff).catch(() => setDiff(null));
    setAnnotations([]); // a fresh diff invalidates line-pinned notes
  }, [issue.issue_id, issue.updated_at]);

  const upsertNote = (path: string, line: number, note: string) =>
    setAnnotations((all) =>
      all.map((a) => (a.path === path && a.line === line ? { ...a, note } : a)),
    );
  const addNote = (path: string, line: number) =>
    setAnnotations((all) =>
      all.some((a) => a.path === path && a.line === line)
        ? all
        : [...all, { path, line, note: "" }],
    );
  const removeNote = (path: string, line: number) =>
    setAnnotations((all) =>
      all.filter((a) => !(a.path === path && a.line === line)),
    );
  const noteCount = annotations.filter((a) => a.note.trim()).length;

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      onDisarm();
      onAction();
    } finally {
      setBusy(false);
    }
  };

  return (
    <article
      className="animate-in-card overflow-hidden rounded-xl bg-card"
      style={{
        border: "1px solid oklch(0.32 0.02 78 / 0.6)",
        boxShadow:
          "inset 0 1px 0 oklch(0.78 0.11 78 / 0.25), 0 8px 24px oklch(0.1 0.01 255 / 0.5)",
      }}
    >
      <div
        className="flex items-start gap-4 border-b border-line px-4 py-3.5"
        style={{ background: "linear-gradient(oklch(0.215 0.014 255), oklch(0.2 0.012 255))" }}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <StateChip state={issue.state} />
            <h3 className="text-[15px] font-[620] tracking-[-0.01em] text-ink">
              {issue.title}
            </h3>
          </div>
          {issue.description && (
            <p className="mt-[7px] max-w-[72ch] text-[12.5px] text-muted" style={{ textWrap: "pretty" }}>
              {issue.description}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 whitespace-nowrap font-mono text-[11px]">
          {issue.branch && <span className="text-[oklch(0.72_0.05_205)]">{issue.branch}</span>}
          {issue.worker_id && (
            <span className="text-[oklch(0.55_0.012_255)]">by {issue.worker_id}</span>
          )}
          <span className="text-[oklch(0.45_0.012_255)]">{heldFor(issue.updated_at)}</span>
        </div>
      </div>

      {diff && diff.files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-[oklch(0.25_0.012_255)] px-4 py-2.5">
          {diff.files.map((file) => (
            <span
              key={file.path}
              className="flex items-center gap-1.5 rounded-md border border-[oklch(0.3_0.013_255)] bg-[oklch(0.24_0.012_255)] py-[3px] pl-1.5 pr-2.5 font-mono text-[11px] text-[oklch(0.78_0.01_255)]"
            >
              <FileStatusSquare status={file.status} />
              {file.path}
            </span>
          ))}
        </div>
      )}
      {diff && (
        <DiffView
          diff={diff.diff}
          annotations={annotations}
          onAnnotate={addNote}
          onNoteChange={upsertNote}
          onRemove={removeNote}
        />
      )}

      <div className="flex min-h-[62px] flex-wrap items-center gap-3.5 border-t border-line bg-raised px-4 py-3">
        <div className="flex min-w-[260px] flex-[1_1_300px] items-center gap-2">
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason to send back…"
            className="h-[34px] min-w-0 flex-1 rounded-[7px] border border-[oklch(0.3_0.014_255)] bg-rail px-[11px] text-[12.5px] outline-none transition-colors focus:border-[oklch(0.62_0.1_45)] focus:shadow-[0_0_0_3px_oklch(0.62_0.1_45/0.14)]"
          />
          <button
            disabled={busy || (!reason.trim() && noteCount === 0)}
            onClick={() => {
              const value = reason;
              const notes = annotations.filter((a) => a.note.trim());
              setReason("");
              setAnnotations([]);
              act(() => api.sendBack(issue.issue_id, value, notes));
            }}
            className={`${MONO_BTN} h-[34px] flex-none border border-[oklch(0.36_0.05_45)] bg-transparent px-3.5 text-[oklch(0.78_0.1_45)] hover:bg-[oklch(0.3_0.05_45/0.4)] disabled:opacity-50`}
          >
            send back{noteCount > 0 ? ` · ${noteCount} note${noteCount > 1 ? "s" : ""}` : ""}
          </button>
        </div>
        <div className="flex h-[34px] flex-[0_0_400px] items-center justify-end">
          {!armed ? (
            <button
              disabled={busy}
              onClick={onArm}
              className={`${MONO_BTN} h-[34px] w-[158px] border border-[oklch(0.42_0.07_152)] bg-[oklch(0.28_0.05_152)] text-[oklch(0.88_0.09_152)] hover:bg-[oklch(0.36_0.07_152)] disabled:opacity-50`}
            >
              approve &amp; merge
            </button>
          ) : (
            <div className="flex items-center gap-2.5">
              <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.7_0.09_152)]">
                cleared for merge?
              </span>
              <button
                disabled={busy}
                onClick={() => act(() => api.approve(issue.issue_id))}
                className={`${MONO_BTN} h-[34px] w-[158px] border border-[oklch(0.62_0.11_152)] bg-[oklch(0.5_0.11_152)] text-[oklch(0.98_0.02_152)] hover:bg-[oklch(0.57_0.12_152)] disabled:opacity-50`}
              >
                confirm merge
              </button>
              <button
                disabled={busy}
                onClick={onDisarm}
                className={`${MONO_BTN} h-[34px] w-[94px] border border-[oklch(0.32_0.013_255)] bg-[oklch(0.22_0.012_255)] text-[oklch(0.7_0.012_255)] hover:bg-[oklch(0.26_0.013_255)]`}
              >
                cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

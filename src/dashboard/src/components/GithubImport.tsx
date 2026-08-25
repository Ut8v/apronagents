import { useEffect, useState } from "react";
import { api, GithubIssue } from "../api/client";

/** Dispatch real GitHub issues as a task. Renders nothing when the project
 * has no gh CLI or no GitHub remote — the feature simply isn't offered. */
export default function GithubImport({
  onDispatched,
}: {
  onDispatched: (label: string) => void;
}) {
  const [issues, setIssues] = useState<GithubIssue[] | null>(null);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .getGithubIssues()
      .then((r) => setIssues(r.available ? r.issues : null))
      .catch(() => setIssues(null));
  }, []);

  if (issues === null) return null;

  const toggle = (n: number) =>
    setSelected((all) =>
      all.includes(n) ? all.filter((x) => x !== n) : [...all, n],
    );

  const dispatch = async () => {
    setBusy(true);
    try {
      const numbers = [...selected].sort((a, b) => a - b);
      await api.submitTaskFromIssues(numbers);
      onDispatched(`github issue${numbers.length > 1 ? "s" : ""} ${numbers.map((n) => `#${n}`).join(", ")}`);
      setSelected([]);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.62_0.012_255)] transition-colors hover:text-[oklch(0.88_0.008_255)]"
      >
        <span className="text-[9px]">{open ? "▾" : "▸"}</span>
        import from github issues
        <span className="text-[oklch(0.5_0.012_255)]">({issues.length} open)</span>
      </button>
      {open && (
        <div className="mt-2 overflow-hidden rounded-lg border border-[oklch(0.3_0.014_255)] bg-rail">
          <div className="max-h-[220px] overflow-auto">
            {issues.length === 0 && (
              <p className="px-3 py-2.5 font-mono text-[11px] text-[oklch(0.55_0.012_255)]">
                no open issues
              </p>
            )}
            {issues.map((issue) => (
              <label
                key={issue.number}
                className="flex cursor-pointer items-center gap-2.5 border-b border-[oklch(0.24_0.012_255)] px-3 py-[7px] last:border-b-0 hover:bg-[oklch(0.21_0.012_255)]"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(issue.number)}
                  onChange={() => toggle(issue.number)}
                  className="accent-[oklch(0.6_0.09_205)]"
                />
                <span className="font-mono text-[11px] text-[oklch(0.6_0.05_205)]">
                  #{issue.number}
                </span>
                <span className="min-w-0 flex-1 truncate text-[12.5px] text-[oklch(0.88_0.008_255)]">
                  {issue.title}
                </span>
                {issue.labels.slice(0, 3).map((label) => (
                  <span
                    key={label}
                    className="rounded-full border border-[oklch(0.32_0.013_255)] px-2 py-px font-mono text-[9px] text-[oklch(0.62_0.012_255)]"
                  >
                    {label}
                  </span>
                ))}
              </label>
            ))}
          </div>
          {issues.length > 0 && (
            <div className="flex items-center gap-3 border-t border-[oklch(0.27_0.013_255)] bg-[oklch(0.19_0.011_255)] px-3 py-2">
              <span className="font-mono text-[10px] text-[oklch(0.55_0.012_255)]">
                {selected.length === 0
                  ? "pick one or more issues"
                  : `${selected.length} selected — dispatched together as one task`}
              </span>
              <span className="flex-1" />
              <button
                disabled={busy || selected.length === 0}
                onClick={dispatch}
                className="h-[28px] rounded-[7px] border border-[oklch(0.6_0.09_205/0.5)] bg-[oklch(0.3_0.05_205)] px-3.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.92_0.05_205)] transition-colors hover:bg-[oklch(0.38_0.07_205)] disabled:opacity-50"
              >
                dispatch {selected.length || ""}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, RunSummary } from "../api/client";

function when(run: RunSummary): string {
  const date = new Date(run.started_at * 1000);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function duration(run: RunSummary): string {
  if (run.finished_at === null) return "—";
  const seconds = Math.max(0, Math.round(run.finished_at - run.started_at));
  const minutes = Math.floor(seconds / 60);
  return minutes > 0 ? `${minutes}m ${seconds % 60}s` : `${seconds}s`;
}

/** Past runs from the journal, each expandable into its shareable report. */
export default function RunsView() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [report, setReport] = useState<string>("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.getRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  const open = async (taskId: string) => {
    if (openId === taskId) {
      setOpenId(null);
      return;
    }
    setOpenId(taskId);
    setReport("");
    setCopied(false);
    const { markdown } = await api.getRunReport(taskId);
    setReport(markdown);
  };

  const copy = async () => {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="mx-auto flex max-w-[980px] flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.66_0.012_255)]">
          run history
        </span>
        <span className="h-px flex-1 bg-[oklch(0.26_0.013_255)]" />
        <span className="font-mono text-[10px] text-[oklch(0.5_0.012_255)]">
          also in your terminal: apron report
        </span>
      </div>

      {runs.length === 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-dashed border-[oklch(0.3_0.013_255)] p-6">
          <span className="h-2 w-2 rounded-full border border-[oklch(0.4_0.012_255)]" />
          <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[oklch(0.55_0.012_255)]">
            no runs recorded yet — dispatch a task and it will land here
          </span>
        </div>
      )}

      {runs.map((run) => (
        <div
          key={run.task_id}
          className="overflow-hidden rounded-xl border border-[oklch(0.28_0.013_255)] bg-card"
        >
          <button
            onClick={() => open(run.task_id)}
            className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-[oklch(0.21_0.012_255)]"
          >
            <span className="font-mono text-[11px] text-[oklch(0.6_0.05_205)]">
              {run.task_id}
            </span>
            <span className="min-w-0 flex-1 truncate text-[13px] text-ink">
              {run.prompt}
            </span>
            <span className="whitespace-nowrap font-mono text-[10.5px] text-[oklch(0.55_0.012_255)]">
              {when(run)} · {duration(run)}
            </span>
            <span className="whitespace-nowrap font-mono text-[10.5px] text-[oklch(0.66_0.012_255)]">
              {run.merged}/{run.issues} merged
            </span>
            <span
              className="whitespace-nowrap rounded-[5px] border px-2 py-px font-mono text-[9px] uppercase tracking-[0.08em]"
              style={
                run.status === "completed"
                  ? {
                      color: "oklch(0.78 0.09 152)",
                      borderColor: "oklch(0.62 0.09 152 / 0.4)",
                      background: "oklch(0.62 0.09 152 / 0.12)",
                    }
                  : {
                      color: "oklch(0.8 0.09 78)",
                      borderColor: "oklch(0.7 0.09 78 / 0.4)",
                      background: "oklch(0.7 0.09 78 / 0.12)",
                    }
              }
            >
              {run.status}
            </span>
          </button>
          {openId === run.task_id && (
            <div className="border-t border-[oklch(0.25_0.012_255)]">
              <div className="flex items-center gap-3 bg-[oklch(0.19_0.011_255)] px-4 py-2">
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[oklch(0.6_0.012_255)]">
                  shareable report · markdown
                </span>
                <span className="flex-1" />
                <button
                  onClick={copy}
                  className="rounded-[6px] border border-[oklch(0.32_0.013_255)] px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.08em] text-[oklch(0.7_0.012_255)] hover:text-[oklch(0.92_0.008_255)]"
                >
                  {copied ? "copied ✓" : "copy"}
                </button>
              </div>
              <pre className="max-h-[440px] overflow-auto whitespace-pre-wrap bg-[oklch(0.155_0.01_255)] px-5 py-4 font-mono text-[11.5px] leading-[1.75] text-[oklch(0.82_0.008_255)]">
                {report || "…"}
              </pre>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

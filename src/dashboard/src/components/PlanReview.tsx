import { useEffect, useState } from "react";
import { api, PlanIssue, PlanReviewState } from "../api/client";

interface Props {
  plan: PlanReviewState;
  onAction: () => void;
}

const FIELD =
  "w-full rounded-[7px] border border-[oklch(0.3_0.014_255)] bg-rail px-[10px] outline-none transition-colors focus:border-[oklch(0.6_0.09_205)] focus:shadow-[0_0_0_3px_oklch(0.6_0.09_205/0.14)]";

/** The plan gate: the proposed issue split, editable, held until the human
 * dispatches it — the planning-time twin of the merge review card. */
export default function PlanReview({ plan, onAction }: Props) {
  const [issues, setIssues] = useState<PlanIssue[]>(plan.issues);
  const [busy, setBusy] = useState(false);

  useEffect(() => setIssues(plan.issues), [plan.task_id]);

  const edit = (index: number, patch: Partial<PlanIssue>) =>
    setIssues((all) => all.map((i, n) => (n === index ? { ...i, ...patch } : i)));
  const remove = (index: number) => {
    const gone = issues[index].id;
    setIssues((all) =>
      all
        .filter((_, n) => n !== index)
        .map((i) => ({ ...i, depends_on: i.depends_on.filter((d) => d !== gone) })),
    );
  };
  const add = () =>
    setIssues((all) => [
      ...all,
      { id: `issue-${all.length + 1}`, title: "", description: "", depends_on: [] },
    ]);

  const ready = issues.length > 0 && issues.every((i) => i.title.trim());
  const dispatch = async () => {
    setBusy(true);
    try {
      await api.approvePlan(plan.task_id, issues);
      onAction();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="animate-in-card overflow-hidden rounded-xl bg-card"
      style={{
        border: "1px solid oklch(0.5 0.07 205 / 0.55)",
        boxShadow:
          "inset 0 1px 0 oklch(0.74 0.1 205 / 0.25), 0 8px 24px oklch(0.1 0.01 255 / 0.5)",
      }}
    >
      <div
        className="flex items-center gap-3 border-b border-line px-4 py-3"
        style={{ background: "linear-gradient(oklch(0.215 0.014 255), oklch(0.2 0.012 255))" }}
      >
        <span className="h-[7px] w-[7px] animate-pulse-slow rounded-full bg-[oklch(0.74_0.1_205)]" />
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.8_0.07_205)]">
          plan gate
        </span>
        <span className="text-[13px] text-muted">
          The planner proposes {plan.issues.length} issue{plan.issues.length === 1 ? "" : "s"} —
          edit freely, then dispatch. No worker starts until you do.
        </span>
      </div>

      <div className="flex flex-col gap-3 p-4">
        {issues.map((issue, index) => (
          <div
            key={index}
            className="rounded-lg border border-[oklch(0.28_0.013_255)] bg-[oklch(0.185_0.011_255)] p-3"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-[10px] text-[oklch(0.6_0.05_205)]">{issue.id}</span>
              <span className="flex-1" />
              <label className="flex items-center gap-1.5 font-mono text-[10px] text-[oklch(0.55_0.012_255)]">
                needs
                <input
                  value={issue.depends_on.join(", ")}
                  onChange={(e) =>
                    edit(index, {
                      depends_on: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  placeholder="—"
                  className={`${FIELD} h-[24px] w-[180px] font-mono text-[10.5px] text-[oklch(0.8_0.01_255)]`}
                />
              </label>
              <button
                onClick={() => remove(index)}
                title="drop this issue"
                className="font-mono text-[11px] text-[oklch(0.55_0.012_255)] hover:text-[oklch(0.78_0.1_25)]"
              >
                ✕
              </button>
            </div>
            <input
              value={issue.title}
              onChange={(e) => edit(index, { title: e.target.value })}
              placeholder="Issue title…"
              className={`${FIELD} h-[30px] text-[13px] font-[550] text-ink`}
            />
            <textarea
              value={issue.description}
              onChange={(e) => edit(index, { description: e.target.value })}
              placeholder="What exactly should the worker do?"
              rows={2}
              className={`${FIELD} mt-1.5 resize-y py-1.5 text-[12.5px] leading-relaxed text-[oklch(0.82_0.008_255)]`}
            />
          </div>
        ))}

        <div className="flex items-center gap-3">
          <button
            onClick={add}
            className="rounded-[7px] border border-dashed border-[oklch(0.32_0.013_255)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.62_0.012_255)] hover:border-[oklch(0.45_0.013_255)] hover:text-[oklch(0.85_0.008_255)]"
          >
            + add issue
          </button>
          <span className="flex-1" />
          <button
            disabled={busy || !ready}
            onClick={dispatch}
            className="h-[34px] rounded-[7px] border border-[oklch(0.6_0.09_205/0.5)] bg-[oklch(0.3_0.05_205)] px-5 font-mono text-[11px] uppercase tracking-[0.1em] text-[oklch(0.92_0.05_205)] transition-colors hover:bg-[oklch(0.38_0.07_205)] disabled:opacity-50"
          >
            dispatch {issues.length} issue{issues.length === 1 ? "" : "s"}
          </button>
        </div>
      </div>
    </section>
  );
}

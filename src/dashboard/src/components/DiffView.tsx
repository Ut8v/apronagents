function lineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-slate-400";
  if (line.startsWith("@@")) return "text-sky-400";
  if (line.startsWith("+")) return "bg-emerald-950 text-emerald-300";
  if (line.startsWith("-")) return "bg-red-950 text-red-300";
  if (line.startsWith("diff ")) return "mt-2 font-semibold text-slate-300";
  return "text-slate-400";
}

export default function DiffView({ diff }: { diff: string }) {
  if (!diff.trim()) {
    return <p className="text-sm text-slate-600">empty diff</p>;
  }
  return (
    <pre className="max-h-96 overflow-auto rounded bg-slate-950 p-3 font-mono text-xs leading-5">
      {diff.split("\n").map((line, index) => (
        <div key={index} className={lineClass(line)}>
          {line || " "}
        </div>
      ))}
    </pre>
  );
}

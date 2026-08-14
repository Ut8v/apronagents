interface DiffLine {
  kind: "add" | "del" | "ctx" | "hunk";
  text: string;
  num: number | null;
}

interface FileGroup {
  path: string;
  header: string;
  plus: number;
  minus: number;
  lines: DiffLine[];
}

const SKIP = /^(index |new file|deleted file|old mode|new mode|similarity|rename |--- |\\ No newline)/;

/** Parse a unified diff into per-file groups with line numbers. */
export function parseDiff(diff: string): FileGroup[] {
  const groups: FileGroup[] = [];
  let group: FileGroup | null = null;
  let newLine = 0;
  let oldLine = 0;

  for (const line of diff.split("\n")) {
    if (line.startsWith("diff --git ")) {
      group = { path: line.split(" b/").pop() ?? "?", header: "", plus: 0, minus: 0, lines: [] };
      groups.push(group);
    } else if (!group || SKIP.test(line)) {
      if (line.startsWith("+++ b/") && group) group.path = line.slice(6);
    } else if (line.startsWith("@@")) {
      const match = /@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
      oldLine = match ? parseInt(match[1], 10) : 0;
      newLine = match ? parseInt(match[2], 10) : 0;
      if (!group.header) group.header = line;
      else group.lines.push({ kind: "hunk", text: line, num: null });
    } else if (line.startsWith("+")) {
      group.plus += 1;
      group.lines.push({ kind: "add", text: line, num: newLine++ });
    } else if (line.startsWith("-")) {
      group.minus += 1;
      group.lines.push({ kind: "del", text: line, num: oldLine++ });
    } else if (line) {
      group.lines.push({ kind: "ctx", text: line, num: newLine++ });
      oldLine += 1;
    }
  }
  return groups;
}

const LINE_STYLES: Record<DiffLine["kind"], React.CSSProperties> = {
  add: { background: "oklch(0.5 0.09 152 / 0.13)", color: "oklch(0.83 0.1 152)" },
  del: { background: "oklch(0.5 0.11 25 / 0.13)", color: "oklch(0.78 0.11 25)" },
  ctx: { color: "oklch(0.64 0.01 255)" },
  hunk: { color: "oklch(0.74 0.09 205)" },
};

export default function DiffView({ diff }: { diff: string }) {
  const groups = parseDiff(diff);
  if (groups.length === 0) {
    return (
      <p className="px-4 py-3 font-mono text-[11px] text-[oklch(0.55_0.012_255)]">
        empty diff
      </p>
    );
  }
  return (
    <div className="max-h-[300px] overflow-auto bg-[oklch(0.155_0.01_255)]">
      {groups.map((group) => (
        <div key={group.path}>
          <div
            className="sticky top-0 flex items-baseline gap-3 border-b border-[oklch(0.26_0.013_255)] px-4 py-[7px] font-mono text-[11px] backdrop-blur-sm"
            style={{ background: "oklch(0.19 0.012 255 / 0.96)" }}
          >
            <span className="text-[oklch(0.86_0.008_255)]">{group.path}</span>
            <span className="text-[oklch(0.74_0.09_205)]">{group.header}</span>
            <span className="flex-1" />
            <span className="text-[oklch(0.74_0.1_152)]">+{group.plus}</span>
            <span className="text-[oklch(0.68_0.13_25)]">-{group.minus}</span>
          </div>
          <div className="py-1">
            {group.lines.map((line, index) => (
              <div
                key={index}
                className="whitespace-pre px-4 font-mono text-[11.5px] leading-[1.7]"
                style={LINE_STYLES[line.kind]}
              >
                <span className="mr-3 inline-block w-[26px] select-none text-right text-[oklch(0.42_0.012_255)]">
                  {line.num ?? ""}
                </span>
                {line.text}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

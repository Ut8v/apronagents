import { useEffect, useState } from "react";
import { api, WorkspaceFile } from "../api/client";

interface Node {
  name: string;
  path: string;
  children: Node[];
  file?: WorkspaceFile;
}

function buildTree(files: WorkspaceFile[]): Node {
  const root: Node = { name: "", path: "", children: [] };
  for (const file of files) {
    let node = root;
    const parts = file.path.split("/");
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join("/");
      let child = node.children.find((c) => c.name === part);
      if (!child) {
        child = { name: part, path, children: [] };
        node.children.push(child);
      }
      node = child;
    });
    node.file = file;
  }
  const sort = (node: Node) => {
    node.children.sort((a, b) =>
      (a.children.length ? 0 : 1) - (b.children.length ? 0 : 1) ||
      a.name.localeCompare(b.name),
    );
    node.children.forEach(sort);
  };
  sort(root);
  return root;
}

const BADGE: Record<string, { label: string; cls: string }> = {
  A: { label: "A", cls: "text-[oklch(0.74_0.1_152)]" },
  M: { label: "M", cls: "text-[oklch(0.78_0.1_78)]" },
  D: { label: "D", cls: "text-[oklch(0.68_0.13_25)]" },
};

function FileRow({ node, depth }: { node: Node; depth: number }) {
  const file = node.file!;
  const badge = file.merged ? BADGE[file.merged] : null;
  return (
    <div
      className="flex items-center gap-1.5 rounded px-1.5 py-[3px] font-mono text-[11px] text-[oklch(0.78_0.01_255)]"
      style={{ paddingLeft: 8 + depth * 14 }}
      title={
        file.editing.length
          ? `being changed by: ${file.editing.join(", ")}`
          : file.merged
            ? "changed by merged work this run"
            : undefined
      }
    >
      <span className={`truncate ${file.merged === "D" ? "line-through opacity-60" : ""}`}>
        {node.name}
      </span>
      {file.editing.length > 0 && (
        <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-[oklch(0.74_0.1_205)]" />
      )}
      {badge && <span className={`ml-auto text-[10px] font-bold ${badge.cls}`}>{badge.label}</span>}
    </div>
  );
}

function Folder({ node, depth }: { node: Node; depth: number }) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 rounded px-1.5 py-[3px] text-left font-mono text-[11px] text-[oklch(0.62_0.012_255)] hover:text-[oklch(0.85_0.008_255)]"
        style={{ paddingLeft: 8 + depth * 14 }}
      >
        <span className="text-[9px]">{open ? "▾" : "▸"}</span>
        <span className="truncate">{node.name}/</span>
      </button>
      {open && node.children.map((child) => <Entry key={child.path} node={child} depth={depth + 1} />)}
    </div>
  );
}

function Entry({ node, depth }: { node: Node; depth: number }) {
  return node.children.length ? (
    <Folder node={node} depth={depth} />
  ) : (
    <FileRow node={node} depth={depth} />
  );
}

/** VS Code-style project tree: every file in sandbox main, badged with what
 * merged work changed (A/M/D since the seed) and a pulsing dot on files an
 * in-flight issue branch is touching. */
export default function WorkspaceTree({ refreshKey }: { refreshKey: string }) {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);

  useEffect(() => {
    api.getWorkspace().then((w) => setFiles(w.files)).catch(() => undefined);
  }, [refreshKey]);

  const changed = files.filter((f) => f.merged || f.editing.length).length;
  const tree = buildTree(files);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center gap-2 px-1">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.66_0.012_255)]">
          workspace
        </span>
        {changed > 0 && (
          <span className="font-mono text-[10px] text-[oklch(0.55_0.012_255)]">
            {changed} changed
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-auto pr-1">
        {tree.children.map((node) => (
          <Entry key={node.path} node={node} depth={0} />
        ))}
        {files.length === 0 && (
          <p className="px-1.5 font-mono text-[10.5px] text-[oklch(0.5_0.012_255)]">
            empty project
          </p>
        )}
      </div>
      <div className="mt-2 space-y-0.5 border-t border-[oklch(0.25_0.012_255)] px-1.5 pt-2 font-mono text-[9px] text-[oklch(0.5_0.012_255)]">
        <div><span className="font-bold text-[oklch(0.74_0.1_152)]">A</span> added · <span className="font-bold text-[oklch(0.78_0.1_78)]">M</span> modified · <span className="font-bold text-[oklch(0.68_0.13_25)]">D</span> deleted (merged so far)</div>
        <div><span className="inline-block h-1.5 w-1.5 rounded-full bg-[oklch(0.74_0.1_205)]" /> being changed by an in-flight issue</div>
      </div>
    </div>
  );
}

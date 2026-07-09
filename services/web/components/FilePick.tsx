"use client";

/**
 * Shared .x3p file picker — used by the homepage upload panel and the Studio
 * upload modal. The input is visually hidden with `sr-only` (not `hidden`) so
 * it stays in the tab order: Tab reaches it, Enter/Space opens the native
 * picker, and the surrounding label shows a focus ring via `focus-within`.
 */
export function FilePick({
  label,
  files,
  onPick,
  multiple,
}: {
  label: string;
  files: File[];
  onPick: (f: File[]) => void;
  multiple?: boolean;
}) {
  const summary =
    files.length === 0
      ? multiple
        ? "Choose .x3p land scans…"
        : "Choose an .x3p scan…"
      : files.length === 1
        ? files[0].name
        : `${files.length} scans selected`;
  return (
    <label className="group flex min-h-24 cursor-pointer flex-col justify-center gap-1.5 rounded-xl border border-dashed border-control bg-foreground/[0.02] p-4 text-sm transition focus-within:border-accent focus-within:ring-2 focus-within:ring-accent hover:border-accent hover:bg-foreground/[0.05]">
      <span className="font-medium text-foreground">{label}</span>
      <span className="truncate text-muted group-hover:text-foreground/80">{summary}</span>
      <input
        type="file"
        accept=".x3p"
        multiple={multiple}
        className="sr-only"
        onChange={(e) => onPick(Array.from(e.target.files ?? []))}
      />
    </label>
  );
}

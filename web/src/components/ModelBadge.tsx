/**
 * Which model produced a record. Provenance is stored per reel
 * (`tokens.backend` + `tokens.model`) — a local 7B and Claude write records of
 * different depth, so every surface that shows a record says which one wrote it.
 */

export const backendChip = (b: string): { label: string; cls: string } | null => {
  if (!b) return null;
  if (b.startsWith("local->")) return { label: "Local→Claude", cls: "bg-peach/15 text-peach" };
  if (b === "local") return { label: "Local", cls: "bg-green/15 text-green" };
  if (b === "api") return { label: "Claude API", cls: "bg-blue/15 text-blue" };
  if (b === "claude-cli") return { label: "Claude", cls: "bg-mauve/15 text-mauve" };
  return { label: b, cls: "bg-surface0 text-subtext" };
};

export function ModelBadge({
  backend,
  model = "",
  showModel = false,
  size = "sm",
}: {
  backend: string;
  model?: string;
  showModel?: boolean;   // spell the model out where there is room (reader, table)
  size?: "xs" | "sm";
}) {
  const chip = backendChip(backend);
  if (!chip) return null;
  const pad = size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded font-medium ${pad} ${chip.cls}`}
      title={`vision by ${backend}${model ? ` · ${model}` : ""}`}
    >
      {chip.label}
      {showModel && model && <span className="font-normal opacity-70">{model}</span>}
    </span>
  );
}

/**
 * A tag chip coloured by the collection it belongs to.
 *
 * The colour is a stable hash of the collection name, so `ai` is the same accent
 * on every screen and in every session — no palette to maintain, no drift. A tag
 * that spans two collections renders as a split chip rather than a blended colour:
 * blending two accents invents a third meaning that maps to no collection.
 */

// Catppuccin accents that stay legible on both `base` and `surface0`. Ordered so
// adjacent hashes land on visually distant hues.
const ACCENTS = [
  "mauve", "green", "peach", "blue", "pink", "yellow",
  "teal", "lavender", "flamingo", "sapphire", "maroon", "sky",
] as const;

export type Accent = (typeof ACCENTS)[number];

/** FNV-1a — small, stable across reloads and machines. */
export function accentFor(name: string): Accent {
  let h = 0x811c9dc5;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return ACCENTS[h % ACCENTS.length];
}

// Tailwind needs literal class names to survive its scanner — no template strings.
const TEXT: Record<Accent, string> = {
  mauve: "text-mauve", green: "text-green", peach: "text-peach", blue: "text-blue",
  pink: "text-pink", yellow: "text-yellow", teal: "text-teal", lavender: "text-lavender",
  flamingo: "text-flamingo", sapphire: "text-sapphire", maroon: "text-maroon", sky: "text-sky",
};
const BG: Record<Accent, string> = {
  mauve: "bg-mauve", green: "bg-green", peach: "bg-peach", blue: "bg-blue",
  pink: "bg-pink", yellow: "bg-yellow", teal: "bg-teal", lavender: "bg-lavender",
  flamingo: "bg-flamingo", sapphire: "bg-sapphire", maroon: "bg-maroon", sky: "bg-sky",
};
const RING: Record<Accent, string> = {
  mauve: "ring-mauve/40", green: "ring-green/40", peach: "ring-peach/40", blue: "ring-blue/40",
  pink: "ring-pink/40", yellow: "ring-yellow/40", teal: "ring-teal/40", lavender: "ring-lavender/40",
  flamingo: "ring-flamingo/40", sapphire: "ring-sapphire/40", maroon: "ring-maroon/40", sky: "ring-sky/40",
};

export function CollectionDot({ name, className = "" }: { name: string; className?: string }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${BG[accentFor(name)]} ${className}`} />;
}

export function TagChip({
  tag,
  count,
  collections = [],
  onClick,
  title,
  size = "sm",
}: {
  tag: string;
  count?: number;
  collections?: { name: string; count: number }[];
  onClick?: () => void;
  title?: string;
  size?: "sm" | "md";
}) {
  const top = collections.slice(0, 2);
  const accent = top.length ? accentFor(top[0].name) : "mauve";
  const pad = size === "md" ? "px-2.5 py-1 text-sm" : "px-2 py-0.5 text-xs";
  const label =
    title ??
    (collections.length
      ? `${count ?? ""} reels · ${collections.map((c) => `${c.name} (${c.count})`).join(", ")}`
      : `${count ?? ""} reels`);

  return (
    <button
      onClick={onClick}
      title={label}
      disabled={!onClick}
      className={`group relative inline-flex items-center gap-1.5 overflow-hidden rounded-md
        ring-1 ${RING[accent]} bg-surface0/60 ${pad} ${TEXT[accent]}
        transition-colors hover:bg-surface0 disabled:cursor-default`}
    >
      {/* colour rail: one bar per collection, split when a tag spans two */}
      <span className="absolute inset-y-0 left-0 flex w-1 flex-col">
        {(top.length ? top : [{ name: "", count: 0 }]).map((c, i) => (
          <span key={i} className={`flex-1 ${c.name ? BG[accentFor(c.name)] : "bg-overlay0"}`} />
        ))}
      </span>
      <span className="pl-1.5 font-medium">#{tag}</span>
      {count != null && <span className="text-overlay0">{count}</span>}
      {collections.length > 2 && (
        <span className="text-overlay0" title={collections.map((c) => c.name).join(", ")}>
          +{collections.length - 2}
        </span>
      )}
    </button>
  );
}

export function CollectionLegend({ names }: { names: string[] }) {
  if (!names.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-overlay0">
      <span>collections:</span>
      {names.map((n) => (
        <span key={n} className="inline-flex items-center gap-1.5">
          <CollectionDot name={n} />
          <span className={TEXT[accentFor(n)]}>{n}</span>
        </span>
      ))}
    </div>
  );
}

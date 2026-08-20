/**
 * One model picker, one source of truth (`GET /api/profiles`).
 *
 * The bench could run seven models while Sync could run three — an accident of
 * when each surface was written. Both now read the same list, and a model that
 * has not been pulled cannot be chosen (the API refuses it too).
 */

import { useEffect, useState } from "react";
import { api, type VisionProfile } from "@/lib/api";
import { Cloud, Cpu } from "lucide-react";

export function useProfiles() {
  const [profiles, setProfiles] = useState<VisionProfile[]>([]);
  useEffect(() => {
    api.profiles().then(setProfiles).catch(() => setProfiles([]));
  }, []);
  return profiles;
}

export function ModelSelect({
  value,
  onChange,
  profiles,
  disabled = false,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  profiles: VisionProfile[];
  disabled?: boolean;
  className?: string;
}) {
  const cloud = profiles.filter((p) => p.kind !== "local");
  const local = profiles.filter((p) => p.kind === "local");
  const sel = profiles.find((p) => p.name === value);

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="flex items-center gap-2">
        {sel?.kind === "local" ? (
          <Cpu size={15} className="text-green" />
        ) : (
          <Cloud size={15} className="text-mauve" />
        )}
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || !profiles.length}
          className="rounded-md border border-surface0 bg-base px-2 py-1.5 text-sm text-text disabled:opacity-60"
        >
          {!profiles.length && <option value={value}>{value}</option>}
          {cloud.length > 0 && (
            <optgroup label="cloud (Claude)">
              {cloud.map((p) => (
                <option key={p.name} value={p.name}>{p.name}</option>
              ))}
            </optgroup>
          )}
          {local.length > 0 && (
            <optgroup label="local GPU">
              {local.map((p) => (
                <option key={p.name} value={p.name} disabled={!p.installed}>
                  {p.name}{p.installed ? "" : " — not installed"}
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>
      {sel && (
        <div className="text-xs text-overlay0">
          {sel.model || sel.kind}{sel.notes ? ` · ${sel.notes}` : ""}
          {sel.kind === "local" ? " · $0, stays on this machine" : " · billed to your Claude quota"}
        </div>
      )}
    </div>
  );
}

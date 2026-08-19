"""The model registry: what can be installed, what is installed, how to install it.

Ollama's stock context (4096) rejects six frames plus our prompt, so every model
is re-created locally with `num_ctx` raised — the same trick `reels-vision` was
built with. Nothing here downloads implicitly: a pull is a command the user runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

REGISTRY_FILE = "models.yaml"
MODELFILE_DIR = Path("scripts/modelfiles")

GPU_HEADROOM_GB = 2.0   # a 32k KV cache on top of the weights — see models.yaml
GPU_BUSY_UTIL = 50      # percent: above this somebody else is mid-job


@dataclass
class ModelEntry:
    name: str            # profile name — what `variants` is keyed by
    tag: str             # what ollama pulls
    num_ctx: int = 32768
    vram_gb: float = 0.0
    role: str = ""
    notes: str = ""
    build: str = ""      # the local model name to run; defaults to `name`

    @property
    def built_name(self) -> str:
        return self.build or self.name


def load_registry(path: str | Path = REGISTRY_FILE) -> list[ModelEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out = []
    for name, e in (data.get("models") or {}).items():
        out.append(ModelEntry(
            name=name, tag=e.get("tag", ""), num_ctx=int(e.get("num_ctx", 32768)),
            vram_gb=float(e.get("vram_gb", 0) or 0), role=e.get("role", ""),
            notes=(e.get("notes") or "").strip(), build=e.get("build", ""),
        ))
    return out


def installed_models() -> set[str]:
    """Model names ollama already has. Empty when ollama is not running/installed."""
    if not shutil.which("ollama"):
        return set()
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return set()
    names = set()
    for line in r.stdout.splitlines()[1:]:          # skip the header
        first = line.split()[0] if line.split() else ""
        if not first:
            continue
        names.add(first)
        names.add(first.split(":")[0])              # `foo:latest` also answers to `foo`
    return names


class GpuContended(RuntimeError):
    """Our model is on the card but not alone — another job pushed layers to CPU.

    Fatal on purpose: a partially-offloaded model answers image prompts an order of
    magnitude slower, so every retry burns 240s to fail again. Stop, don't grind.
    """


def _parse_ps(stdout: str) -> list[tuple[str, str, str]]:
    """(name, size, processor) per `ollama ps` row.

    SIZE and PROCESSOR are each two whitespace-separated columns — "8.1 GB" and
    either "100% GPU" or a split like "17%/83% CPU/GPU".
    """
    out = []
    for line in stdout.splitlines()[1:]:            # skip the header
        f = line.split()
        if len(f) >= 6:
            out.append((f[0], f"{f[2]} {f[3]}", f"{f[4]} {f[5]}"))
    return out


def processor_of(model: str) -> str:
    """How ollama is running `model` — "100% GPU", "17%/83% CPU/GPU", "" if not loaded."""
    names = {model, model.split(":")[0]}
    for name, _size, proc in resident_models():
        if name in names or name.split(":")[0] in names:
            return proc
    return ""


def resident_models() -> list[tuple[str, str, str]]:
    """Models ollama is holding in VRAM right now. Empty when ollama is absent."""
    if not shutil.which("ollama"):
        return []
    try:
        r = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return _parse_ps(r.stdout)


def _parse_smi(stdout: str) -> tuple[float, float, float] | None:
    """(used_gb, total_gb, util_pct) from nvidia-smi csv,noheader,nounits."""
    line = next((ln for ln in stdout.splitlines() if ln.strip()), "")
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return None
    try:
        used, total, util = float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return None
    return used / 1024, total / 1024, util


def gpu_state() -> tuple[float, float, float] | None:
    """GPU 0 as (used_gb, total_gb, util_pct), or None with no nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return _parse_smi(r.stdout)


def vram_need(model: str) -> float:
    """What the registry says this model's weights take, 0.0 if it is not listed."""
    for e in load_registry():
        if model in (e.name, e.built_name, e.tag):
            return e.vram_gb
    return 0.0


def gpu_blockers(want: str = "", need_gb: float | None = None) -> list[str]:
    """Reasons the GPU is not free for a local vision run. Empty list = go.

    The box runs ONE model at a time (models.yaml). When something else is holding
    VRAM, ollama offloads ours to CPU and a 7.7s reel becomes a 240s read timeout:
    a 2026-08-19 sync burned 40 minutes on 5 reels and dead-lettered 3 while
    another project's `gemma4:12b` sat resident. Not starting is the cheap fix.

    Set REELS_IGNORE_GPU=1 to run anyway.
    """
    if os.environ.get("REELS_IGNORE_GPU"):
        return []
    if need_gb is None:
        need_gb = vram_need(want)

    blockers = []
    mine = {want, want.split(":")[0]} - {""}
    warm = False
    for name, size, _proc in resident_models():
        if name in mine or name.split(":")[0] in mine:
            warm = True                 # already loaded, so it already fits
        else:
            blockers.append(f"ollama is holding {name} ({size})")

    state = gpu_state()
    if state:
        used, total, util = state
        free, want_gb = total - used, need_gb + GPU_HEADROOM_GB
        if need_gb and not warm and free < want_gb:
            blockers.append(f"only {free:.1f}GB free of {total:.1f}GB — "
                            f"{want or 'the model'} needs ~{want_gb:.1f}GB")
        if util >= GPU_BUSY_UTIL:
            blockers.append(f"GPU is {util:.0f}% busy — another job is running")
    return blockers


def status(registry: list[ModelEntry] | None = None) -> list[dict]:
    """Registry entries plus whether the built model is present."""
    have = installed_models()
    return [
        {
            "name": e.name, "tag": e.tag, "role": e.role, "vram_gb": e.vram_gb,
            "num_ctx": e.num_ctx, "notes": e.notes,
            "installed": e.built_name in have,
            "base_pulled": e.tag in have or e.tag.split(":")[0] in have,
        }
        for e in (registry if registry is not None else load_registry())
    ]


def write_modelfile(entry: ModelEntry, directory: Path = MODELFILE_DIR) -> Path:
    """A Modelfile that is only the base model plus the context it actually needs."""
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{entry.name}.Modelfile"
    p.write_text(
        f"# generated by `reels-scrap models pull {entry.name}` — do not edit by hand\n"
        f"# {entry.role}: {entry.notes}\n"
        f"FROM {entry.tag}\n"
        f"# six 720px frames + prompt overflow the stock 4096 context\n"
        f"PARAMETER num_ctx {entry.num_ctx}\n",
        encoding="utf-8",
    )
    return p


def _run(cmd: list[str], timeout: float) -> tuple[int, str]:
    # ollama's progress bars carry box-drawing bytes; Windows text mode defaults to
    # cp1252 and a reader thread dies on them mid-pull. Decode as utf-8, replace.
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stderr or r.stdout or "").strip()[:400]


def pull(entry: ModelEntry, timeout: float = 7200) -> dict:
    """`ollama pull` the base tag, then `ollama create` it at the wider context.

    Returns a result dict rather than raising, so pulling `all` reports every arm
    instead of stopping at the first bad tag.
    """
    if not shutil.which("ollama"):
        return {"name": entry.name, "ok": False, "error": "ollama not found on PATH"}
    if entry.build:
        # an explicit `build:` means the model was created by hand (reels-vision,
        # the control arm) — rebuilding it would change what the baseline measured
        return {"name": entry.name, "ok": True, "skipped": "pre-built model, left alone"}

    code, out = _run(["ollama", "pull", entry.tag], timeout)
    if code != 0:
        return {"name": entry.name, "ok": False, "error": f"pull {entry.tag}: {out}"}

    mf = write_modelfile(entry)
    code, out = _run(["ollama", "create", entry.name, "-f", str(mf)], timeout)
    if code != 0:
        return {"name": entry.name, "ok": False, "error": f"create {entry.name}: {out}"}
    return {"name": entry.name, "ok": True, "modelfile": str(mf)}


def as_profiles(registry: list[ModelEntry] | None = None,
                base_url: str = "http://127.0.0.1:11434/v1") -> dict[str, dict]:
    """Registry -> profile dicts. `profiles.resolve_profile` reads the registry
    directly, so this is for showing the shape, not for rewriting a config."""
    return {
        e.name: {
            "kind": "local", "model": e.built_name, "base_url": base_url,
            "num_ctx": e.num_ctx, "max_tokens": 1500, "timeout": 300.0,
            "notes": e.role,
        }
        for e in (registry if registry is not None else load_registry())
    }

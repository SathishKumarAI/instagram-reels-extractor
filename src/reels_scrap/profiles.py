"""Named model profiles — the unit the bench, the UI and `variants` all key on.

`vision_backend` was a closed set of three strings and `local` meant exactly one
model, so a second local model overwrote the first. A profile is a name plus the
settings to run one model, and a reel stores one variant per profile name.

Three names resolve without being declared anywhere, so every existing config,
caller and stored variant keeps working:

    claude-cli   the base config's claude path
    api          the same, via the Anthropic API
    local        extract.vision_local — falling back to config-local.yaml, which
                 is the only file that carries base_url on this machine
"""

from __future__ import annotations

from pathlib import Path

from .config import Config

# Names that work with no `vision_profiles` block at all. Also the two keys the
# 641 already-stored variants use, which is why they stay valid profile names.
IMPLICIT = ("claude-cli", "api", "local")

_LOCAL_CONFIG = "config-local.yaml"


def _base(base_config: str | Path) -> Config:
    return Config.load(str(base_config))


def _local_config(base_config: str | Path) -> Config:
    """The config that actually carries a local endpoint.

    `config.yaml` has no `vision_local.base_url`; `config-local.yaml` does. Rather
    than make every caller know that, look there when the base config is silent.
    """
    cfg = _base(base_config)
    if not cfg.extract.vision_local.base_url and Path(_LOCAL_CONFIG).exists():
        return Config.load(_LOCAL_CONFIG)
    return cfg


def _registry_profile(name: str):
    """A models.yaml entry, so a pulled model runs by name with no config edit."""
    from .modelreg import load_registry

    return next((e for e in load_registry() if e.name == name), None)


def list_profiles(base_config: str | Path = "config.yaml") -> list[str]:
    """Every profile name that resolves — declared, then registry, then implicit."""
    from .modelreg import load_registry

    declared = list(_base(base_config).extract.vision_profiles)
    registry = [e.name for e in load_registry() if e.name not in declared]
    seen = declared + registry
    return seen + [n for n in IMPLICIT if n not in seen]


def resolve_profile(name: str, base_config: str | Path = "config.yaml") -> Config:
    """A Config set up to run exactly one model.

    Declared profiles win over the implicit names, so `local` can be redefined
    without touching `extract.vision_local`.
    """
    base = _base(base_config)
    declared = base.extract.vision_profiles.get(name)

    if declared is None:
        entry = _registry_profile(name)
        if entry is not None:
            return _from_registry(entry, base_config)
        if name not in IMPLICIT:
            known = ", ".join(list_profiles(base_config))
            raise KeyError(f"unknown vision profile {name!r} — known: {known}")
        return _implicit(name, base_config)

    if declared.kind != "local":
        cfg = base
        cfg.extract.vision_backend = declared.kind
        if declared.model:
            cfg.extract.vision_model = declared.model
        return cfg

    # a local profile may inherit the endpoint rather than repeat it
    cfg = _local_config(base_config)
    lc = cfg.extract.vision_local
    lc.base_url = declared.base_url or lc.base_url
    lc.model = declared.model or lc.model
    lc.api_key = declared.api_key or lc.api_key
    lc.timeout = declared.timeout
    lc.max_tokens = declared.max_tokens
    cfg.extract.vision_backend = "local"
    # a fallback to Claude would silently fake this arm's result
    cfg.extract.vision_local_fallback = False
    if not lc.base_url:
        raise ValueError(
            f"vision profile {name!r} has no base_url — set it on the profile or in "
            f"extract.vision_local ({_LOCAL_CONFIG})"
        )
    return cfg


def _from_registry(entry, base_config: str | Path) -> Config:
    """Run a pulled model by its registry name, borrowing the local endpoint.

    Keeps `models.yaml` the single list of models and leaves the hand-written,
    heavily-commented `config-local.yaml` alone.
    """
    cfg = _local_config(base_config)
    lc = cfg.extract.vision_local
    lc.model = entry.built_name
    lc.timeout = max(lc.timeout, 300.0)
    # Reasoning models (qwen3-vl) think before they answer, and a 1500-token budget
    # is spent before the JSON closes — measured: two truncated replies at 1500.
    lc.max_tokens = max(lc.max_tokens, 4000)
    cfg.extract.vision_backend = "local"
    cfg.extract.vision_local_fallback = False
    if not lc.base_url:
        raise ValueError(
            f"profile {entry.name!r} needs a local endpoint — set "
            f"extract.vision_local.base_url ({_LOCAL_CONFIG})"
        )
    return cfg


def _implicit(name: str, base_config: str | Path) -> Config:
    if name == "local":
        cfg = _local_config(base_config)
        cfg.extract.vision_backend = "local"
        cfg.extract.vision_local_fallback = False
        if not cfg.extract.vision_local.base_url:
            raise ValueError(
                "profile 'local' has no endpoint — set extract.vision_local.base_url "
                f"(see {_LOCAL_CONFIG} / docs/LOCAL-VISION.md)"
            )
        return cfg
    cfg = _base(base_config)
    cfg.extract.vision_backend = name
    return cfg


def profile_model(name: str, base_config: str | Path = "config.yaml") -> str:
    """The model id a profile actually runs — for provenance and the scoreboard."""
    cfg = resolve_profile(name, base_config)
    return (
        cfg.extract.vision_local.model
        if cfg.extract.vision_backend == "local"
        else cfg.extract.vision_model
    )


# `compare.py`, `cli.py` and the sync endpoint asked for a backend before profiles
# existed. Same function, older name.
cfg_for_backend = resolve_profile

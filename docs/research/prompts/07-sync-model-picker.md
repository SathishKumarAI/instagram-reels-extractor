# Prompt 07 — pick any installed model for a sync

Written before the code. Raised by the owner: "why can't I manually select the
model I want to run on the sync right now?"

---

**Role.** You are closing a gap between two surfaces of the same app. The bench
can run seven models; the Sync tab can run three. That difference is an accident
of when each was written, not a decision.

<context>
`POST /api/sync` validates `backend in {claude-cli, api, local}` and the job
resolves that name through `cfg_for_backend`. Profiles (phase 1) already resolve
any registry model by name, and `GET /api/profiles` lists them with an
`installed` flag. The Sync tab (`web/src/views/SyncPage.tsx`) and the Sources tab
both hold a `SyncBackend` union of exactly three strings and render three fixed
radio-style options.
</context>

<task>
Any installed model can run a sync, chosen in the UI, with the same list the
Compare tab shows.
</task>

<steps>
1. `/api/sync` accepts any name `list_profiles()` resolves; the 400 names the
   valid options instead of repeating a hard-coded set.
2. Reject a local model that is in the registry but not pulled — with the exact
   `models pull` command in the message.
3. Sync tab: replace the three fixed options with the profile list, grouping
   cloud and local, marking the not-installed ones, and showing the model id
   under each name.
4. Sources tab: same picker, same source of truth.
5. `SyncStatus.backend` already carries whatever ran, so the run strip needs no
   change beyond displaying the profile name.
</steps>

<must>
- A model that is not installed cannot be selected, and the API refuses it too —
  the UI is not the only guard.
- The default stays `claude-cli`, so an unattended scheduled sync is unchanged.
- One API test: an unknown profile is a 400 that names the known profiles.
</must>

<must-not>
- Do not fork a second profile list in the frontend.
- Do not let a sync silently fall back to a different model than the one picked.
</must-not>

---

## Outcome

`/api/sync` profile-aware, `ModelSelect` shared by the Sync and Sources tabs,
`tests/test_api.py::test_sync_rejects_unknown_profile`.

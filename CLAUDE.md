# Stella Rain: moderation

Public moderation data for Stella Rain (ADR-025). The game downloads `blocklist.json` from
`main` by raw URL at startup and hides the listed stages and creators for everyone. Players
report stages and creators with the in-game **Report** button: mainly by email to the
moderation mailbox, or, if they choose, as an issue here.

## This repository is public

- How moderation is decided (thresholds, volumes, strategy) is discussed in
  `stella-rain/app` issues, never here.
- Reports may contain what a reporter wrote; never add personal data to issues, commits or
  the blocklist, and never copy report text into commits.
- Data is CC0 1.0.

## `blocklist.json`

```json
{
  "version": 12,
  "updated": "2026-10-08",
  "blocked_stages": ["alice/my-stages@bad-stage@v1"],
  "blocked_hashes": ["<sha-256 of stage + replay>"],
  "blocked_creators": ["spammer123"]
}
```

- `blocked_stages`: stage codes, `owner/repo@stage-id@vN`. `blocked_creators`: GitHub logins.
- `blocked_hashes`: the content hash the game and catalog record for a stage with its replay
  (SHA-256, lowercase hex). It keeps a stage blocked as a share code or republished under
  another code. Block a stage by code and by hash.
- Every change increases `version` by 1 and sets `updated` to the date (UTC).
- Keep every list sorted and free of duplicates, so diffs show exactly what changed.
- A malformed file reaches every player at once (the game is meant to keep its last good copy,
  but new blocks stop applying). Validate before committing: `python3 -m json.tool blocklist.json`.

## Handling a report

1. **Only Kade decides** what is blocked or unblocked. Claude may summarise a report and
   prepare the change, but never adds or removes an entry without Kade's decision on that entry.
2. Block: add the entry, bump `version` and `updated`, commit with a subject that names the
   issue (`Block one stage reported in #12`), and close the issue with a short neutral comment.
   An email report never reaches this repository: Kade relays the decision, and the subject
   says `reported by email`. Nothing from the email (address, name, text) goes into a commit,
   an issue or the blocklist.
3. Unblock: remove the entry the same way; say why in the commit body without personal details.
4. Not acted on: close the issue with a short neutral comment.

## Gates

| Part | Gate |
|---|---|
| `blocklist.json` | `python3 -m json.tool blocklist.json`; version bumped; lists sorted |
| `CLAUDE.md` | `python3 ../.github/scripts/claude_md_check.py .` (CI runs it too) |

## State and version control

- Moderation issues are not synced to the organization Project (ADR-044); development work on
  this repository is tracked in `stella-rain/app` issues.
- **Local and cloud sessions** work on `claude/<task>`; a task may hold several commits and
  gets one PR. Kade merges it (see Overrides). A local session opens the PR with Kade's `gh`
  login; without it, it prints the commands for Kade.
- Zip deliveries (needed on the Windows PC only) are laid out from the `stella-rain` root.

## Overrides of global rules

- **No auto-merge.** A cloud session opens a PR and Kade merges it; GitHub auto-merge stays
  off. A malformed `blocklist.json` reaches every player at once, and only Kade decides what
  is blocked.

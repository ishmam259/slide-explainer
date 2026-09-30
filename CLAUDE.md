# CLAUDE.md

@AGENTS.md

The rules above apply to every agent. This section adds Claude Code specifics.

## Before UI work

Read `DESIGN.md` in full before creating or changing any screen or component. It is deliberately not imported here (it's large); load it when the task touches UI. For design direction, critique, or polish, use the installed design skills rather than improvising:

| Need | Use |
|---|---|
| Build or restyle UI in this design system | `/impeccable` (audit, critique, polish, typeset, colorize, harden…) and `/frontend-design:frontend-design` |
| Add or fix shadcn components | `shadcn` skill |
| Accessibility check | `ecc:accessibility` / `ecc:a11y-architect` agent |
| Check a DESIGN.md token change | `designmd lint DESIGN.md` |

## Spec-driven workflow

Spec Kit is this project's workflow. Use its skills in order for features:

`/speckit-constitution` (once) → `/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

- Use `/grill-me` to stress-test a plan or spec before implementing it.
- GSD (`/gsd-*`) is also installed globally. Don't start a GSD `.planning/` workflow in this repo unless the user asks — it would duplicate Spec Kit's `specs/`.

## Environment

- Windows 11. Primary shell is PowerShell; use PowerShell syntax (`$env:VAR`, `;` / `&&`) unless running a POSIX script via Bash.
- The Spec Kit CLI is not on PATH: `C:\Users\16IRL8\AppData\Roaming\Python\Python314\Scripts\specify.exe`.
- The DESIGN.md linter binary is `designmd` (not `design.md`, which Windows treats as a file).
- ECC's GateGuard hook asks for facts before the first shell command and before creating new files — answer it directly, then retry.

## Working style

- Verify before claiming done: run type-check, lint, and relevant tests, and state what you ran.
- Keep changes scoped to the request; mention unrelated issues instead of fixing them silently.
- Update `AGENTS.md` (not this file) when project-wide commands, structure, or conventions change, so every agent stays in sync. Put only Claude-specific notes here.

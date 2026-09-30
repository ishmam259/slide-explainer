---
version: alpha
name: Agentic
description: Visual identity for an agentic AI tool built on Next.js + shadcn/ui. Vercel-inspired — a stark ink-on-near-white (and near-white-on-ink in dark mode) system with Geist type, hairline borders, stacked subtle shadows, and a mono voice for everything technical. Colour is reserved for state (running, success, error, warning) and a single hero-scale gradient.

colors:
  primary: "#171717"
  on-primary: "#ffffff"
  ink: "#171717"
  body: "#4d4d4d"
  mute: "#888888"
  hairline: "#ebebeb"
  hairline-strong: "#a1a1a1"
  canvas: "#ffffff"
  canvas-soft: "#fafafa"
  canvas-soft-2: "#f5f5f5"
  link: "#0070f3"
  link-deep: "#0761d1"
  link-bg-soft: "#d3e5ff"
  focus-ring: "#0070f3"
  success: "#0a7c3e"
  success-soft: "#d9f5e4"
  error: "#ee0000"
  error-soft: "#f7d4d6"
  error-deep: "#c50000"
  warning: "#f5a623"
  warning-soft: "#ffefcf"
  warning-deep: "#ab570a"
  running: "#7928ca"
  running-soft: "#ece3fa"
  gradient-start: "#007cf0"
  gradient-mid: "#7928ca"
  gradient-end: "#ff0080"
  selection-bg: "#171717"
  selection-fg: "#f2f2f2"
  dark-canvas: "#0a0a0a"
  dark-canvas-soft: "#111111"
  dark-canvas-soft-2: "#1a1a1a"
  dark-ink: "#ededed"
  dark-body: "#a1a1a1"
  dark-mute: "#737373"
  dark-hairline: "#262626"
  dark-hairline-strong: "#404040"
  dark-primary: "#ededed"
  dark-on-primary: "#0a0a0a"
  dark-link: "#3291ff"
  dark-running: "#a67ef0"

typography:
  display-xl:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 48px
    fontWeight: 600
    lineHeight: 48px
    letterSpacing: -2.4px
  display-lg:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 32px
    fontWeight: 600
    lineHeight: 40px
    letterSpacing: -1.28px
  display-md:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 24px
    fontWeight: 600
    lineHeight: 32px
    letterSpacing: -0.96px
  display-sm:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 20px
    fontWeight: 600
    lineHeight: 28px
    letterSpacing: -0.6px
  body-lg:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 18px
    fontWeight: 400
    lineHeight: 28px
  body-md:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
  body-sm:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
    letterSpacing: -0.28px
  body-sm-strong:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 20px
    letterSpacing: -0.28px
  caption:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  caption-mono:
    fontFamily: Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
  code:
    fontFamily: Geist Mono, ui-monospace, SFMono-Regular, Menlo, monospace
    fontSize: 13px
    fontWeight: 400
    lineHeight: 20px
  button-md:
    fontFamily: Geist, Inter, system-ui, -apple-system, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 20px

rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 40px
  3xl: 48px
  4xl: 64px
  5xl: 96px

components:
  app-header:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    height: 56px
    padding: "0px {spacing.md}"
  sidebar:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    width: 260px
  sidebar-row:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "{spacing.xs} {spacing.sm}"
    height: 32px
  sidebar-row-active:
    backgroundColor: "{colors.canvas-soft-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm-strong}"
    rounded: "{rounded.sm}"
    padding: "{spacing.xs} {spacing.sm}"
    height: 32px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: "0px {spacing.sm}"
    height: 36px
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: "0px {spacing.sm}"
    height: 36px
  button-ghost:
    textColor: "{colors.body}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: "0px {spacing.sm}"
    height: 36px
  button-destructive:
    backgroundColor: "{colors.error}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.sm}"
    padding: "0px {spacing.sm}"
    height: 36px
  form-input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "0px {spacing.sm}"
    height: 40px
  card:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.lg}"
  badge:
    backgroundColor: "{colors.canvas-soft-2}"
    textColor: "{colors.body}"
    typography: "{typography.caption}"
    rounded: "{rounded.full}"
    padding: "0px {spacing.xs}"
    height: 20px
  chat-composer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm}"
  message-user:
    backgroundColor: "{colors.canvas-soft-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.sm} {spacing.md}"
  message-agent:
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    padding: "0px"
  tool-call-card:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.body}"
    typography: "{typography.caption-mono}"
    rounded: "{rounded.md}"
    padding: "{spacing.xs} {spacing.sm}"
  run-status-running:
    backgroundColor: "{colors.running-soft}"
    textColor: "{colors.running}"
    typography: "{typography.caption-mono}"
    rounded: "{rounded.full}"
    padding: "0px {spacing.xs}"
  run-status-success:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    typography: "{typography.caption-mono}"
    rounded: "{rounded.full}"
    padding: "0px {spacing.xs}"
  run-status-error:
    backgroundColor: "{colors.error-soft}"
    textColor: "{colors.error-deep}"
    typography: "{typography.caption-mono}"
    rounded: "{rounded.full}"
    padding: "0px {spacing.xs}"
  approval-card:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  code-block:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.code}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  command-palette:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.lg}"
    padding: "{spacing.xs}"
    width: 640px
  toast:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
  empty-state:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: "{spacing.3xl}"
---

## Overview

This is a tool for people who direct AI agents: they write a goal, watch the agent plan and call tools, approve risky steps, and inspect what it produced. The interface should feel like a precise instrument, not a toy. It borrows Vercel's developer-platform language — ink on near-white, Geist type, hairline borders, whisper-quiet shadows — because that language signals *engineered, trustworthy, fast*.

Two rules shape everything:

1. **Colour means state.** The UI is grayscale. Colour appears only when it carries information: violet = the agent is running, green = done, red = failed, amber = waiting on the human. If something is coloured and not stateful, it's wrong.
2. **Mono means machine.** Anything the agent or system emitted verbatim — tool names, arguments, IDs, logs, file paths, token counts, durations — is set in Geist Mono. Human-facing prose is Geist sans. The font switch tells the user whose voice they're reading.

The product is used for long sessions, so it ships with a first-class dark mode (see *Colors → Dark mode*). Both themes are equal citizens; neither is an afterthought.

**Key characteristics**
- Near-monochrome ink/gray palette with four semantic state colours.
- Geist (sans) for UI and prose, Geist Mono for all machine output.
- 6 px base radius for controls, 8 px for cards, 12 px for large surfaces (composer, dialogs, palette).
- Hairline borders do the structural work; shadows are stacked and barely visible.
- Dense by default (14 px UI text, 32–36 px control heights) with generous whitespace around the conversation column.

## Colors

### Ink & surfaces (light)
- **Primary / Ink** `{colors.primary}` `#171717` — primary buttons, headings, body text on light surfaces.
- **Body** `{colors.body}` `#4d4d4d` — secondary text, inactive nav, descriptions.
- **Mute** `{colors.mute}` `#888888` — placeholders, timestamps, metadata. Never for anything the user must read to act.
- **Canvas** `{colors.canvas}` `#ffffff` — cards, dialogs, composer, main content.
- **Canvas Soft** `{colors.canvas-soft}` `#fafafa` — app background, sidebar, tool-call cards.
- **Canvas Soft 2** `{colors.canvas-soft-2}` `#f5f5f5` — user message bubbles, active sidebar row, hover fills.
- **Hairline** `{colors.hairline}` `#ebebeb` — every 1 px border and divider. **Hairline Strong** `#a1a1a1` for input hover and emphasised dividers.

### State colours
| State | Token | Soft background | Use |
|---|---|---|---|
| Running | `{colors.running}` `#7928ca` | `{colors.running-soft}` | Agent is thinking / streaming / executing a tool. Pair with a pulse or spinner. |
| Success | `{colors.success}` `#0a7c3e` | `{colors.success-soft}` | Run completed, tool call succeeded, check passed. |
| Error | `{colors.error}` `#ee0000` | `{colors.error-soft}` | Run failed, tool error, destructive action. |
| Warning / needs you | `{colors.warning}` `#f5a623` | `{colors.warning-soft}` | Awaiting human approval, rate-limited, degraded. |
| Link / focus | `{colors.link}` `#0070f3` | `{colors.link-bg-soft}` | Inline links and the keyboard focus ring. Not a state colour. |

State is never communicated by colour alone — always pair with an icon and/or a text label (`running`, `done`, `failed`, `needs approval`).

### Gradient
`{colors.gradient-start}` → `{colors.gradient-mid}` → `{colors.gradient-end}` (blue → violet → pink). Used **only** at hero scale: the marketing landing hero and the empty "new session" screen backdrop, at low opacity behind content. Never on buttons, icons, text, or borders.

### Dark mode
Dark mode inverts polarity rather than inventing new colours:

| Role | Light | Dark |
|---|---|---|
| Background (app) | `canvas-soft` `#fafafa` | `dark-canvas` `#0a0a0a` |
| Surface (card) | `canvas` `#ffffff` | `dark-canvas-soft` `#111111` |
| Inset / hover | `canvas-soft-2` `#f5f5f5` | `dark-canvas-soft-2` `#1a1a1a` |
| Text | `ink` `#171717` | `dark-ink` `#ededed` |
| Secondary text | `body` `#4d4d4d` | `dark-body` `#a1a1a1` |
| Muted text | `mute` `#888888` | `dark-mute` `#737373` |
| Border | `hairline` `#ebebeb` | `dark-hairline` `#262626` |
| Primary button | `#171717` / white text | `#ededed` / `#0a0a0a` text |
| Link | `#0070f3` | `dark-link` `#3291ff` |
| Running | `#7928ca` | `dark-running` `#a67ef0` |

In dark mode, soft state backgrounds become the state colour at ~15 % opacity over the surface. Code blocks stay dark in both themes (in dark mode use `dark-canvas-soft-2` with a hairline border so they don't disappear).

### shadcn/ui token mapping
Implement tokens as CSS variables in `app/globals.css` and let shadcn components consume them. Do not hard-code hex values in components.

| shadcn variable | Light | Dark |
|---|---|---|
| `--background` | `#fafafa` | `#0a0a0a` |
| `--foreground` | `#171717` | `#ededed` |
| `--card` / `--popover` | `#ffffff` | `#111111` |
| `--card-foreground` / `--popover-foreground` | `#171717` | `#ededed` |
| `--primary` | `#171717` | `#ededed` |
| `--primary-foreground` | `#ffffff` | `#0a0a0a` |
| `--secondary` / `--muted` / `--accent` | `#f5f5f5` | `#1a1a1a` |
| `--secondary-foreground` / `--accent-foreground` | `#171717` | `#ededed` |
| `--muted-foreground` | `#4d4d4d` | `#a1a1a1` |
| `--border` / `--input` | `#ebebeb` | `#262626` |
| `--ring` | `#0070f3` | `#3291ff` |
| `--destructive` | `#ee0000` | `#ff4d4d` |
| `--radius` | `0.5rem` (8 px; shadcn derives sm/md/lg from it) | same |

Add project-specific variables for state: `--running`, `--running-soft`, `--success`, `--success-soft`, `--warning`, `--warning-soft`, plus Tailwind theme entries so utilities like `text-running` and `bg-success-soft` exist.

## Typography

**Families.** Geist and Geist Mono — both open source (SIL OFL). Load with the `geist` npm package (`GeistSans`, `GeistMono`) via `next/font`, exposed as `--font-sans` and `--font-mono`. Fallbacks: Inter and JetBrains Mono.

**Weights.** 400 body, 500 buttons/emphasis, 600 headings. Never 700+.

| Token | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `display-xl` | 48/48 | 600 | -2.4px | Marketing hero only. |
| `display-lg` | 32/40 | 600 | -1.28px | Page titles on marketing / settings landing. |
| `display-md` | 24/32 | 600 | -0.96px | In-app page titles, dialog titles on large dialogs. |
| `display-sm` | 20/28 | 600 | -0.6px | Section headings, card titles. |
| `body-lg` | 18/28 | 400 | 0 | Marketing lead paragraphs. |
| `body-md` | 16/24 | 400 | 0 | Chat messages (user and agent), composer input. |
| `body-sm` | 14/20 | 400 | -0.28px | Default UI text: nav, tables, forms, settings. |
| `body-sm-strong` | 14/20 | 500 | -0.28px | Labels, active nav, table emphasis. |
| `caption` | 12/16 | 400 | 0 | Helper text, timestamps. |
| `caption-mono` | 12/16 | 400 | 0 | Tool names, IDs, status pills, token/latency counters, eyebrows. |
| `code` | 13/20 | 400 | 0 | Code blocks, logs, JSON arguments, diffs. |

**Principles**
- Sentence case everywhere. No all-caps except `caption-mono` eyebrows, which may be uppercase with +0.04em tracking.
- Negative tracking on display sizes is part of the voice — don't reset it.
- Chat content is 16 px for readability; chrome around it is 14 px. This size step separates *content* from *interface*.
- Render agent markdown with a constrained prose style: headings cap at `display-sm`, lists and tables use `body-md`, inline code uses `code` on `canvas-soft-2` with `rounded.xs`.
- Numbers that update live (tokens, cost, elapsed time) use `font-variant-numeric: tabular-nums` so they don't jitter.

## Layout

**Spacing.** 4 px base unit; use only the `spacing` tokens (Tailwind's default scale maps cleanly: 1 = 4 px, 2 = 8 px, 3 = 12 px, 4 = 16 px, 6 = 24 px, 8 = 32 px…).

**App shell.**
- `app-header` 56 px tall, hairline bottom border, full width.
- `sidebar` 260 px on the left (sessions / agents / history), collapsible to 56 px icon rail; becomes a sheet on mobile.
- Main area: conversation column centred at **max-width 768 px** with `spacing.md` gutters. Optional right-hand **inspector panel** (360–480 px, resizable) for run details, tool I/O, files, and traces.
- Composer is sticky to the bottom of the conversation column with a `canvas-soft` fade above it.

**Density.** In-app screens are dense: 32 px rows, 36 px buttons, 40 px inputs, 12–16 px card padding for list items, 24 px for standalone cards. Marketing pages are airy: 64–96 px between sections, max content width 1200 px.

**Breakpoints.**
| Name | Width | Behaviour |
|---|---|---|
| Mobile | < 640 px | Sidebar becomes a sheet; inspector becomes a bottom drawer; composer full width. |
| Tablet | 640–1023 px | Sidebar collapses to icon rail; inspector opens as overlay. |
| Desktop | 1024–1439 px | Sidebar + conversation; inspector docked when opened. |
| Wide | ≥ 1440 px | Sidebar + conversation + inspector all docked. |

Touch targets are at least 44×44 px on touch devices (pad the hit area, not the visual).

## Elevation & Depth

Structure comes from hairlines; shadows are a whisper.

| Level | Treatment | Use |
|---|---|---|
| 0 | none | App background, sidebar, inline tool-call cards. |
| 1 | 1 px hairline border | Cards, inputs, composer (resting). |
| 2 | `0 1px 1px #00000005, 0 2px 2px #0000000a` + hairline | Hovered cards, composer (focused). |
| 3 | `0 2px 2px #0000000a, 0 8px 16px -4px #0000000a` + hairline | Popovers, dropdowns, toasts. |
| 4 | `0 1px 1px #00000005, 0 8px 16px -4px #0000000a, 0 24px 32px -8px #0000000f` + hairline | Dialogs, command palette, sheets. |

In dark mode drop the shadows and rely on hairline + a one-step-lighter surface for elevation.

Overlays (dialogs, sheets) use a `#000000` scrim at 40 % (light) / 60 % (dark), no blur.

## Shapes

| Token | Value | Use |
|---|---|---|
| `rounded.xs` | 4 px | Inline code, kbd hints, checkboxes. |
| `rounded.sm` | 6 px | Buttons, inputs, sidebar rows, menu items. |
| `rounded.md` | 8 px | Cards, tool-call cards, code blocks, toasts. |
| `rounded.lg` | 12 px | Composer, user message bubbles, dialogs, command palette. |
| `rounded.full` | 9999 px | Badges, status pills, avatars, icon-only round buttons. |

No pill-shaped primary buttons inside the app — app buttons are 6 px. The 9999 px pill is for status and metadata only.

**Icons.** Lucide (shadcn default), 16 px in UI chrome, 14 px inside pills, 1.5 px stroke, `currentColor`. Never coloured unless the icon *is* a state indicator.

## Components

Build on shadcn/ui primitives; restyle via tokens rather than forking components.

### Controls
- **`button-primary`** — ink fill, white text, 36 px, 6 px radius. One per view: the single most important action (Run, Send, Save).
- **`button-secondary`** — white fill, hairline border, ink text. Alternatives and Cancel.
- **`button-ghost`** — no fill, body text, `canvas-soft-2` on hover. Toolbars and row actions.
- **`button-destructive`** — red fill. Only for irreversible actions, always behind a confirmation.
- **`form-input`** — 40 px, hairline border, border goes `hairline-strong` on hover and gets a 2 px `focus-ring` outline (with 2 px offset) on focus.
- **`badge`** — 20 px pill, `caption` text, for counts and metadata.

### Agent surfaces (signature components)
- **`chat-composer`** — 12 px radius multi-line input with hairline border; grows to ~40 % viewport height, then scrolls. Bottom row: attachment and tool/model pickers (ghost buttons, `caption-mono` labels) on the left, Send (`button-primary`, icon + label) on the right; Send becomes **Stop** (secondary, square icon) while running. `Enter` sends, `Shift+Enter` inserts newline.
- **`message-user`** — `canvas-soft-2` bubble, 12 px radius, right-aligned, max 85 % column width.
- **`message-agent`** — no bubble; full-width prose on the canvas, preceded by a small agent avatar + name in `body-sm-strong`. Streaming text shows a 2 px ink caret that blinks at 1 s.
- **`tool-call-card`** — collapsed by default: one row with status icon, tool name in `caption-mono`, a one-line argument summary, and duration right-aligned (`tabular-nums`). Expands to show arguments and result as `code-block`s. Consecutive tool calls group into a single "N steps" disclosure.
- **`run-status-*` pills** — `running` (violet, animated dot), `success` (green check), `error` (red x), plus `queued` (neutral `badge`) and `needs approval` (amber). Mono label, full radius.
- **`approval-card`** — amber-soft card with amber left border (2 px) when the agent requests permission: states the exact action and target in mono, then `button-primary` "Approve" and `button-secondary` "Deny". Never auto-dismiss.
- **`code-block`** — dark surface in both themes, `code` type, 8 px radius, header row with language label (`caption-mono`) and copy button. Diffs use success-soft / error-soft line backgrounds.
- **Reasoning / thinking** — collapsed disclosure labelled "Thought for 12s" in `caption` mute; expanded content in `body-sm`, `body` colour, left hairline rule.
- **`command-palette`** — shadcn `Command` in a 640 px dialog, 12 px radius, level-4 elevation; `⌘K` / `Ctrl+K` everywhere.
- **Inspector panel** — tabs (`Overview`, `Steps`, `Files`, `Logs`) using underline tabs, `body-sm-strong` active label, 2 px ink underline.
- **`toast`** — Sonner, bottom-right, level-3 elevation, 4 s auto-dismiss except errors (persist until dismissed).
- **`empty-state`** — centred in `canvas-soft`, a 1-sentence heading in `display-sm`, one line of `body` text, one primary action, and 3–4 example prompts as secondary buttons.

### Motion
- Durations: 120 ms (hover, press), 200 ms (popovers, disclosures), 300 ms (sheets, dialogs). Easing `cubic-bezier(0.2, 0, 0, 1)`.
- Only animate opacity and transform. No bouncing, no spring overshoot.
- Running indicators: a 1.4 s opacity pulse on the status dot; streaming text appears token-by-token without per-token animation.
- Respect `prefers-reduced-motion`: disable pulses and slide transitions, keep instant opacity changes.

### Voice & copy
- Plain, specific, and calm. "Run failed: the GitHub token is missing the `repo` scope." not "Oops! Something went wrong."
- Buttons are verbs: Run, Approve, Deny, Retry, Copy. Not "OK".
- Say what the agent did in past tense and what it's doing in present progressive: "Searched 4 files", "Editing `page.tsx`…".
- Show cost, tokens, and elapsed time where the user is making a decision about running something — in mono, never hidden.

## Do's and Don'ts

### Do
- Keep the UI grayscale; spend colour only on state.
- Put every machine-emitted string (tool names, args, paths, IDs, logs) in Geist Mono.
- Pair every state colour with an icon or label for accessibility.
- Show the agent's work progressively: status → steps → result, each collapsible.
- Make destructive or external actions explicit and require human approval via `approval-card`.
- Use shadcn primitives + CSS variables; keep both themes in sync from the same token table.
- Meet WCAG 2.2 AA: 4.5:1 text contrast, visible focus ring on every interactive element, full keyboard operation of the composer, palette, and approval flow.

### Don't
- Don't add a new accent or brand colour. Violet, green, red, amber are state — nothing else gets colour.
- Don't use the gradient anywhere except hero-scale backdrops.
- Don't use pill-shaped primary buttons in the app, or weights above 600.
- Don't put chat prose in mono or machine output in sans.
- Don't use heavy single drop-shadows, glassmorphism, or background blur.
- Don't hide failures: never collapse an errored step by default, never swallow a tool error into a generic message.
- Don't animate layout properties (width/height/top/left) or run motion when `prefers-reduced-motion` is set.

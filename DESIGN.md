---
name: AutoScout
description: Local FRC video review workspace.
colors:
  surface: "#f6f7f4"
  paper: "#fff"
  ink: "#202a25"
  muted: "#56625a"
  line: "#dce2da"
  accent: "#176442"
  accent-soft: "#e7f1e9"
  red: "#ad3434"
  blue: "#225f9c"
  focus: "#277754"
typography:
  body:
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "14px"
    fontFeature: "tabular-nums"
  headline:
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontSize: "16px"
    fontWeight: 700
  label:
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.6
rounded:
  input: "5px"
  control: "6px"
  video: "7px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.input}"
    padding: "7px 9px"
  filter-selected:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
    padding: "7px 10px"
---

# Design System: AutoScout

## Overview

**Creative North Star: "The automatic scouting workspace"**

A light neutral workspace puts automatic estimates and their recorded evidence first. Optional manual validation follows the automatic results. Dense controls, restrained forest green actions, and flat divided sections support sustained desktop review. This records the built interface; no reference composition was supplied.

**Key Characteristics:**

- Automatic estimates lead a persistent processing queue and video evidence.
- Compact system typography and tabular measurements.
- Explicit processing, estimated, unassigned, reviewed, and official-data labels.

## Colors

Forest green marks primary actions, recording readiness, and selection. Paper and surface neutrals separate regions; ink and muted text establish hierarchy; line supplies boundaries. Red and blue identify alliances, with red also used for rejection. Focus green supplies keyboard outlines. A dark video stage frames footage.

## Typography

Inter is preferred when installed; otherwise the platform sans-serif is used. No webfont is loaded. Match headlines use the headline role; the library title is 23px. Section titles use the title role. Supporting metadata ranges from 10–13px. Help text uses a relaxed line height (1.6) and a maximum measure (75ch).

## Layout

The desktop header is 65px high. A sticky 248px queue sits beside a workspace capped at 1700px, with 28px vertical and 32px horizontal padding. The full-width automatic dashboard precedes video and optional manual validation. Alliance totals and runtime wrap across a row; team and volley tables scroll within a 320px maximum height. Video and scouting form use a flexible column plus a 270px sidebar, separated by 24px. Video keeps a 16:9 stage. Observations and comparison follow below.

At 1700px and above the sidebar grows to 310px and video height is capped at 640px. At 1150px and below the scouting panel moves below footage in two columns; observation actions move below their text. At 900px and below the queue becomes an upper horizontal scroller and the workspace uses one column; header export links and the queue footer are hidden. At 560px and below the scouting panel stacks, the header is 58px high, and workspace padding is 19px by 16px. Inputs use 16px text and 40px minimum height; playback and observation buttons use 38px minimum height. These are actual sizes, not a blanket 44px touch-target guarantee. Comparison tables scroll when needed.

## Elevation & Depth

No shadows are used. Background tones, thin borders, and spacing distinguish sections. Selected queue items use paper and a border. Button backgrounds transition over 150ms with ease timing. Reduced-motion preference removes transitions.

## Shapes

Controls have gently rounded corners, with slightly tighter inputs and softer video clipping. Sections remain open and divided by single-pixel rules rather than decorative cards. Small circular dots mark the wordmark and local workspace status.

## Components

- **Buttons:** Primary green commits optional review actions. Automatic processing has no start button; the diagnostic sample button remains hidden. Paper and transparent variants support secondary actions. Standard minimum height is 36px; compact controls vary. Hover changes the background. Disabled controls use half opacity. Keyboard focus uses a 2px outline with 3px offset.
- **Fields:** White bordered inputs, selects, and textareas retain visible labels. Focus changes the border to the action accent. Notes resize vertically.
- **Match navigation:** Two-column rows pair labels and scores with recording availability, alliance, and queued, processing, ready, or failed analysis status. Active rows use paper and a border. Narrow layouts scroll horizontally. Long labels wrap; scores remain dense.
- **Review filters:** Candidates, Accepted, and Rejected use explicit selected state and aria-pressed. Counts separately state pending and accepted totals.
- **Automatic dashboard:** Blue/red estimated fuel and processing time lead a six-team contribution table with one explicit unassigned row per alliance. Unavailable totals say “Pending”; unknown team contributions say “Unresolved.” Queue progress includes processing, complete, attention, and resume states. Selected-match results refresh every five seconds; queue entries refresh every fifteen seconds. Late responses from other match selections do not replace current evidence.
- **Volley evidence:** A disclosure reveals video time, alliance, score delta, visual crossings, and unassigned counts, plus the full analysis JSON link. An empty table explains that volleys appear after analysis completes.
- **Detection evidence:** Separate toggles control fuel boxes and robot boxes; robot boxes are enabled by default beside playback controls. Robot labels use opaque dark backgrounds, light blue/red alliance colors, and amber dashed boxes for unknown identities. Labels move to avoid overlap. Fuel confidence labels are limited to the ten strongest detections; robots show a team number or temporary track ID. GPU metadata, export, and first-detection seek support inspection; detections are not made shots or robot scores.
- **Video and overlays:** Native video controls remain available. Playback shortcuts, attachment, and download sit below footage. The detection overlay supports optional robot selection for identity tagging.
- **Observation rows:** Timestamped evidence, source and alliance labels, attribution, and Accept/Update/Reject/Restore actions stay together. Empty states identify the selected review state and a next action.
- **Optional manual validation and comparison:** Divided statistics and a compact table distinguish reviewed observations from official alliance data. Unreviewed statistics say “Not reviewed”; unavailable official data remains unknown.
- **Feedback:** Inline notices and progress appear above the workspace. Errors use a warm red treatment and textual explanation.

## Do's and Don'ts

- **Do** keep automatic estimates, raw crossings, reviewed observations, and official alliance data distinct.
- **Do** preserve native video controls, visible focus, and reduced-motion behavior.
- **Do** organize dense information with borders and tonal surfaces.
- **Don't** present detections or estimated robot contributions as validated makes or official individual scores.
- **Don't** substitute zero for missing or unreviewed data.
- **Don't** add decorative shadows, gradients, or hero metrics to this review surface.


## Simplified scoring and robot identity review

The primary flow is a single six-team scoring table followed by full-width playback. Video fuel estimates and Statbotics EPA expectations occupy separate columns with explicit units; unavailable data stays unavailable. Unassigned alliance fuel remains visible. Alliance totals, raw detection diagnostics, manual observations, and comparison tables are closed disclosures by default.

“Identify a robot in playback” opens an optional inline editor. A paused robot box or keyboard-accessible visible-track selector supplies the track; the reviewer chooses a roster team and bounded video interval. Saved tags offer Edit and Undo. Tags identify existing evidence rather than invent scoring. Native playback controls remain accessible below the canvas hit area. Automatic processing requires no tagging or review action.

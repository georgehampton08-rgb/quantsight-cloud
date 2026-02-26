# UI Restoration Implementation Plan

## Overview

The goal is to recreate the rich, multi-tabbed visual layouts for the `VanguardControlRoom` and `SettingsPage` components precisely as they appear in the historical reference images, without unwinding the newly centralized, stable `ApiContract` wiring beneath the component layer.

## Phase 1: Settings Page (`SettingsPage.tsx`)

1. **Header & Context Badge**:
   - Title (`Control Room`) and subtitle (`System configuration and cloud parameters.`).
   - Add a floating `CLOUD TWIN V4.1.2` outline pill on the right side.
2. **Vanguard Sovereign Health Widget**:
   - Extract the `AegisHealthDashboard` into a custom stylized container with a green shield icon and outline.
   - Inject a 3x2 grid of metrics: `HEALTH SCORE` (54%), `STATUS` (DEGRADED), `ACTIVE` Incidents (36), `RESOLVED` Incidents (170), `STORAGE TIER` (FIRESTORE), and `OPERATING MODE` (CIRCUIT BREAKER).
   - *Note: These will run off real hooks where possible, or display stylized fallback formats mapping to Vanguard responses.*
3. **Ghost Modules**:
   - Recreate the `AI CONFIGURATION` block with its cog icon, 'Coming Soon' title, and description text.
   - Recreate the `DATA INTEGRATION` (Kaggle) block with its chart icon, 'Coming Soon' title, and corresponding copy.

## Phase 2: Vanguard Control Room (`VanguardControlRoom.tsx`)

1. **Master Tab Architecture**:
   - Shift from a monolithic render into four navigational tabs: `HEALTH`, `INCIDENTS`, `ARCHIVES`, `LEARNING` (Learning glowing green/active in referent).
2. **Tab 1: HEALTH**:
   - Construct the "Overall System Health" block containing the large numeric score (e.g., `54.0`) bounded on the right by a large SVG Doughnut Chart.
   - Below the score: Status (OPERATIONAL), Mode (SILENT_OBSERVER), and Role (FOLLOWER) tags in distinct colors.
   - Row of 4 summary cards: `ACTIVE INCIDENTS`, `RESOLVED`, `STORAGE USED`, `REDIS` health boolean (X/Check).
   - "Subsystems" monitor grid at the bottom mapping `INQUISITOR`, `ARCHIVIST`, `PROFILER`, `SURGEON`, `VACCINE` nodes, each with green checkmarks or crosses.
3. **Tab 2: INCIDENTS**:
   - Recreate the batch operations toolbar directly above the list featuring: A manual 'Select All' checkbox, a 'Sort by: Newest First' dropdown, and a large deep-purple `Analyze All` button with the total count mapped on the right.
   - Replace the current incident list structure with the deeply dark padded rows featuring the incident type, the yellow/amber severity badge immediately beside the title, the path nested underneath, and `Count: [X] | Last: [TIME]` explicitly listed below.
   - Maintain the 'AI Analysis' (purple outline) and 'Resolve' (green outline) action buttons on the far right.
4. **Tab 3: ARCHIVES**:
   - Minimal graphics slate: Display the "Archive Management" title with "Weekly archives: 7 days retention" subtitle, centered alongside the locked document SVG.
5. **Tab 4: LEARNING**:
   - Construct a horizontal, 4-column metric rail: `TOTAL RESOLUTIONS`, `VERIFIED`, `PENDING`, `SUCCESS PATTERNS`.
   - Embed a dark, wide table block titled "Top Success Patterns" spanning the rest of the tab.

## Execution Requirements

- Use inline SVGs for charts and icons (e.g., Lucide React icons matching the imagery) to ensure no new heavy dependencies are strictly required.
- Do not mutate the `ApiContract` fetch signatures underneath; simply reroute the payload mapping to populate these highly-designed interface shells.

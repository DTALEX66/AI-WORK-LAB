# WORK-LAB to DESIGN-LAB Update Plan (2026-08-18)

> Source: WORK-LAB 50-taskpacks/WORK-LAB-DSH-HANDOFF-2026-08-18.md (latest handoff) + 00-governance/migration-status.json.
> Scope: only items relevant to DESIGN-LAB; WORK-LAB internal todos (WL3/DSH) are out of scope.

## 1. Boundary sync items (decided in WORK-LAB, DESIGN-LAB side to align/record)

| # | Boundary | WORK-LAB side | DESIGN-LAB side action | Status |
|---|---|---|---|---|
| 1 | Open Design dual identity | client USER_GLOBAL desired = MANAGE + apply_supported=false | Record in ADAPTER_POLICY/BOUNDARY: DESIGN-LAB owns Open Design capability only, never manages client config | TODO record |
| 2 | DESIGN-LAB projection to open-design | PROJECT_OVERLAY / OBSERVE (read-only) | Consistent with existing adapters/hosts/open-design (host adapter E0); keep OBSERVE read-only | Aligned |
| 3 | Three-plane system | WORK-LAB = control plane (agent registry / work unit / policy engine) | DESIGN-LAB = capability plane: Provider SPI / capability contracts exist; integration point = WORK-LAB provider_policy downstream, DESIGN-LAB decides design capability - no new work, record only | Covered |

## 2. Actionable items (WORK-LAB state changes unlock DESIGN-LAB tasks)

| # | Change | Impact on DESIGN-LAB | Action | Status |
|---|---|---|---|---|
| 4 | Open Design host installed (D:/Programs/Open Design, Electron + opencode CLI verified) | B1 (Open Design E3) flips from blocked to actionable | opencode run real design task + export session for E3 evidence | Awaiting your task |
| 5 | Photoshop 2023 verified controllable (COM + JSX: doc/text layer/editable PSD) | B2 (PS E3) actionable | JSX real editable PSD delivery + readback for E3 evidence | Awaiting your task |
| 6 | WORK-LAB has no code/assets to push into DESIGN-LAB | Handoff confirms capability belongs to DESIGN-LAB; nothing to receive | No receive action | Done |

## 3. WORK-LAB internal todos unrelated to DESIGN-LAB (boundary only, not executed here)

- WL3-100/110 onboarding, DSH-040 paid smoke (needs user key), DSH migration residue cleanup, handoff doc commit/push (WORK-LAB approval flow)

## 4. Execution suggestion

1. Record boundary #1 into docs/ADAPTER_POLICY.md or BOUNDARY_CONTRACT (one small commit)
2. Use #4/#5 for G1/G2 (real artifact) then A1 (Jury) then E4 path
3. No other receive items from WORK-LAB

## 5. Evidence

- WORK-LAB 08-18 handoff (TL;DR, 1.3 Open Design dual identity, 2 exact state, 4 todos)
- Local verification: Open Design CLI (opencode run OK), PS 2023 (JSX saved editable PSD 105KB)

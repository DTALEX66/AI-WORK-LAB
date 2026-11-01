# Prototyping — Agent Rules

Rules for any AI agent working on this codebase.
Read **Design.md** first for all visual tokens and component specs.

---

## Product Context — New-User Prototype Only

This is a **UI/UX prototype** built to pitch/demo — not a production app with real accounts or database persistence.

- **Every flow should assume a brand-new user.** All entry points and portals should walk through onboarding / sign-up or first-time setup, not a "returning user" sign-in, unless explicitly asked.
- **Keep existing seed/mock data as-is** — the app should look populated and lived-in for demos, even though the *flow* should always present as a new user signing up. The inconsistency between "just signed up" and "dashboard full of records" is acceptable and desirable for a demo.

---

## File Structure

```
index.html               ← Hub launcher page (links to app entry point + figma.html)
app.html                 ← Core application entry point (loads Babel and React)
figma.html               ← Static design board/artboards view of all screens.
styles.css               ← Global CSS. Minimal — most styles are inline React.
shared.jsx               ← T tokens, SAFE_TOP, NAV_H, shared components + hooks.
data.jsx                 ← All mock data (DATA object). No logic here.
icons.jsx                ← SVG icons wrapper component.
app.jsx                  ← Router, overlays, BottomNav, Stage mount.
screens-onboarding.jsx   ← Splash screen, onboarding flows, walkthroughs.
screens-home.jsx         ← Home dashboard, main feeds, core landing.
```

**Script load order in HTML is strict.** `shared.jsx` and `data.jsx` must load before all screen files. `app.jsx` mounts last.

---

## Scope / Globals Pattern

All files are `<script type="text/babel">` — NOT ES modules. Babel transforms `const` → `var`, so top-level `const` in each file lands on `window`.

**Sharing between files:** Always use `Object.assign(window, { MyComponent, myFn })` at the bottom of each file. Read from `window` globals in other files.

**Naming:** Every `styles` object MUST be uniquely named (e.g. `const homeStyles = {…}`). Never use bare `const styles = {…}` — it will collide across files.

---

## Design Token Rules

1. **Never hardcode colors.** Before writing any `#hex` / `rgb()` / `rgba()`, check whether it matches an existing `T.*` token, and use the token instead.
2. **All screen backgrounds are `T.bg` (`#FFFFFF`).** Do not use `T.bg2` or any tinted color as a full-screen layer background.
3. **Secondary fills** use `T.bg2` (`#F5F5F5` or similar neutral light gray).
4. **Card borders** use `boxShadow: 'inset 0 0 0 1px ' + T.sep` — not CSS `border`.
5. **Separator lines** use `T.sep` or `T.sepN` — never hard-coded colors.
6. If you genuinely need a new color that has no existing token equivalent, add it to `T` in `shared.jsx` with a clear semantic name.

---

## Layout Rules

1. **No mobile frame / bezel inside screens.** The app fills `100vw × 100vh` directly inside its viewport wrapper.
2. **`SAFE_TOP = 12`** — top padding for screen headers.
3. **`NAV_H = 84`** — bottom nav height. Always add `paddingBottom: NAV_H + 16` to scrollable tab root screens.
4. **Never use `position: fixed`** inside screens — use `position: absolute` within the `.layer` context.
5. **Sticky headers:** any screen with a `<TopBar>` + scroll div must use `useStickyHeader()` and pass `shadow={scrolled}` to `<TopBar>` and `onScroll={onScroll}` to the scroll container.

---

## Navigation Rules

- `api.push('screenName', { params })` — push a new screen
- `api.pop()` — go back
- `api.setTab('tabName')` — switch tab root
- `api.resetToLauncher()` — return to the launcher / portal selector

### Adding a new screen
```jsx
function MyScreen({ params }) {
  const api = useApp();
  const { scrolled, onScroll } = useStickyHeader();
  return (
    <div className="layer">
      <TopBar title="My Screen" onBack={() => api.pop()} shadow={scrolled} />
      <div className="scroll" style={{ flex: 1, padding: '0 16px 24px' }} onScroll={onScroll}>
        {/* content */}
      </div>
    </div>
  );
}
Object.assign(window, { MyScreen });
// Then in app.jsx SCREENS list: myScreen: window.MyScreen
// Navigate: api.push('myScreen', { param: value })
```

---

## Figma Board (figma.html)

Whenever you add a new screen, route, or significant UI flow, you must also update `figma.html` to keep the visual design board in sync.
- Screens are grouped and mapped to the figma canvas layout.
- The figma board canvas background should remain distinct from screen backgrounds to visually group the artboards.

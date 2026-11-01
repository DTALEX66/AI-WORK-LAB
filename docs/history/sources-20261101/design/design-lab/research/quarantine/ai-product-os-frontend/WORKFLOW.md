# AI Product OS — UI/UX · Brand · Prototype — Complete Workflow Guide

> Welcome. This is your step-by-step operating manual for designing and shipping premium mobile & web products using AI tools. Whether you're a designer learning to code, or a developer learning to design — this guide meets you where you are.
>
> **Every step has:** what to do · what tools to use · exact prompts to copy · what you'll have at the end.

---

## Before You Begin

### Tools You'll Need

| Tool | What It's For | Cost |
|------|--------------|------|
| **Gemini** (gemini.google.com) | Deep market research | Free |
| **Claude** (claude.ai) | Strategy, UX, PRD, coding | Free / Pro |
| **Claude Cowork** | Persistent project context across sessions | Claude Pro |
| **Figma** | Brand guidelines, design system, handoff | Free / Pro |
| **Figma MCP** | Claude creates FigJam flows directly | Free plugin |
| **Magnific MCP** | AI image generation for moodboards + logo SVGs | Subscription |
| **ChatGPT** *(optional)* | Backup ideation, copy drafting | Free / Plus |
| **Antigravity IDE** | AI-powered coding environment | Your current tool |
| **Vercel** | Deploy the live prototype | Free |
| **html.to.design** | Convert live prototype → Figma components | Free plugin |

### Your Project Folder Structure

Before starting any project, create this folder structure. Everything has a home.

```
YourProjectName/
│
├── 📁 docs/                          ← All strategy & research documents
│   ├── brief.md                      ← Project brief (from Step 1)
│   ├── research.md                   ← Gemini research export (from Step 2)
│   ├── personas.md                   ← User personas (from Step 5)
│   ├── userflows.md                  ← User flows (from Step 6)
│   ├── problem-statements.md         ← Problem statements (from Step 7)
│   ├── PRD.md                        ← Product Requirements Doc (from Step 12)
│   ├── brand-guidelines.pdf          ← Figma export (from Step 10)
│   └── handoff.md                    ← Dev handoff notes (from Step 19)
│
├── 📁 assets/                        ← All visual assets
│   ├── logo/
│   │   ├── logo-wordmark.svg
│   │   ├── logo-wordmark-dark.svg
│   │   ├── logo-icon.svg
│   │   └── logo-icon@512.png
│   └── images/                       ← Photos, illustrations, moodboard refs
│
├── 📁 claude-design-export/          ← Claude Design output (from Step 14)
│   ├── screens/                      ← Individual screen code/images
│   └── archive.zip                   ← Full export archive
│
├── 📁 skills/                        ← Custom AI agent skill files
│   ├── ui-ux-designer.md
│   └── ai-product-design.md
│
├── index.html                        ← Hub launcher
├── app.html                          ← Interactive prototype
├── figma.html                        ← Design board (all screens)
├── app.jsx                           ← Router & overlays
├── shared.jsx                        ← Design tokens & components
├── data.jsx                          ← Mock data
├── icons.jsx                         ← Icon component
├── screens-onboarding.jsx
├── screens-home.jsx
├── [screens-*.jsx ...]               ← Add as you build
├── styles.css
├── Design.md                         ← Design token reference
├── rules.md                          ← Agent rules
├── WORKFLOW.md                       ← This file
└── README.md
```

> 💡 **New to this?** Don't stress about having everything set up perfectly. Create the folders as you need them. The structure is a guide, not a gate.

---

## Phase 1 — Discovery

### ✦ Step 1 · Get the Project Brief

**What this is:** A structured document that captures everything you know about the project before touching any design tool.

**Do this yourself** (in a meeting, call, or async questionnaire with the client):

**Questions to always ask:**
```
1. What problem are you solving? (in one sentence)
2. Who are the primary users?
3. What platforms? (iOS, Android, Web, all?)
4. What are the 3 most important features for launch?
5. Who are your main competitors?
6. What does success look like in 3 months?
7. What's the rough timeline?
8. What's the budget range?
9. Do you have existing branding? (logo, colors, fonts)
10. Are there any hard constraints? (tech stack, legal, etc.)
```

**Then use Claude to structure it:**
```
I just finished a client discovery session. Here are my raw notes:

[paste your notes]

Please structure this into a clean project brief with these sections:
- Project Overview (2-3 sentences)
- Problem Statement
- Target Users (rough)
- Platform & Scope
- MVP Feature List (prioritised)
- Competitors
- Success Metrics
- Timeline & Budget
- Open Questions

Keep it concise — this will be shared with stakeholders.
```

**Save as:** `docs/brief.md`

> ✅ **End of Step 1:** You have a clean, structured brief that everyone agrees on.

---

### ✦ Step 2 · Deep Research with Gemini

**What this is:** A thorough market and competitor analysis so you design with evidence, not assumptions.

**Go to:** gemini.google.com → use **Deep Research** mode

**Research prompt:**
```
I'm designing a [type of app] called [AppName] that [what it does].
Target audience: [description].
Main competitors: [list any you know].

Please conduct a comprehensive research report covering:

1. Market Overview
   - Market size and growth trends
   - Key players and their positioning
   - Gaps and opportunities

2. Competitor Analysis (analyse 4-5 apps)
   - Core features each offers
   - UX patterns they use
   - What users love / hate about each (from app store reviews)
   - Their pricing model

3. User Behaviour & Pain Points
   - How users currently solve this problem
   - Common frustrations with existing solutions
   - What they wish existed

4. Design Trends
   - UI patterns common in this category
   - What's working well in similar apps
   - What's feeling dated or overused

5. Technical Considerations
   - Common integrations and APIs in this space
   - Data/privacy considerations

Please be thorough — this will guide the entire product design.
```

**Export:** File → Download as `.docx`

**Convert to Markdown:**
1. Open the `.docx` in Google Docs
2. Clean up any formatting issues
3. File → Download → Markdown (.md)
4. Save as `docs/research.md`

> 💡 **Why Markdown?** AI agents read Markdown natively. Saving as `.md` means Claude, Cursor, and Antigravity can all reference this document directly without any conversion.

> ✅ **End of Step 2:** You have a solid `research.md` with real evidence to guide design decisions.

---

### ✦ Step 3 · Research → Markdown

Already covered at the end of Step 2. Make sure `docs/research.md` is clean and well-structured before moving on.

**Quick cleanup checklist:**
- [ ] Headings are properly formatted (`#`, `##`, `###`)
- [ ] Tables use Markdown table syntax
- [ ] No leftover HTML or Word formatting artifacts
- [ ] File is under 50,000 words (if longer, split into sections)

---

## Phase 2 — Strategy & UX

### ✦ Step 4 · Set Up Claude Cowork Project

**What this is:** Claude Projects gives Claude persistent memory across all your conversations on this project. Upload all your documents here and Claude will reference them every session without you needing to re-paste anything.

**How to set up:**
1. Go to claude.ai → **Projects** → **New Project**
2. Name it: `[AppName] — Product Design`
3. Add a project description:
   ```
   This is the working Claude project for [AppName], a [type of app].
   I am the lead UI/UX designer on this project.
   All documents uploaded to this project are the authoritative source of truth.
   Always reference the brief, research, and any uploaded materials before answering.
   ```
4. **Upload files:**
   - `docs/brief.md`
   - `docs/research.md`
   - Any existing brand assets (logo, style guide, etc.)

5. **Set the project instructions** (paste this):
   ```
   You are my senior product design partner on this project.
   
   Your role:
   - Help me make smart design decisions backed by the research
   - Challenge assumptions when you see a better approach
   - Always cite which part of the research or brief supports a recommendation
   - When generating user-facing copy, match the brand voice
   - When in doubt, ask me before assuming
   
   My role: Final decision maker on all design choices.
   ```

> ✅ **End of Step 4:** Claude has full context and is set up as your design partner.

---

### ✦ Step 5 · User Research → Personas in Claude Cowork

**What this is:** Turning research data into vivid, specific user personas. These aren't corporate template personas — they're real-feeling people who will guide every design decision.

**Run this in your Claude Project:**
```
Based on the research and brief in this project, create 3 detailed user personas.

For each persona, include:
- Name, age, location, occupation
- A realistic profile photo description (so I can find a reference)
- Their primary goal related to [AppName]
- Their biggest frustration with how they solve this today
- A typical day (morning to evening, briefly)
- How they use technology (casual / power user / specific apps they love)
- Their exact quote that captures their mindset
- The moment they would download [AppName] (the trigger)
- The moment they would delete [AppName] (the dealbreaker)
- Accessibility or language considerations

Make these feel like real people, not marketing archetypes.
```

**Then refine:**
```
Take Persona 1 ([name]). 
I want to run a mock user interview with her. 
Play her role and I'll ask questions. 
Stay in character based on her profile.
```

This simulates user interviews so you can discover insights without needing to recruit participants for a prototype project.

**Save as:** `docs/personas.md`

> 💡 **Pro tip:** Create 3 personas minimum but design primarily for 1. The "primary persona" drives all decisions. The others keep you honest about edge cases.

> ✅ **End of Step 5:** You have 3 detailed personas and have stress-tested them through mock interviews.

---

### ✦ Step 6 · Figma MCP → User Flows in FigJam

**What this is:** Instead of manually drawing user flows in FigJam, you connect Claude to Figma via MCP and let Claude create the flow structure directly in your Figma file.

**Setup:**
1. Install the **Figma MCP** server in your Claude environment
2. Open a new FigJam file in Figma
3. Copy the FigJam file URL

**Prompt Claude with Figma MCP connected:**
```
I have a FigJam file open at [URL].

Please create user flow diagrams for [AppName] covering these journeys:

1. New User Onboarding Flow
   - App launch → Sign up → Verify → Onboarding steps → Home
   
2. Core Feature Flow: [Main feature name]
   - Entry point → [key steps] → Success state → Return to home
   
3. Error & Edge Case Flow
   - What happens when: network fails, invalid input, empty states

For each flow:
- Use rounded rectangles for screens
- Use diamonds for decision points  
- Use arrows with labels for navigation paths
- Group each flow in its own section with a clear title
- Use color coding: green for happy path, orange for alternative paths, red for error states

Reference the personas from the project documents to name the flows after who takes them.
```

**After Claude creates the flows, review and annotate:**
- Add notes for anything Claude missed
- Mark which screens are MVP vs future
- Add timing notes (e.g., "OTP expires in 5 minutes")

**Export:** Screenshot or export as PDF from FigJam
**Save reference:** `docs/userflows.md` (text description of flows)

> 💡 **Don't have Figma MCP set up?** You can ask Claude to describe the flows as structured text and manually create them in FigJam. The MCP just saves time.

> ✅ **End of Step 6:** You have visual user flows in FigJam and a text reference in your docs folder.

---

### ✦ Step 7 · Define Problem Statements + Sketches

**This step is yours.** AI can suggest, but you as the designer need to feel the problem.

**Problem Statements — How Might We framework:**

After reading through personas and flows, write 5–10 "How Might We" statements:
```
How might we... [action] for [persona] so that [outcome]?
```

Examples:
```
How might we reduce onboarding friction for first-time users so they reach the core feature in under 2 minutes?

How might we help [Persona 1] trust the app enough to enter their payment details?

How might we surface the most relevant content for [Persona 2] without overwhelming them?
```

**Check with Claude:**
```
Here are my problem statements:
[paste them]

Based on our personas and research, are there any critical user problems I've missed?
Are any of these solving the wrong problem?
Rank these by impact × feasibility for a first release.
```

**Sketches:**

Grab paper (or iPad + Procreate/Concepts) and sketch rough layouts for the 3 most important screens. No need to be pretty — this is thinking with your hands.

Sketch:
- The main home/dashboard screen
- The core feature flow (2–3 screens)
- The onboarding splash

Photograph your sketches and save to `assets/images/sketches/`.

**Save as:** `docs/problem-statements.md`

> 💡 **Why sketch by hand?** Sketching forces decisions without the distraction of pixels and tools. You'll design faster and more confidently in the digital phase because the thinking is already done.

> ✅ **End of Step 7:** You have clear problem statements and rough screen layouts. You know what you're building before you open Figma.

---

### ✦ Step 8 · Custom Skills Files for Your AI Agents

**What this is:** Custom `.md` skill files that teach AI agents your design expertise, terminology, and standards. When you upload these to Claude, it stops being a generic assistant and becomes a specialised design partner.

**Create `skills/ui-ux-designer.md`:**
```markdown
# UI/UX Designer Skill

## Role
You are an expert UI/UX designer with 10+ years of experience in 
mobile and web product design. You specialise in:
- User-centred design processes
- Design systems and component libraries
- iOS and Android platform conventions
- Conversion-optimised UX patterns
- Accessibility (WCAG 2.1 AA compliance)

## Design Principles You Follow
1. Clarity over cleverness — if users have to think, we've failed
2. Consistency over novelty — use established patterns before inventing
3. Feedback is mandatory — every action needs a visible response
4. Empty states are screens too — design them with care
5. Design for the 80% — edge cases should be handled, not celebrated

## When Reviewing Designs
- Always check: Does this work for Persona 1?
- Always ask: What happens if this fails?
- Always verify: Is this consistent with the design system?
- Always confirm: Is the hierarchy clear at a glance?

## Platform Conventions
### iOS
- Safe area insets: top 59px, bottom 34px (iPhone 14 Pro)
- Bottom tab bar: 83px including safe area
- Touch targets: minimum 44×44pt
- Navigation: back swipe from left edge

### Android  
- Status bar: 24dp
- Navigation bar: 48dp
- Bottom nav: 56dp + system nav bar
- Touch targets: minimum 48×48dp

## Typography Rules
- Never use more than 2 font families
- Body text: minimum 14px / 1.4 line height
- Captions: minimum 11px
- Don't use font weight for emphasis alone — use colour too

## Colour Rules
- Minimum contrast ratio: 4.5:1 for body text (WCAG AA)
- Interactive elements must be distinguishable without colour alone
- Never use pure black (#000000) for text — use near-black
- Success: green · Warning: amber · Error: red · Info: blue
```

**Create `skills/ai-product-design.md`:**
```markdown
# AI Product Design Skill

## Role
You are an AI-native product designer who uses artificial intelligence 
at every stage of the design process — not as a shortcut, but as 
a thinking partner that amplifies human creativity and judgement.

## AI Tools in the Workflow
- Gemini: Market research, competitive analysis
- Claude: Strategy, personas, PRD, code generation
- Claude Design: UI screen generation
- Magnific MCP: Visual generation, moodboards, logo SVG concepts
- Antigravity: Prototype building and iteration
- Figma MCP: Automated flow creation in FigJam
- html.to.design: Prototype → Figma conversion

## AI-Assisted Design Principles
1. AI generates options, humans make decisions
2. Always validate AI output against user research
3. AI output is a starting point — always refine
4. Use AI for speed on execution, not for replacing thinking
5. Document every AI-assisted decision for transparency

## Prototype-First Philosophy
We build functional prototypes, not static mockups, because:
- Stakeholders understand interactions better than slides
- Developers get living specification, not PDFs
- Real browsers catch real problems early
- Investor demos need to feel real

## Output Quality Standards
Every screen we ship must be:
- Pixel-precise to the design system
- Interactive (not just a static image)
- Viewable on the actual device size (390px mobile)
- Part of the figma.html board for design review
```

**Upload both files to your Claude Project.**

> ✅ **End of Step 8:** Your AI agents now behave like specialised design experts, not generic chatbots.

---

## Phase 3 — Brand

### ✦ Step 9 · Moodboards + Logo via Magnific MCP

**What this is:** Using the Magnific MCP server connected to Claude to generate high-quality visual moodboards and explore logo directions as SVGs — all without leaving Claude.

#### Part A — Moodboards

**With Magnific MCP connected, prompt Claude:**
```
Generate a moodboard for [AppName] — a [type of app] for [audience].

The brand should feel: [3-5 adjectives, e.g. "warm, trustworthy, modern, approachable"]

Create 4 moodboard images exploring these visual directions:
1. Direction A: [describe first visual concept]
2. Direction B: [describe second visual concept]  
3. Direction C: [describe third visual concept]
4. Direction D: [wildcard — surprise me]

Each image should show: colour palette, typography mood, texture/pattern, 
photography style, and overall emotional tone.
```

Review the 4 directions and pick 1–2 to take forward.

#### Part B — Logo Generation

**Prompt Claude with Magnific MCP:**
```
Based on Direction [A/B] from the moodboard, generate logo concepts for [AppName].

Logo brief:
- Type: [wordmark / lettermark / combination mark]
- Style: [geometric / organic / minimal / bold / playful]
- Feeling: [adjectives]
- Must work on: white background, dark background, app icon (square)

Generate 3 logo concepts as SVG files.
For each concept, explain the design rationale in 2 sentences.
```

#### Part C — Clean Up in Figma

Take the best SVG from Magnific and bring it into Figma for cleanup — no extra subscriptions needed:

1. File → Place image → select the SVG → ungroup all layers
2. Use **Flatten** (⌘E) to merge compound shapes cleanly
3. Check the icon at 16px (as a frame) — does it still read?
4. Check at 1024px — are curves smooth?
5. Rename layers cleanly: `icon`, `wordmark`, `background`
6. Export the full asset set:

```
assets/logo/
├── logo-wordmark.svg          ← full name + icon, on light bg
├── logo-wordmark-dark.svg     ← full name + icon, on dark bg  
├── logo-icon.svg              ← icon only
├── logo-wordmark.png          ← @2x PNG (800px wide)
├── logo-icon@512.png          ← app icon (512×512)
├── logo-icon@1024.png         ← App Store icon (1024×1024)
└── favicon.ico                ← 32×32
```

> 💡 **Figma exports clean SVGs** — use `File → Export → SVG` with "Include id attribute" off. This keeps the code lean and editor-friendly.

> ✅ **End of Step 9:** You have a professional logo in vector format, ready for every context.

---

### ✦ Step 10 · Brand Guidelines in Figma → PDF

**What this is:** A formal document that defines the visual language of the brand. Once made, this is the source of truth for every designer, developer, and AI agent working on this product.

**Figma Brand Guidelines structure:**

```
Page 1: Cover — logo on brand colour, app name, tagline
Page 2: Logo Usage — dos and don'ts, clearspace rules, minimum size
Page 3: Colour Palette — swatches with HEX, RGB, HSL values + usage rules
Page 4: Typography — font family, type scale (sizes + weights), hierarchy examples
Page 5: Iconography — icon set style, size guidelines, usage examples
Page 6: Photography — mood direction, sample images, what to avoid
Page 7: Voice & Tone — writing style, example microcopy, words to use/avoid
Page 8: Spacing & Grid — base unit, screen margins, component spacing
Page 9: UI Components Preview — how brand feels in actual UI
```

**Export:** File → Export PDF  
**Save as:** `docs/brand-guidelines.pdf`  
**Upload to Claude Project**

> ✅ **End of Step 10:** You have a professional brand guidelines document that any collaborator (or AI agent) can reference.

---

### ✦ Step 11 · Design System in Figma → `Design.md`

**What this is:** Building the component library in Figma and then writing `Design.md` — the machine-readable token reference that your code and your AI agents will both use.

#### Part A — Figma Design System Setup

**Local Variables to define:**
- Colours (primitives + semantic aliases)
- Spacing scale (4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80)
- Border radius (4, 8, 12, 16, 20, 24, 999)
- Typography (size + weight + line-height)
- Shadow (xs, sm, md, lg)

**Components to build (minimum set for mobile):**
```
Atoms:
- Button (Primary, Secondary, Outline, Destructive, Disabled)
- Input (Default, Focused, Error, Disabled)
- Badge / Chip (Default, Active, Status variants)
- Avatar (Small, Medium, Large + image vs initials)
- Icon (20px, 24px, 32px)

Molecules:
- TopBar (with/without back button, with/without right action)
- BottomNav (5 tabs, active + inactive states)
- Card (Default, Pressable, with image)
- List Item (Simple, With icon, With avatar, With badge)
- Empty State (icon + title + description + CTA)
- Toast / Snackbar
- Bottom Sheet (handle + scrollable content)

Organisms:
- Modal / Dialog
- Form (input + label + error)
- Screen Template (TopBar + scroll area + nav padding)
```

#### Part B — Write `Design.md`

After building in Figma, document every token and component in `Design.md`. This file already exists in the boilerplate — **update it with your actual project tokens.**

```markdown
# [AppName] — Design System

## Colour Tokens
| Token | Hex | Usage |
|-------|-----|-------|
| brand.primary | #____ | [usage] |
| brand.secondary | #____ | [usage] |
...

## Typography
...

## Components
...
```

**Upload the updated `Design.md` to Claude Project.**

> 💡 **The magic of Design.md:** When Claude and Antigravity can read `Design.md`, they stop making up colors. Every piece of code they write will reference your actual tokens. This is what makes AI-generated code actually match your design.

> ✅ **End of Step 11:** You have a Figma design system and a machine-readable `Design.md`. Your brand is now codeable.

---

## Phase 4 — UI/UX Design

### ✦ Step 12 · Build the PRD with Claude

**What this is:** A Product Requirements Document — the full specification of what gets built. This is the contract between design and development.

**In your Claude Project (which now has brief, research, personas, flows, brand PDF, Design.md):**

```
Using all the documents in this project, create a comprehensive PRD for [AppName].

Structure:
1. Executive Summary (1 paragraph)
2. Problem Statement (from our validated research)
3. User Personas (reference docs/personas.md)
4. User Stories
   For each persona, write user stories in this format:
   "As [persona name], I want to [action] so that [outcome]."
   Include: happy path, edge cases, error states
5. Feature Specifications (MVP)
   For each feature:
   - Feature name
   - Priority (P0=must have, P1=should have, P2=nice to have)
   - User story it serves
   - Acceptance criteria (how do we know it's done?)
   - Edge cases to handle
6. Screen Inventory
   List every screen in the app with:
   - Screen name
   - Purpose (one sentence)
   - Entry point(s)
   - Exit point(s)
   - Key components
7. Navigation Structure
   - Tab bar structure (if applicable)
   - Screen hierarchy (push/pop stack)
   - Modals and overlays
8. Non-functional Requirements
   - Performance targets (load time, animation fps)
   - Accessibility requirements
   - Offline behaviour
9. Out of Scope (V1)
   What we're explicitly NOT building now
10. Success Metrics
    - What KPIs prove this product is working?

Reference the brand guidelines and Design.md for any visual specifications.
```

**Save as:** `docs/PRD.md`  
**Upload to Claude Project**

> ✅ **End of Step 12:** You have a full PRD. Developers have everything they need to build. Stakeholders have a clear scope document.

---

### ✦ Step 13 · UI Design in Claude Design

**What this is:** Using Claude Design (claude.ai/design) to generate the actual UI screens. The key discipline here: **stick to the design system tokens only.** No improvising with new colours or fonts.

#### Prepare Your Context Package

Collect and upload to Claude Design:
- [ ] `docs/personas.md`
- [ ] `docs/userflows.md`
- [ ] `docs/PRD.md`
- [ ] `docs/brand-guidelines.pdf`
- [ ] `Design.md` (your updated version)
- [ ] `assets/logo/logo-wordmark.svg`
- [ ] `assets/logo/logo-icon.svg`
- [ ] Sketches (photos of your hand sketches from Step 7)

#### Prompt Claude Design

```
You are designing a premium [mobile/web] app called [AppName].

CONTEXT:
- Personas: [attach personas.md]
- User Flows: [attach userflows.md]  
- PRD: [attach PRD.md]
- Brand Guidelines: [attach brand-guidelines.pdf]
- Design System: [attach Design.md]
- Logo: [attach logo files]

CRITICAL RULES:
1. Use ONLY the colour tokens defined in Design.md — no custom colours
2. Use ONLY the type scale from Design.md — no custom font sizes
3. Every component must match the Figma design system spec
4. Design for 390×844px (iPhone 14 Pro viewport)
5. Every screen needs: header/nav + scrollable content + bottom navigation
6. Include micro-interactions description in your output

SCREENS TO DESIGN (in order):
1. Splash Screen — brand intro, 2-second display
2. Onboarding — [describe your flow, e.g. 3 slides + sign up]
3. Home / Dashboard — [describe primary content]
4. [Core Feature Screen 1] — [describe]
5. [Core Feature Screen 2] — [describe]
6. Profile / Settings — [describe]
7. [Any additional screens from PRD]

For each screen, also describe:
- The emotion the user should feel
- The primary action they take
- What happens after that action
```

**Iterate with Claude Design:**
```
Screen 3 (Home) needs work. The hierarchy isn't clear.
The [element] is competing with [other element] for attention.
Reduce the visual weight of [element] and make [primary action] 
more prominent. Keep all colours from Design.md.
```

> 💡 **Don't try to design everything at once.** Go screen by screen. Nail one before moving to the next. Claude Design works best with focused, specific requests.

> ✅ **End of Step 13:** You have AI-generated UI designs that match your design system.

---

### ✦ Step 14 · Export Claude Design Archive

**What this is:** Saving all the Claude Design output so it can be imported into the boilerplate.

**In Claude Design:**
1. Export the conversation / session archive
2. Save any generated code snippets into individual files
3. Screenshot every designed screen at full resolution
4. Note any design decisions that weren't captured in files

**Organise in:**
```
claude-design-export/
├── screens/
│   ├── 01-splash.png
│   ├── 02-onboarding-1.png
│   ├── 03-onboarding-2.png
│   ├── 04-home.png
│   └── [etc.]
├── code/
│   ├── home-screen.jsx      ← any code Claude Design generated
│   └── [etc.]
├── notes.md                 ← design decisions and rationale
└── archive.zip              ← full export if available
```

> ✅ **End of Step 14:** You have a clean archive of all design work, ready for the build phase.

---

### ✦ Step 15 · Add Claude Design Export to Boilerplate

**What this is:** Dropping the Claude Design export folder into your boilerplate project directory so Antigravity can access it.

1. Copy `claude-design-export/` into your project root
2. Your project folder now looks like this boilerplate — it has all the code files AND the design archive
3. Commit to Git if you're using version control

> ✅ **End of Step 15:** Everything is in one place. Time to build.

---

## Phase 5 — Build & Deploy

### ✦ Step 16 · Build the Prototype in Antigravity

**What this is:** Bringing Antigravity IDE into your fully-stocked project and asking it to build the complete interactive prototype by reading all your materials.

#### The Master Prompt (give this to Antigravity at the start)

```
I have a complete product design project ready to build. 
Please read all the materials in this directory before starting.

Key files to read:
- docs/PRD.md — full product spec
- docs/personas.md — who we're designing for
- docs/userflows.md — all navigation flows
- Design.md — design tokens (use these ONLY for all styles)
- rules.md — coding conventions for this codebase
- claude-design-export/notes.md — design rationale
- claude-design-export/screens/ — reference images for each screen

Your task is to build the complete interactive prototype:

1. CREATE all screens listed in the PRD
2. WIRE all navigation using api.push/pop/setTab per rules.md
3. USE only T.* tokens from Design.md for all colours, spacing, shadows
4. UPDATE figma.html to include every new screen in the artboard board
5. POPULATE data.jsx with realistic mock data for the demo
6. ENSURE the launcher screen lets you enter all user flows

When complete, there should be TWO products:
A. app.html — the fully interactive prototype (customer-facing flow)
B. figma.html — the design board showing every single screen as a static artboard

Work screen by screen. After each screen, tell me what's done and what's next.
```

#### Testing Checklist

After Antigravity builds each screen:
- [ ] Screen renders without console errors
- [ ] Navigation pushes and pops correctly
- [ ] Back button works
- [ ] Bottom nav highlights the correct tab
- [ ] Overlays (sheets, dialogs, toasts) open and close
- [ ] Content scrolls smoothly on 390px viewport
- [ ] figma.html artboard board updates with the new screen
- [ ] Mock data looks realistic (not "Lorem Ipsum")
- [ ] All colours match Design.md tokens exactly

**Run locally:**
```bash
# Any simple HTTP server works:
python3 -m http.server 8000
# Then open: http://localhost:8000
```

**Iterate with Antigravity:**
```
The Home screen looks good but the card spacing is too tight.
Increase the gap between cards to 16px (use T.* spacing, not hardcoded values).
Also the profile avatar in the top bar is missing — add it.
Make sure figma.html reflects these changes.
```

> 💡 **Two outputs:** At the end of this step you have `app.html` (the live, interactive prototype) and `figma.html` (the static design board). Both are valuable — the prototype for demos, the board for design review and Figma export.

**Deploy to Vercel:**
```bash
npm install -g vercel    # if not installed
vercel --prod            # deploys and gives you a live URL
```

Or: Connect your GitHub repo to Vercel → every push auto-deploys.

> ✅ **End of Step 16:** You have a live, interactive prototype at a real URL. You can share it with stakeholders, investors, and users for feedback.

---

## Phase 6 — Figma Export & Dev Handoff

### ✦ Step 17 · Export Prototype → Figma via html.to.design

**What this is:** The `html.to.design` plugin captures your live prototype and creates real Figma layers from it — so you don't have to rebuild everything in Figma from scratch.

**Steps:**
1. Install [html.to.design](https://www.figma.com/community/plugin/1159123024924461424) in Figma
2. Open a new Figma file: `[AppName] — Design File`
3. Run the plugin
4. Enter your live prototype URL (Vercel deploy URL)
5. Let it capture the rendered screens

**After import — clean up and map:**
- Map all imported colours to your **Figma Styles / Variables**
- Map all imported text to your **Text Styles**
- Replace auto-generated layers with your **Component Library** components
- Name all layers properly: `Screen/HomeScreen`, `Component/Card/Default`
- Organise into Figma pages:
  ```
  Page 1: 📋 Cover
  Page 2: 🎨 Design System
  Page 3: 🗺 User Flows
  Page 4: 📱 Screens — Onboarding
  Page 5: 📱 Screens — Core Flows
  Page 6: 📱 Screens — Profile & Settings
  Page 7: 🔁 Prototype Links
  ```

> 💡 **Why this direction (code → Figma)?** Traditional workflow goes Figma → code. By going code → Figma, you have a living prototype as the source of truth, and Figma becomes the documentation layer — not the bottleneck.

> ✅ **End of Step 17:** You have a real Figma file with properly mapped components and styles.

---

### ✦ Step 18 · Blueprint for Developers — Dev Handoff

**What this is:** Preparing the Figma file so developers can build from it without asking you 50 questions.

#### Annotations (use Figma's annotation tool or Figma Annotations plugin)

Label every interactive element:
```
[Button: Primary] → Navigates to /checkout
[Input: Email] → Validates on blur, shows error if invalid format
[Card: Restaurant] → Pressable, navigates to RestaurantScreen
[Tab: Home] → Sets active tab, resets stack to home root
```

#### Navigation Wiring (Figma Prototype)

1. Click the Prototype tab in Figma
2. Wire every interactive element to its destination screen
3. Set the correct animation (slide in → for push, slide out → for pop)
4. Set starting screen to LauncherScreen
5. Test the full prototype flow in Figma Preview

#### User Flow Pages

Create a dedicated "Flows" page:
- Show each user journey from Step 6 (userflows.md) visually
- Use Figma's connector/arrow tool
- Label each step with the screen name and trigger action
- Add persona name to show whose flow this is

#### Dev Mode Readiness Checklist

```
Colours:
[ ] All colours linked to Variables (not hardcoded hex)
[ ] Variable names match Design.md token names

Typography:
[ ] All text linked to Text Styles
[ ] No overridden fonts

Components:
[ ] All UI elements use Component Library instances
[ ] Variants are properly named (Default, Hover, Active, Disabled, Error)
[ ] Component descriptions explain behaviour

Assets:
[ ] Icons exportable as SVG
[ ] Images exportable as PNG @2x
[ ] Logo available in all formats

Prototype:
[ ] All primary flows wired
[ ] Starting screen set
[ ] Animations match Design.md specs

Documentation:
[ ] Frame descriptions filled in
[ ] Interactions annotated
[ ] Edge cases noted in frame comments
```

**Write `docs/handoff.md`:**
```markdown
# [AppName] — Developer Handoff Notes

## Tech Stack Recommendation
- [Framework]
- [State management]
- [Navigation library]
- [Key dependencies]

## Design Token Implementation
All tokens in Design.md should map to CSS variables / theme tokens.
See Design.md for the full list.

## Animation Specs
- Screen transitions: 280ms ease-in-out, slide from right
- Bottom sheet: 280ms cubic-bezier(.32,.72,0,1) slide up
- Toast: 240ms fade + scale in
- Press feedback: 80ms scale to 0.97

## Accessibility Notes
- Minimum touch target: 44×44px
- All interactive elements have accessible labels
- Contrast ratios meet WCAG AA (4.5:1 for body text)

## Edge Cases to Handle
[List specific edge cases you've designed for]

## Known Limitations / Future Scope
[What's in V2 that developers should be aware of]
```

> ✅ **End of Step 18:** The Figma file is a complete blueprint. Any developer can open it and start building without a single follow-up call.

---

### ✦ Step 19 · Get Paid 💸

**Deliverables to hand over to the client:**

```
Deliverable package:
[ ] Live prototype URL (Vercel)
[ ] Figma design file (shared with view access)
[ ] Brand guidelines PDF
[ ] Design system Figma file (or library)
[ ] Logo asset pack (all formats)
[ ] docs/handoff.md
[ ] Source code repository (if included in scope)
```

**Invoice checklist:**
- Discovery & Research
- UX Strategy (Personas, Flows, Problem Statements)
- Brand Identity (Logo + Guidelines)
- Design System
- UI/UX Design (all screens)
- Interactive Prototype
- Developer Handoff
- Revisions (specify number of rounds)

> 🎉 **You did it.** From brief to handoff, using AI at every step — without cutting corners on quality.

---

## Toolchain Quick Reference

| Phase | Tool | What You're Doing |
|-------|------|-------------------|
| Discovery | Gemini Deep Research | Market + competitor analysis |
| Discovery | Claude | Structuring brief into clean doc |
| Strategy | Claude Cowork (Projects) | Persistent project context |
| Strategy | Claude Cowork | Personas via mock user interviews |
| Strategy | Claude + Figma MCP | User flows created in FigJam |
| Strategy | You | Problem statements + hand sketches |
| Strategy | Claude | skills.md agent specialisation |
| Brand | Claude + Magnific MCP | Moodboards + logo SVG generation |
| Brand | Figma | Brand guidelines document |
| Brand | Figma | Design system + component library |
| Brand | You | Design.md — token documentation |
| UI/UX | Claude Cowork | PRD creation with full context |
| UI/UX | Claude Design | UI screen generation |
| Build | Antigravity | Full prototype build from all materials |
| Build | Vercel | Live deployment |
| Figma | html.to.design plugin | Prototype → Figma components |
| Handoff | Figma Dev Mode | Annotations + prototype wiring |
| Handoff | You | handoff.md — developer notes |

---

## Time Estimates

| Phase | Realistic Time |
|-------|---------------|
| Discovery & Research | 2–4 hours |
| UX Strategy & Personas | 3–5 hours |
| Figma Flows | 1–2 hours |
| Problem Statements + Sketches | 1–2 hours |
| Brand (Logo + Guidelines) | 3–6 hours |
| Design System | 2–4 hours |
| PRD | 1–2 hours |
| UI/UX Design (Claude Design) | 3–6 hours |
| Prototype Build (Antigravity) | 3–8 hours |
| Figma Export + Cleanup | 2–4 hours |
| Dev Handoff | 2–3 hours |
| **Total** | **~23–46 hours** |

> ⚡ With AI handling the heavy lifting at every stage, you can realistically deliver what used to take 6–8 weeks in **1–2 focused weeks**.

---

## Troubleshooting & Common Questions

**"The AI keeps using colours not in my design system"**
> Upload `Design.md` to Claude and start every session with: *"Use only tokens from Design.md for all colours, spacing, and typography."*

**"The prototype doesn't look like my Figma designs"**
> Provide Claude Design screenshots as reference images in Antigravity. Antigravity can use images as implementation targets.

**"html.to.design isn't mapping to my components properly"**
> Do the mapping manually for the most-used components first (Cards, Buttons, Inputs). These cover 80% of the work.

**"I don't know how to code — can I still use this?"**
> Yes. Antigravity writes all the code. Your job is to describe screens clearly, review the output, and iterate. The skills.md files teach the agent your design standards so it generates better code.

**"My client wants a Figma prototype, not a code prototype"**
> Build the code prototype first (much faster with AI), then use html.to.design to get the Figma version. You end up with both.

**"The figma.html board is getting too large"**
> This is normal for large projects. Split into multiple figma board files: `figma-onboarding.html`, `figma-core.html`, `figma-settings.html`.

---

*This workflow was built by a working UI/UX designer and refined across multiple real client projects. Every step reflects a real decision about which AI tools are best for which job, and where human judgement is irreplaceable.*

*Update this file as your workflow evolves. The best version of this document is the one you've personalised for how you actually work.*

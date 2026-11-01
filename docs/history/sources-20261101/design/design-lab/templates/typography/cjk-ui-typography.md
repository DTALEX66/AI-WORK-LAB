# CJK UI typography rules

Use for Chinese/Japanese/Korean UI generated in Open Design.

## Font stacks

Prefer system-native stacks unless the brief requires a branded font:

```css
font-family: Inter, "SF Pro Display", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
```

For monospace HUD/terminal labels:

```css
font-family: "JetBrains Mono", "SF Mono", "Cascadia Mono", "Noto Sans Mono CJK SC", monospace;
```

## Sizing

```text
mobile body: 14-16px
mobile metadata: 11-13px
desktop body: 15-17px
large title: 28-56px depending on screen
button label: 13-16px
```

## Line-height

```text
Chinese body: 1.55-1.85
Chinese dense UI: 1.35-1.55
English UI: 1.35-1.55
HUD metadata: 1.1-1.3
```

## Letter spacing

- Chinese body: usually 0 to 0.04em.
- Large all-caps English labels: 0.06 to 0.14em.
- Do not apply wide tracking to long Chinese paragraphs.

## Rules

- Chinese button labels should be short: 2-6 characters when possible.
- Avoid mixing too many weights; use size, color, and spacing first.
- Reserve monospace for data, codes, timestamps, and HUD labels.
- Avoid thin gray Chinese text on dark backgrounds.
- Long Chinese menu items need wrapping or explicit abbreviation.

## Open Design prompt add-on

```text
Use CJK-safe typography: readable Chinese font fallback, generous line-height, short labels, strong contrast, and no thin low-contrast Chinese body text.
```

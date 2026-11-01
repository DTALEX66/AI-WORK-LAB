# Surgical removal of baked CCTV labels

## Trigger

Use this workflow when a supplied CCTV/gameplay asset is visually correct except for one baked label, fixed floor route, answer cue, or pseudo-text region.

## Scope contract

Before editing, restate the exact visual contract:

- **Preserve:** authored scene, cabin/subject, doors, arrows, lighting, perspective, scanlines, texture, and all surrounding composition.
- **Remove:** only the user-identified baked pixels (for example `7F → 8F`).
- **Do not add unless explicitly requested:** black cards, broad opaque strips, duplicate runtime readouts, procedural replacement art, or whole-image fallbacks.

A red circle on a screenshot defines a local target, not permission to redesign the whole frame.

## Preferred repair order

1. Locate every runtime variant that contains the same defect (up/down, mobile/desktop, generated target copies).
2. Identify a tight normalized bounding box around only the unwanted glyphs.
3. Build a color/brightness mask for glyph pixels inside that box; do not mask the whole rectangle.
4. Dilate by only 1–2 px to catch antialiasing.
5. Inpaint masked pixels from neighboring texture (OpenCV TELEA radius ~3 is a useful starting point).
6. Optimize the repaired PNG without resizing or changing composition.
7. Remove renderer workarounds that were introduced solely to hide the label.
8. Rebuild generated platform assets from the repaired canonical source.

## Minimal OpenCV pattern

```python
img = cv2.imread(path)
h, w = img.shape[:2]
x1, x2 = int(w * 0.435), int(w * 0.565)
y1, y2 = int(h * 0.285), int(h * 0.345)
roi = img[y1:y2, x1:x2]
b, g, r = cv2.split(roi)
mask = ((g.astype(int) > r.astype(int) + 16)
        & (g.astype(int) > b.astype(int) + 9)
        & (g > 72)).astype(np.uint8) * 255
mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
full = np.zeros((h, w), np.uint8)
full[y1:y2, x1:x2] = mask
cleaned = cv2.inpaint(img, full, 3, cv2.INPAINT_TELEA)
```

Thresholds and bounds are asset-specific; inspect the result instead of treating them as constants.

## Verification

Verify the canonical source images and the official runtime separately:

- unwanted label is absent in every affected variant;
- elevator/subject and composition remain visible;
- arrows, center guides, scanlines and texture remain intact;
- no black strip/card or duplicate floor label was introduced;
- generated target package contains the repaired images;
- official Developer Tool screenshot confirms the real runtime result;
- add a regression assertion forbidding the previously introduced broad renderer mask.

## Failure pattern to avoid

Do not interpret “去掉这个显示” as “remove the whole image” or “replace the scene with a black procedural display.” If a first overlay leaks, that does not justify expanding the overlay. Return to the source asset and remove only the offending pixels.

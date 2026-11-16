# Ideogram captions

ideogram-4 was trained only on JSON captions, so write one for every request and pass it as the prompt (in a file, with `@caption.json`). Source: Ideogram's [prompting guide](https://github.com/ideogram-oss/ideogram4/blob/main/docs/prompting.md).

## The shape

```json
{
  "high_level_description": "One or two sentences about the whole picture.",
  "style_description": {
    "aesthetics": "keywords for the feel",
    "lighting": "where the light comes from and its quality",
    "medium": "illustration",
    "art_style": "what the art looks like",
    "color_palette": ["#6B4A2B", "#A9773E", "#F2E2B6"]
  },
  "compositional_deconstruction": {
    "background": "The setting behind everything.",
    "elements": [
      {"type": "obj", "bbox": [300, 250, 950, 750], "desc": "An object, described in detail."},
      {"type": "text", "bbox": [380, 290, 520, 710], "text": "TRAILHEAD", "desc": "How the letters look and where they sit."}
    ]
  }
}
```

## Rules

- `compositional_deconstruction` is required, with `background` before `elements`. The other two top-level keys are optional but recommended.
- `style_description` holds exactly one of `photo` (camera and lens, with `medium: "photograph"`) or `art_style` (anything else), and also needs `aesthetics`, `lighting` and `medium`.
- **Key order matters**, because the model was trained on one order:
  - photo: `aesthetics`, `lighting`, `photo`, `medium`, `color_palette`
  - anything else: `aesthetics`, `lighting`, `medium`, `art_style`, `color_palette`
  - an `obj` element: `type`, `bbox`, `desc`, `color_palette`
  - a `text` element: `type`, `bbox`, `text`, `desc`, `color_palette`
- `bbox` is `[y_min, x_min, y_max, x_max]` from 0 to 1000, origin top left. Optional.
- `medium` is one of `photograph`, `illustration`, `3d_render`, `painting`, `graphic_design`, and so on.
- `color_palette`: uppercase `#RRGGBB` only, up to 16 for the picture and up to 5 per element. Include background colours too, and both highlight and shadow colours.
- Write the file as compact JSON with real characters, not `\u` escapes.

## Lettering

Give each line of text its own `text` element, with the exact wording in `text` and the look in `desc`. Ideogram spells it right and puts it in its box. It won't draw pixel art, so for a pixel-art sign either letter it on Ideogram and pixelate the result, or try Qwen and check the spelling letter by letter (Qwen's lettering hasn't been tested here).

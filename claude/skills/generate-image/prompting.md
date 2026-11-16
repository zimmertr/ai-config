# Prompting

What worked and what didn't in testing, then recipes for common jobs. The examples come from painting a glaciated volcano for a pixel-art game, but the lessons are general.

## Writing a prompt

- **Plain sentences, in this order:** the medium and purpose, the framing, the subject, its parts and where they are, the setting, the light, the style. For example - "A clean, crisp digital gouache illustration for a video game background, looking slightly down across rolling forested foothills toward one huge mountain standing alone in the middle distance. The whole mountain is visible, with clear blue sky on both sides. ... Strong light from the upper left."
- **Say where things are.** "A lower rounded shoulder on the left and a dark rock tooth low on the right flank" was followed. Qwen keeps left and right straight.
- **Describe irregularity outright.** Models default to tidy symmetry. "Glaciers flow between rock ridges" gave evenly spaced spokes; "glaciers of different widths joining and splitting around ridges of different lengths" didn't.
- **Say what's rare as rare.** "Blue icefalls" put ice towers everywhere; "icefalls appear only where a glacier drops over a steep step" put them in a few places.
- **Avoid words with a strong stock image.** "Crater" gave meteor streaks on Z-Image and a huge caldera on Qwen; "summit dome" with "large crater" in the negative prompt worked.
- **Watch framing words.** "World map", "landmark", "tile" and "three-quarter view" made a floating island cut out of the ground. "A landscape, the ground continues past every edge of the picture" kept it rooted.
- **Ask for the whole subject when it mustn't be cropped:** "standing alone in the middle distance, the whole mountain visible, with sky on both sides and above it", plus "cropped" in the negative prompt.
- **Naming a real place or thing as inspiration works** ("inspired by Mount Rainier"). Don't ask for the look of a specific existing game, film or artist; describe the qualities you want instead.

## Negative prompts (Qwen only)

List the failures you've seen or expect, as short phrases: `floating island, diorama, isometric tile, radial symmetry, evenly spaced ridges, perfect cone, cropped, text, border, frame, blurry, photo`. They nudge rather than forbid, so fix the main prompt first. Z-Image ignores them entirely.

## Size and seeds

- **Pick the size for where the picture goes**, and pass it with `--size`: the aspect ratio of the slot, about 1024 on the long side. Larger costs about three times as long for no more detail.
- **A pixel-art model's "pixels" are several model pixels wide** (about 4 for Qwen from a prompt alone). A whole subject in a 1024-wide picture is only about 250 of those across. If the target needs more, use the paint-then-repaint recipe.
- **Try new seeds before rewording.** Keep the seed fixed while you test a change in wording, so you see what the words did.

## Recipes

### Quick drafts

Z-Image, 4 to 8 seeds, a short prompt. Pick the composition you like, then rebuild it on Qwen: as an edit of the draft, or as a fuller prompt that describes what the draft got right.

### Repaint a picture and keep its layout

Qwen `edit`. Lead with the subject and an explicit instruction to keep the layout:

> Repaint this mountain as a detailed, beautiful 16-bit pixel art illustration of Mount Rainier. Keep the exact outline, position and size of the mountain and its rocky tooth on the right, and keep the foothills, forest and meadow where they are. [Then describe the content you want: snowfields, glaciers, crevasses, light.]

The output keeps whatever the input's composition is, faults included. Fix layout problems in the input picture.

### Paint first, then repaint as pixel art

For pixel art with more detail than a pixel-art prompt gives:

1. `gen` on Qwen: ask for "a clean, crisp digital gouache illustration", with flat shapes, hard edges and few colours, and put "pixel art" in the negative prompt. This gets the best composition.
2. `scale` it down to the target's real pixel size with `--resample box`, and `palette` it onto the project's palette if there is one. Then `scale` back up to about 1024 wide with `--resample nearest`.
3. `edit` on Qwen with the "Repaint this … as a detailed, beautiful 16-bit pixel art illustration of …, keep the exact outline …" prompt above, describing the content.
4. `scale` and `palette` the result down to the target size again.

In testing, this gave fine pixels, the painting's composition and far more detail than either step alone. Asking at step 3 to "redraw this as pixel art with clean clusters and a limited palette" gave chunky pixels instead.

### Match the style of an existing picture

Qwen `edit` with two pictures: `-i content.png -i style.png`, and "Repaint the first picture in exactly the style of the second picture: the same pixel size, colours and treatment. Keep the first picture's composition exactly." Results vary, so check that the style really carried over. Clean up both inputs first (flat backgrounds, no banding), because the edit copies their flaws.

### Variations of a picture

Z-Image `img2img` at 0.4 to 0.6 keeps the layout and changes the surface; 0.75 and up treats the input as a loose suggestion.

### Lettering

Ideogram with a JSON caption. Give each piece of text its own `text` element and box, and put the exact wording in `text`. See [ideogram.md](ideogram.md).

## Clean-up

- **Backgrounds:** if the picture will sit over something else, `cutout` the sky or flat background, then check the edge on a contact sheet (transparency shows as a checkerboard).
- **Size:** `scale` with `--resample box` to shrink a painting, and `nearest` to enlarge pixel art without blurring it.
- **Palette:** `palette --palette file.json` maps every pixel onto a project's colours (a list of hex strings or `[r, g, b]` lists, or an object holding one under `colors`). Smooth gradients like skies band badly, so cut those away first.
- **Only the material's colours:** `--groups snow,ice,rock` limits the match to named groups, when the palette file names them (`"groups": {"snow": [3, 4]}` or `"names": {"3": "snow[0]"}`). Matched to the whole palette, neighbouring pixels of one material land in unrelated groups. That looks noisy, and a palette with a second theme (night, dusk) turns them different colours. In testing, a mountain matched only to its snow, ice and rock groups used 32 colours instead of 179, looked like the project's own art, and stayed even in the second theme.
- **Small sprites:** shrunk to 10 to 15 pixels, AI sprites came out no better than simple drawn ones; the detail that makes them worthwhile doesn't survive. Use the models for pictures roughly 32 pixels and up.
- **Review again after clean-up.** Shrinking and palette mapping can reveal noise and mixed pixel sizes.

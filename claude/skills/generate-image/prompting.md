# Prompting

What worked and what didn't in testing, then recipes for common jobs. The examples come from painting a glaciated volcano for a pixel-art game, but the lessons are general.

## Writing a prompt

- **Plain sentences, in this order:** the medium and purpose, the framing, the subject, its parts and where they are, the setting, the light, the style. For example - "A clean, crisp digital gouache illustration for a video game background, looking slightly down across rolling forested foothills toward one huge mountain standing alone in the middle distance. The whole mountain is visible, with clear blue sky on both sides. ... Strong light from the upper left."
- **Say where things are.** "A lower rounded shoulder on the left and a dark rock tooth low on the right flank" was followed. Qwen keeps left and right straight.
- **Describe irregularity outright.** Models default to tidy symmetry. "Glaciers flow between rock ridges" gave evenly spaced spokes; "glaciers of different widths joining and splitting around ridges of different lengths" didn't.
- **Say what's rare as rare.** "Blue icefalls" put ice towers everywhere; "icefalls appear only where a glacier drops over a steep step" put them in a few places.
- **Whatever you name gets drawn everywhere.** "Rock broken into ledges, ribs and cracks" turned a whole cliff into brickwork, and "an icefall of blue blocks" put blue blocks over the whole glacier. Say how far each thing reaches: "a few ledges near the top", "only where it drops over the step".
- **Every word is drawn literally.** "A square summit block" and "a flat-topped tower" became chimneys, "smooth slabs" became a blank face, and "water streaks" became icicles. Describe shapes as rough and broken rather than as solids, and say what a thing is not ("dark grey stains, not ice").
- **Don't ask for a blurred background** in a picture that will be matched to a palette. Ideogram's out-of-focus trees turned into flat blobs once matched. Ask for a crisp background, or a plain one you cut away.
- **Don't ask for distance or haze.** "Pale and hazy, across many miles of air" washed a mountain range out to almost white. Paint it crisp and make it look far afterwards, with a palette or an overlay.
- **Avoid words with a strong stock image.** "Crater" gave meteor streaks on Z-Image and a huge caldera on Qwen; "summit dome" with "large crater" in the negative prompt worked.
- **Watch framing words.** "World map", "landmark", "tile" and "three-quarter view" made a floating island cut out of the ground. "A landscape, the ground continues past every edge of the picture" kept it rooted.
- **Ask for the whole subject when it mustn't be cropped:** "standing alone in the middle distance, the whole mountain visible, with sky on both sides and above it", plus "cropped" in the negative prompt. If it still runs off an edge, give it a share of the frame: "it fills only the middle half of the picture's width, and its ridges come down to low ground well inside the picture."
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

It does sharpen peaks, towers and other tops into points unless told not to. Name the shapes to keep ("keep the exact silhouette of every summit: the blunt square tops, the leaning one. Do not sharpen any summit into a point.") and put `pointed peaks, needles, daggers` in the negative prompt.

### Paint first, then repaint as pixel art

For pixel art with more detail than a pixel-art prompt gives:

1. `gen` on Qwen: ask for "a clean, crisp digital gouache illustration", with flat shapes, hard edges and few colours, and put "pixel art" in the negative prompt. This gets the best composition.
2. `scale` it down to about 400 wide with `--resample box` (or the target's real size, if that's bigger), and `palette` it onto the project's palette if there is one. Then `scale` back up to about 1024 wide with `--resample nearest`. The repaint draws pixels the size of its input's: an input shrunk to 210 wide came back with pixels twice the target's and flat, empty faces.
3. `edit` on Qwen with the "Repaint this … as a detailed, beautiful 16-bit pixel art illustration of …, keep the exact outline …" prompt above, describing the content.
4. `scale` and `palette` the result down to the target size again.

In testing, this gave fine pixels, the painting's composition and far more detail than either step alone. Don't skip step 3 because the palette is small: a mountain range shrunk 2.2 times straight onto six colours came out speckled, and repainted first it came out clean. Only a picture made at close to its final size matched cleanly without it. Asking at step 3 to "redraw this as pixel art with clean clusters and a limited palette" gave chunky pixels instead.

### A strip that tiles sideways

For a background that wraps round as it scrolls. Asking for matching ends doesn't work: "at both edges it dips to the same low saddle" dropped the range to the ground at both ends.

1. `gen` a wide picture (`--size 1024x384`) with the subject running from edge to edge.
2. `roll` it by half, so the join sits in the middle. The new edges are the old picture's unbroken middle, so they already meet.
3. Qwen `edit` the rolled picture: "Fill the gap in the middle with more [subject], so it runs on unbroken from the left edge to the right edge. Keep everything else exactly as it is: the left quarter and the right quarter of the picture must not change at all." In testing, the edges kept their outline to within 3 pixels; only the colours shifted a little.
4. Check the join by laying two copies side by side.

### Match the style of an existing picture

Qwen `edit` with two pictures: `-i content.png -i style.png`, and "Repaint the first picture in exactly the style of the second picture: the same pixel size, colours and treatment. Keep the first picture's composition exactly." Results vary, so check that the style really carried over. Clean up both inputs first (flat backgrounds, no banding), because the edit copies their flaws.

### Variations of a picture

Z-Image `img2img` at 0.4 to 0.6 keeps the layout and changes the surface; 0.75 and up treats the input as a loose suggestion.

### Lettering

Qwen spells well from a plain prompt that quotes each line and says where it goes: "Above the opening, big routed cream capitals read \"TRAIL REGISTER\"." Use Ideogram, with a JSON caption and a box per line, when each line must sit in an exact place. See [ideogram.md](ideogram.md).

Lettering survives a repaint when the prompt says "Keep the lettering exactly as it is, letter for letter:" and quotes it, and `misspelled, garbled text` is in the negative prompt. Check the spelling after every step. Shrunk to pixel art, letters about 7 pixels tall or more stayed clear; at 5 they turned lumpy.

## Clean-up

- **Backgrounds:** if the picture will sit over something else, `cutout` the sky or flat background, then check the edge on a contact sheet (transparency shows as a checkerboard).
- **Size:** `scale` with `--resample box` to shrink a painting, and `nearest` to enlarge pixel art without blurring it.
- **Palette:** `palette --palette file.json` maps every pixel onto a project's colours (a list of hex strings or `[r, g, b]` lists, or an object holding one under `colors`). Smooth gradients like skies band badly, so cut those away first.
- **Only the material's colours:** `--groups snow,ice,rock` limits the match to named groups, when the palette file names them (`"groups": {"snow": [3, 4]}` or `"names": {"3": "snow[0]"}`). Matched to the whole palette, neighbouring pixels of one material land in unrelated groups. That looks noisy, and a palette with a second theme (night, dusk) turns them different colours. In testing, a mountain matched only to its snow, ice and rock groups used 32 colours instead of 179, looked like the project's own art, and stayed even in the second theme.
- **Cut away what you won't keep before matching**, and list only the groups of what's left. Every other group you allow steals pixels: a cliff matched with the vegetation groups allowed put dark green in every rock shadow, and a pale rock face brighter than the top of its own group fell onto the snow, sky or yellow-leaf group, whichever was allowed.
- **Split materials that share a brightness.** Sunlit rock and snow are both near white, so in one match the rock fell onto the snow colours and the whole range looked snowbound. Pick out one material by how it looks with `--part`, which sends the pixels that meet its conditions to their own groups: `--groups rock --part 'snow:light>215,sat<40,blue>0'` (bright, unsaturated and bluish is snow).
- **Small sprites:** shrunk to 10 to 15 pixels, AI sprites came out no better than simple drawn ones; the detail that makes them worthwhile doesn't survive. Use the models for pictures roughly 32 pixels and up.
- **Review again after clean-up.** Shrinking and palette mapping can reveal noise and mixed pixel sizes.

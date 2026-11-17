---
name: generate-image
description: Make pictures with the image models on TJ's own GPU (llama-swap on the R9700), review them yourself, re-prompt until they're right, then show TJ your pick. Use whenever a task needs a picture (artwork, an illustration, a background, concept art, mockup imagery, pixel art, lettering) or needs an existing picture repainted, in any project, and when TJ types /generate-image.
---

# Generate image

llama-swap serves five image models on TJ's R9700. You write the prompts, look at every result yourself, and keep improving the prompt until the picture does the job. Then you normally show TJ your pick.

## Before you start

- **A project's own rules come first.** If the project has image or art rules (its CLAUDE.md points to them), read them before writing a prompt. They win over the general advice here.
- **One model is loaded at a time.** An image request unloads whatever llama-swap has loaded, including the Qwen coding model another session may be using. `imagegen.py` waits up to five minutes for a busy language model to go idle, then goes ahead and says so. Don't run several jobs in parallel.
- **Work in a job folder in the session's scratchpad**, one folder per job, for example `<scratchpad>/images/<job>`. Copy any input pictures into it first: the container sees only that folder. Copy keepers into the project yourself afterwards.

## Running it

Everything runs in Docker through `run.sh`, which reads llama-swap's address and API key from the cluster with kubectl. The first run builds the image.

```sh
R=~/.claude/skills/generate-image/run.sh
J=<scratchpad>/images/cabin
$R $J models                                    # what's available and what's loaded
$R $J gen qwen-image-2.1 @prompt.txt --neg @neg.txt --seeds 1,2,3 --size 1024x640 --out draft
$R $J edit qwen-image-2.1 @repaint.txt -i draft-s2.png --seeds 5,6 --size 1024x640 --out paint
$R $J img2img z-image-turbo "..." -i draft-s2.png -t 0.6 --size 1024x640 --out var
$R $J sheet sheet.png draft-s1.png draft-s2.png draft-s3.png --cols 3 --width 400
```

- `@file` reads a prompt from a file in the job folder. Write long prompts to files; shell quoting mangles them.
- Each picture is saved as `<out>-s<seed>.png` and logged to `log.jsonl` with its model, seed, size, prompt and negative prompt, so any pick can be made again.
- Clean-up commands, all local: `scale` (to a width, a height or by a factor, or stretched to both a width and a height), `roll` (slide sideways with wrap-around, to fix the join of a strip that tiles), `palette` (onto a project's palette file, or only some named groups of its colours, sending pixels that look a certain way to other groups, or N colours), `cutout` (make a sky or flat background transparent), `sheet` (a labelled contact sheet; transparency shows as a checkerboard), `page` (the approval page). Run `$R $J <command> --help` for the options.

## Choosing a model

| Model | Use it for | Avoid it for |
|---|---|---|
| `qwen-image-2.1` | Almost everything: paintings, pixel art, scenes, lettering, and repainting a picture you give it while keeping its layout. Follows long prompts and negative prompts. About 40 s from a prompt, 50 to 75 s for an edit | Quick throwaway drafts |
| `z-image-turbo` | Fast drafts, 5 to 15 s: try many compositions, then take the best to Qwen | Fine detail; anything that needs a negative prompt (it ignores them) |
| `z-image-turbo-pixel-art` | A softer, more detailed pixel look than plain Z-Image | Crisp pixels; it smears into gradients |
| `z-image-turbo-trailhead` | trailhead's art: Z-Image with a LoRA trained on the game's own pictures | Other projects; overhead map views |
| `ideogram-4` | Lettering that must sit in an exact place, exact layouts with boxes, colour palettes | Pixel art (it paints illustrations instead); plain-sentence prompts |

Strengths, weaknesses, settings and known bugs for each: [models.md](models.md). Ideogram needs a JSON caption, which you write yourself: [ideogram.md](ideogram.md).

## Writing the prompt

The full advice and the tested recipes are in [prompting.md](prompting.md). The rules that matter most:

- **Describe what's in the picture, in plain sentences:** the subject, where it is, how it's framed, the light, the style. Specific beats adjectives.
- **Say the size when it matters.** The default is 1024 × 1024. Pass `--size` for a landscape, a banner or a target aspect ratio. Bigger than about 1024 on the long side costs about three times as long for no more detail.
- **Framing words change everything.** "World map landmark" draws a floating island tile; "a landscape where the ground continues past every edge" doesn't. Say "the whole X visible, with sky on both sides" when nothing may be cropped.
- **Name failures in a negative prompt** (Qwen only): `floating island, diorama, radial symmetry, text, border, blurry`. It helps, but wording in the main prompt helps more.
- **For pixel art, name the content, not the technique.** "Clusters", "limited palette" and "outline" switch on a stock chunky style.

## The loop

1. **Write the brief.** Before the first prompt, write down what the picture is for and a short checklist it must pass: from the need, from the project's rules, and from the review list below.
2. **Generate a round.** One prompt on 2 to 4 seeds.
3. **Review every picture yourself.** Open each one with Read at full size, and make a contact sheet to compare them. Zoom into crops wherever detail matters. Check each against the brief's checklist.
4. **Decide.** If one passes, go on to step 6. If not, write down what's wrong and change one thing: the seed, a sentence of the prompt, the negative prompt, the strength, the input picture, or the model. Changing everything at once hides what worked.
5. **Repeat, up to 6 rounds.** If six rounds haven't produced a picture that passes, stop. Say what you tried, what still fails, and show the closest one.
6. **Clean up** if the project needs it: cut out the background, scale to the target size, map onto the project's palette. Then review the cleaned-up picture again; clean-up can reveal faults.
7. **Present your pick.** Make the approval page and publish it as an Artifact (see below). Normally, ask TJ whether he approves.

**Approval is the default, not a gate.** When TJ is around, show the page and ask. When you're working on your own, say overnight, don't stop and wait: use your pick, note why in the job folder, and carry on with the bigger task. Gather every picture you picked that way onto one review page, and give TJ its link when he's back.

## Reviewing a picture

Check, every time:

- **Does it do the job?** The subject, the composition and the mood the brief asked for.
- **Is anything wrong in it?** Extra or missing parts, garbled text, streaks, watermarks or marks in a corner, things cut off at the edges, repeated patterns, a floating island where you wanted a landscape.
- **Does it fit beside what's already there?** The same style, light direction, pixel size and palette as the project's other art. Never put chunky pixels beside fine ones.
- **Is it the right size and shape** for where it goes?
- **Does it hold up close?** Zoom into crops. Smudged areas, mixed pixel sizes and noise hide at thumbnail size.

## The approval page

```sh
$R $J page index.html --pick paint-s5.png --alt paint-s6.png --alt draft-s2.png \
  --title "Cabin in the snow" --why "Seed 5 has the clearest roofline and the warmest windows." --pixelated
```

It shows your pick with your reason, two runners-up, and under each a folded "How this was made" with the model, seed, size and prompts. Publish it with the Artifact tool: `file_path` is the page, and `files` maps each picture's file name to its path in the job folder. Use `--pixelated` for pixel art so it isn't blurred when scaled.

## Known problems

- **Z-Image image-to-image** crashes sd-server on both OpenAI image routes. `img2img` already uses sd-server's WebUI-style route through `/upstream`, which works.
- **A 502 or a dropped connection** means sd-server crashed. Look at the llama-swap pod's log (`kubectl -n llama-swap-system logs deploy/llama-swap -c llama-swap`). llama-swap starts it again on the next request.
- **LoRAs can't be chosen per request.** `z-image-turbo-pixel-art` and `z-image-turbo-trailhead` have their LoRAs built in, and a request's `lora` field does nothing. To train a LoRA of your own, see [lora.md](lora.md).
- **Ideogram given a plain sentence** answers with a grey "Image blocked by safety filter" picture. Write its JSON caption.

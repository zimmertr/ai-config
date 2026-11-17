# The image models

All five run in `sd-server` behind llama-swap on the R9700 (32 GB). Their sampler settings (steps, guidance) are fixed at startup in Kubernetes-Manifests' `ai/llama-swap/configs/config.yaml`; a request can still pass `--steps`. Timings below are measured on that card, for one picture, with the model already loaded. The first request after a swap adds about 10 to 30 s to load it.

## qwen-image-2.1

The workhorse. Qwen-Image 2.1 at Q8 with Qwen3-VL-8B as its text encoder, including its vision weights, so it can see pictures it's given.

- **Prompt only:** about 40 s at 1024 × 640. Follows long, specific natural-language prompts well: framing, light, which side a feature is on.
- **Edits:** 50 to 75 s. Give it one or more pictures and say what to change. It keeps the layout of the first picture very faithfully: outline, positions and sizes. That includes the input's faults, so fix the composition in the input, not the prompt.
- **Several input pictures:** "Repaint the first picture in the style of the second" carries some of the second picture's treatment over, but not reliably. Give it clean inputs: it copies banding and noise too.
- **Negative prompts:** honoured (guidance 6). They change the result, but less than rewording the main prompt.
- **Pixel art:** clean and convincing. Asked for pixel-art technique ("clusters", "limited palette", "crisp outline") it falls back to a stock style with chunky pixels about 8 model pixels wide. Asked to repaint a described subject as "a detailed 16-bit pixel art illustration", it keeps fine pixels (see the recipes in [prompting.md](prompting.md)).
- **Paintings:** asked for "a clean, crisp digital gouache illustration" it gave the best compositions of any model in testing.
- **Lettering:** good. Asked in plain words for a sign whose lines it quotes, it spelled every line right on every seed, up to four lines with unusual names, distances ("2.4 MI") and arrows. It places lines less exactly than Ideogram: one seed in three put a line somewhere else on the object. A repaint keeps lettering letter for letter when told to.
- **Size:** 1536 × 960 took 105 s against 38 s at 1024 × 640 and gave no finer detail.

## z-image-turbo

Z-Image Turbo at Q8 with Qwen3-4B as its text encoder, distilled to 8 steps.

- **Speed:** 5 to 15 s. Use it to try many compositions or ideas cheaply, then take the best to Qwen.
- **Negative prompts:** ignored. It runs at guidance 1, so `--neg` makes no difference at all.
- **Pixel art:** crisp and blocky by default when the prompt says "pixel art". Less detail than Qwen.
- **Image-to-image:** keeps the layout at a strength of 0.6 or less, and invents freely at 0.75 or more. It can't keep the layout and add a lot of detail at once; a blurred input comes back flat. Runs only through `img2img` (the OpenAI routes crash on it).
- **Word traps:** "crater" drew meteor streaks across the sky. "World map landmark" drew an isometric island tile with roads.

## z-image-turbo-pixel-art

Z-Image Turbo with the elusarca pixel-art LoRA applied to every request.

- Needs "pixel art" in the prompt.
- More detail than plain Z-Image, but softer: areas smear into gradients instead of clean pixels. Plain `z-image-turbo` won side by side for crisp pixel art.
- Everything else as `z-image-turbo`, including ignoring negative prompts.

## z-image-turbo-trailhead

Z-Image Turbo with trailhead's style LoRA applied to every request. It was trained on the game's own pixel art (see [lora.md](lora.md)), so use it for trailhead and nothing else.

- **Start the prompt with "pixel art, side view scene,"** then describe the subject. It draws scenes and landmarks in the game's look: fine pixels, golden larches, layered ridges, the game's softer palette.
- **Leave out the trigger word "trlhd".** The LoRA is always on, so the word changes nothing but gets drawn as lettering on signs.
- **Avoid "overhead map".** It comes back as a generic piece of the game's map instead of the subject.
- **A row of summits** tends to come out at nearly even heights. Say how they differ, or fix it in a later step.
- Everything else as `z-image-turbo`: 15 to 20 s, no negative prompts.

## ideogram-4

Ideogram 4 at Q4, streaming its weights from RAM.

- **Speed:** about 90 s at 1024 × 1024.
- **Prompts:** only its JSON caption format ([ideogram.md](ideogram.md)). A plain sentence returns a grey "Image blocked by safety filter" picture.
- **Lettering:** exact. It spelled two lines of sign text correctly and put them where their boxes said.
- **Layout:** follows bounding boxes for each element, and a colour palette of up to 16 hex colours.
- **Style:** paints polished illustrations or photographs. Asked for pixel art in `art_style`, it painted an illustration anyway.
- **Marks:** it left a small symbol in the bottom-right corner once. Check corners, and crop if needed.

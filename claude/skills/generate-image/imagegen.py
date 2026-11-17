"""Image generation on llama-swap's sd-server, and the clean-up around it.

Run it through run.sh, which supplies LS_URL and LS_KEY and mounts the job
folder as the working directory. Every path is relative to that folder.

  models                              list image models and what's loaded
  gen     MODEL PROMPT [options]      prompt only
  edit    MODEL PROMPT -i IMG [-i ..] repaint the pictures given
  img2img MODEL PROMPT -i IMG -t 0.6  start from a picture at a strength
  scale   IN OUT (--width N | --factor F) [--resample box|nearest|lanczos]
  palette IN OUT (--palette FILE | --colors N)
  cutout  IN OUT [--tolerance T]      make the background behind a subject transparent
  sheet   OUT IMG [IMG ..] [--cols N] [--width W]
  page    OUT --pick IMG [--alt IMG ..] --title T --why TEXT

A PROMPT starting with @ is read from that file. Every generated picture is
logged to log.jsonl with what made it, so it can be made again.

Keeps to Python 3.9 and imports Pillow only where pictures are touched, so
the request-building parts can be tested without it.
"""
import argparse
import base64
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

# The image models in llama-swap's config.yaml. Others it serves are not for
# this skill.
IMAGE_MODELS = ("qwen-image-2.1", "z-image-turbo", "z-image-turbo-pixel-art", "z-image-turbo-trailhead", "ideogram-4")
LOG = "log.jsonl"
BUSY_GPU_PERCENT = 20
WAIT_SECONDS = 300
POLL_SECONDS = 15


# ---------------------------------------------------------------------------
# Requests


def read_prompt(text):
    if text.startswith("@"):
        with open(text[1:], encoding="utf-8") as f:
            return f.read().strip()
    return text


def extra_args(seed, negative=None, steps=None):
    """Fields the OpenAI routes have no place for travel inside the prompt."""
    extra = {"seed": seed}
    if negative:
        extra["negative_prompt"] = negative
    if steps:
        extra["sample_params"] = {"sample_steps": steps}
    return extra


def with_extra(prompt, extra):
    return prompt + " <sd_cpp_extra_args>" + json.dumps(extra) + "</sd_cpp_extra_args>"


def parse_size(size):
    w, h = size.lower().split("x")
    return int(w), int(h)


def generation_request(model, prompt, seed, size, negative=None, steps=None):
    body = {
        "model": model,
        "prompt": with_extra(prompt, extra_args(seed, negative, steps)),
        "size": size,
        "n": 1,
        "output_format": "png",
    }
    return "/v1/images/generations", json.dumps(body).encode(), "application/json"


def multipart(fields, files, boundary="----generate-image"):
    out = []
    for name, value in fields.items():
        out.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, name, value)).encode())
    for path, data in files:
        head = "--%s\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"%s\"\r\nContent-Type: image/png\r\n\r\n"
        out.append((head % (boundary, os.path.basename(path))).encode() + data + b"\r\n")
    out.append(("--%s--\r\n" % boundary).encode())
    return b"".join(out), "multipart/form-data; boundary=" + boundary


def edit_request(model, prompt, seed, size, images, negative=None, steps=None):
    fields = {
        "model": model,
        "prompt": with_extra(prompt, extra_args(seed, negative, steps)),
        "n": "1",
        "output_format": "png",
        "size": size,
    }
    data, ctype = multipart(fields, images)
    return "/v1/images/edits", data, ctype


def img2img_request(model, prompt, seed, size, image, strength, negative=None, steps=None):
    """sd-server's WebUI-style route, through llama-swap's /upstream path. On
    the OpenAI routes, Z-Image's image-to-image fails an assertion and takes
    sd-server down; this route works for every model."""
    w, h = parse_size(size)
    body = {
        "prompt": prompt,
        "init_images": [base64.b64encode(image).decode()],
        "denoising_strength": strength,
        "width": w,
        "height": h,
        "seed": seed,
    }
    if negative:
        body["negative_prompt"] = negative
    if steps:
        body["steps"] = steps
    return "/upstream/%s/sdapi/v1/img2img" % model, json.dumps(body).encode(), "application/json"


def image_from_response(payload):
    if "images" in payload:
        return base64.b64decode(payload["images"][0])
    return base64.b64decode(payload["data"][0]["b64_json"])


def http(path, data=None, ctype=None, timeout=1800):
    headers = {"Authorization": "Bearer " + os.environ["LS_KEY"]}
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(os.environ["LS_URL"].rstrip("/") + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---------------------------------------------------------------------------
# Sharing the GPU


def gpu_percent(metrics_text):
    for line in metrics_text.splitlines():
        if line.startswith("llamaswap_gpu_util_percent"):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def busy_other_model(running, metrics_text):
    """The loaded model that would be unloaded mid-request, or None. llama-swap
    doesn't report requests in flight, so a loaded language model with the
    GPU busy counts as one."""
    for entry in running.get("running", []):
        if entry.get("model") not in IMAGE_MODELS and entry.get("state") == "ready":
            if gpu_percent(metrics_text) >= BUSY_GPU_PERCENT:
                return entry["model"]
    return None


def wait_for_gpu(fetch=None, sleep=time.sleep, clock=time.monotonic, limit=WAIT_SECONDS):
    fetch = fetch or (lambda: (json.loads(http("/running")), http("/metrics").decode()))
    start = clock()
    while True:
        running, metrics = fetch()
        model = busy_other_model(running, metrics)
        if model is None:
            return None
        if clock() - start >= limit:
            print("%s is still busy after %d s; going ahead anyway" % (model, limit), file=sys.stderr)
            return model
        print("%s is busy; waiting" % model, file=sys.stderr)
        sleep(POLL_SECONDS)


# ---------------------------------------------------------------------------
# Running a job


def log_entry(**fields):
    fields["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return json.dumps(fields, ensure_ascii=False)


def run_requests(args, build):
    prompt = read_prompt(args.prompt)
    negative = read_prompt(args.neg) if args.neg else None
    if args.model not in IMAGE_MODELS:
        sys.exit("unknown image model %r; use one of %s" % (args.model, ", ".join(IMAGE_MODELS)))
    for seed in args.seeds:
        if not args.no_wait:
            wait_for_gpu()
        out = "%s-s%d.png" % (args.out, seed)
        path, data, ctype = build(prompt, seed, negative)
        started = time.time()
        try:
            payload = json.loads(http(path, data, ctype))
        except urllib.error.HTTPError as e:
            sys.exit("%s: HTTP %d %s" % (out, e.code, e.read()[:300]))
        except urllib.error.URLError as e:
            sys.exit("%s: %s (a 502 or a dropped connection usually means sd-server crashed; see the llama-swap log)" % (out, e))
        with open(out, "wb") as f:
            f.write(image_from_response(payload))
        seconds = round(time.time() - started)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(log_entry(file=out, mode=args.cmd, model=args.model, seed=seed, size=args.size,
                              prompt=prompt, negative=negative, steps=args.steps,
                              images=getattr(args, "image", None), strength=getattr(args, "strength", None),
                              seconds=seconds) + "\n")
        print("%s  %d s" % (out, seconds))


def cmd_models(args):
    ids = [m["id"] for m in json.loads(http("/v1/models"))["data"]]
    loaded = [r["model"] for r in json.loads(http("/running")).get("running", [])]
    for m in IMAGE_MODELS:
        print("%-26s %s" % (m, "loaded" if m in loaded else ("available" if m in ids else "MISSING from llama-swap")))
    others = [m for m in loaded if m not in IMAGE_MODELS]
    if others:
        print("also loaded (unloaded by any image request): " + ", ".join(others))


def cmd_gen(args):
    run_requests(args, lambda p, s, n: generation_request(args.model, p, s, args.size, n, args.steps))


def cmd_edit(args):
    images = [(p, open(p, "rb").read()) for p in args.image]
    run_requests(args, lambda p, s, n: edit_request(args.model, p, s, args.size, images, n, args.steps))


def cmd_img2img(args):
    image = open(args.image[0], "rb").read()
    run_requests(args, lambda p, s, n: img2img_request(args.model, p, s, args.size, image, args.strength, n, args.steps))


# ---------------------------------------------------------------------------
# Pictures


def parse_palette(data):
    """Accepts a list of "#RRGGBB" strings or [r, g, b] lists, or an object
    holding one under "colors" or "day"."""
    if isinstance(data, dict):
        data = data.get("colors") or data.get("day")
    out = []
    for c in data:
        if isinstance(c, str):
            c = c.lstrip("#")
            out.append((int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)))
        else:
            out.append(tuple(int(v) for v in c[:3]))
    return out


def group_indices(data, groups):
    """The palette entries in the named groups. A palette file names them either
    as "groups": {"snow": [3, 4, 5]} or, per entry, as "names": {"3": "snow[0]"}."""
    wanted = set(groups)
    if isinstance(data, dict) and "groups" in data:
        return sorted(i for g in wanted for i in data["groups"].get(g, []))
    if isinstance(data, dict) and "names" in data:
        return sorted(int(i) for i, n in data["names"].items() if n.split("[")[0] in wanted)
    raise ValueError("the palette file names no groups")


PART_KEYS = ("light", "sat", "blue")


def parse_part(spec):
    """A --part option, "snow,ice:light>215,sat<40,blue>0": the groups, then the conditions a
    pixel must all meet to go to them. light is the mean of red, green and blue, sat is the
    largest minus the smallest, blue is blue minus red; each from 0 to 255."""
    groups, _, conds = spec.partition(":")
    out = []
    for c in filter(None, conds.split(",")):
        for op in ("<", ">"):
            key, sep, val = c.partition(op)
            if sep:
                break
        if not sep or key.strip() not in PART_KEYS:
            raise ValueError("a condition is light, sat or blue, then < or >, then a number: " + c)
        out.append((key.strip(), op, float(val)))
    if not groups or not out:
        raise ValueError("a part is GROUPS:CONDITIONS, for example snow:light>215,sat<40")
    return groups.split(","), out


def part_mask(a, conds):
    """Which pixels of an (n, 3) float array meet every condition."""
    import numpy as np
    m = np.ones(len(a), bool)
    for key, op, val in conds:
        v = {"light": a.mean(1), "sat": a.max(1) - a.min(1), "blue": a[:, 2] - a[:, 0]}[key]
        m &= (v > val) if op == ">" else (v < val)
    return m


# Perceptual weights: green counts most, blue least.
WEIGHTS = (0.3, 0.59, 0.11)


def nearest_index(rgb, palette):
    best, best_d = 0, None
    for i, p in enumerate(palette):
        d = sum(w * (a - b) ** 2 for w, a, b in zip(WEIGHTS, rgb, p))
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


def scale_size(w, h, width=None, height=None, factor=None):
    if bool(factor) == bool(width or height):
        raise SystemExit("scale: give --factor, or --width and/or --height")
    if width and height:
        # Both given: stretch to exactly that size, for a picture painted at one shape that has
        # to fill a slot of another.
        return width, height
    if width:
        return width, round(h * width / w)
    if height:
        return round(w * height / h), height
    return round(w * factor), round(h * factor)


def cmd_scale(args):
    from PIL import Image
    im = Image.open(args.input)
    size = scale_size(im.width, im.height, args.width, args.height, args.factor)
    filt = {"box": Image.BOX, "nearest": Image.NEAREST, "lanczos": Image.LANCZOS}[args.resample]
    im.resize(size, filt).save(args.output)
    print("%s %dx%d" % (args.output, size[0], size[1]))


def cmd_roll(args):
    # Slides the picture sideways with wrap-around, so the join of a strip that must tile sits in
    # the middle, where an edit can paint over it, and the edges are the old unbroken middle.
    from PIL import Image, ImageChops
    im = Image.open(args.input)
    shift = round(im.width * args.by)
    ImageChops.offset(im, shift, 0).save(args.output)
    print("%s rolled %d px" % (args.output, shift))


def cmd_palette(args):
    import numpy as np
    from PIL import Image
    im = Image.open(args.input).convert("RGBA")
    rgb = im.convert("RGB")
    if args.colors:
        out = rgb.quantize(colors=args.colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    else:
        with open(args.palette, encoding="utf-8") as f:
            data = json.load(f)
        full = np.array(parse_palette(data), float)

        def entries(groups):
            # Only the colours of the picture's own material, so a palette with
            # a second set of colours (a night theme, say) turns it over evenly.
            sel = group_indices(data, groups)
            if not sel:
                sys.exit("no palette entries in groups " + ",".join(groups))
            return sel

        a = np.asarray(rgb, float).reshape(-1, 3)
        # Each pixel's share of the palette: the first --part whose conditions it meets, else
        # --groups. Two materials of one brightness (sunlit rock, snow) can't be told apart by
        # nearest colour alone, so a part picks one out by what it looks like first.
        todo = np.ones(len(a), bool)
        shares = []
        for spec in args.part or []:
            groups, conds = parse_part(spec)
            m = todo & part_mask(a, conds)
            shares.append((entries(groups), m))
            todo &= ~m
        shares.append((entries(args.groups.split(",")) if args.groups else list(range(len(full))), todo))
        w = np.array(WEIGHTS)
        idx = np.zeros(len(a), int)
        for sel, m in shares:
            pal, rows = full[sel], np.where(m)[0]
            for i in range(0, len(rows), 65536):  # in chunks, so a big picture fits in memory
                r = rows[i:i + 65536]
                d = (((a[r, None, :] - pal[None, :, :]) ** 2) * w).sum(2)
                idx[r] = np.array(sel)[d.argmin(1)]
        out = Image.fromarray(full[idx].reshape(rgb.height, rgb.width, 3).astype("uint8"))
        allowed = len(set(i for sel, _ in shares for i in sel))
        print("colours used: %d of %d" % (len(np.unique(idx[np.asarray(im.getchannel("A")).reshape(-1) > 0])), allowed))
    out.putalpha(im.getchannel("A"))
    out.save(args.output)


def cmd_cutout(args):
    """Floods from the top edge through pixels close to their neighbour, so a
    smooth sky gradient goes and the subject's outline stops it."""
    from collections import deque
    from PIL import Image
    im = Image.open(args.input).convert("RGBA")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    q = deque((x, 0) for x in range(w))
    for x in range(w):
        seen[x] = 1
    t = args.tolerance
    while q:
        x, y = q.popleft()
        here = px[x, y]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                there = px[nx, ny]
                if abs(here[0] - there[0]) + abs(here[1] - there[1]) + abs(here[2] - there[2]) <= t:
                    seen[ny * w + nx] = 1
                    q.append((nx, ny))
    for i in range(w * h):
        if seen[i]:
            x, y = i % w, i // w
            r, g, b, _ = px[x, y]
            px[x, y] = (r, g, b, 0)
    im.save(args.output)
    print("%s: %d%% transparent" % (args.output, round(100 * sum(seen) / (w * h))))


def flatten(im):
    """Transparent areas over a checkerboard, so a cutout shows what it removed."""
    from PIL import Image
    if im.mode not in ("RGBA", "LA", "P"):
        return im.convert("RGB")
    im = im.convert("RGBA")
    board = Image.new("RGBA", im.size, (200, 200, 200, 255))
    dark = Image.new("RGBA", (8, 8), (150, 150, 150, 255))
    for y in range(0, im.height, 8):
        for x in range((y // 8) % 2 * 8, im.width, 16):
            board.paste(dark, (x, y))
    return Image.alpha_composite(board, im).convert("RGB")


def cmd_sheet(args):
    from PIL import Image, ImageDraw
    ims = [flatten(Image.open(p)) for p in args.images]
    cw = args.width
    ch = max(round(im.height * cw / im.width) for im in ims)
    rows = (len(ims) + args.cols - 1) // args.cols
    sheet = Image.new("RGB", (args.cols * cw, rows * (ch + 16)), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    for i, (path, im) in enumerate(zip(args.images, ims)):
        x, y = (i % args.cols) * cw, (i // args.cols) * (ch + 16)
        sheet.paste(im.resize((cw, round(im.height * cw / im.width)), Image.LANCZOS), (x, y))
        draw.text((x + 4, y + ch + 2), os.path.basename(path), fill=(230, 230, 230))
    sheet.save(args.output)
    print(args.output)


PAGE = """<title>%(title)s</title>
<style>
:root{--bg:#f4f5f7;--fg:#1c2230;--muted:#5d6676;--line:#d5dae3;--accent:#2f6fd0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#13161c;--fg:#e5e8ee;--muted:#9aa3b3;--line:#2b313c;--accent:#7aa7f0;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#13161c;--fg:#e5e8ee;--muted:#9aa3b3;--line:#2b313c;--accent:#7aa7f0;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding-block:28px 56px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:28px}
h1,h2{margin:0;text-wrap:balance} p{margin:0;max-width:68ch}
figure{margin:0;display:grid;gap:8px}
img{width:100%%;height:auto;display:block;border:1px solid var(--line);border-radius:4px;image-rendering:%(rendering)s}
.alts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,320px),1fr));gap:20px}
details{color:var(--muted);font-size:.85rem} summary{cursor:pointer;color:var(--accent)}
pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 0}
</style>
<main>
<h1>%(title)s</h1>
<p>%(why)s</p>
%(pick)s
%(alts)s
</main>
"""


def figure(path, label, entry):
    made = ""
    if entry:
        rows = ["model: %s" % entry.get("model"), "seed: %s" % entry.get("seed"), "size: %s" % entry.get("size")]
        if entry.get("strength") is not None:
            rows.append("strength: %s" % entry["strength"])
        rows.append("prompt: %s" % entry.get("prompt"))
        if entry.get("negative"):
            rows.append("negative: %s" % entry["negative"])
        made = "<details><summary>How this was made</summary><pre>%s</pre></details>" % html.escape("\n".join(rows))
    return "<figure><h2>%s</h2><img src=\"%s\" alt=\"%s\">%s</figure>" % (
        html.escape(label), html.escape(path), html.escape(label), made)


def read_log():
    entries = {}
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                entries[e["file"]] = e
    return entries


def build_page(title, why, pick, alts, entries, pixelated=False):
    alt_html = ""
    if alts:
        alt_html = "<div class=\"alts\">%s</div>" % "".join(
            figure(p, "Runner-up %d" % (i + 1), entries.get(p)) for i, p in enumerate(alts))
    return PAGE % {
        "title": html.escape(title), "why": html.escape(why), "rendering": "pixelated" if pixelated else "auto",
        "pick": figure(pick, "My pick", entries.get(pick)), "alts": alt_html,
    }


def cmd_page(args):
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(build_page(args.title, args.why, args.pick, args.alt or [], read_log(), args.pixelated))
    print(args.output)


# ---------------------------------------------------------------------------


def parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models")
    for name in ("gen", "edit", "img2img"):
        s = sub.add_parser(name)
        s.add_argument("model")
        s.add_argument("prompt")
        s.add_argument("--neg", help="negative prompt (Qwen only; Z-Image ignores it)")
        s.add_argument("--seeds", type=lambda v: [int(x) for x in v.split(",")], default=[1])
        s.add_argument("--size", default="1024x1024")
        s.add_argument("--steps", type=int)
        s.add_argument("--out", default="img", help="file name prefix")
        s.add_argument("--no-wait", action="store_true", help="don't wait for a busy language model")
        if name != "gen":
            s.add_argument("-i", "--image", action="append", required=True)
        if name == "img2img":
            s.add_argument("-t", "--strength", type=float, default=0.6)
    s = sub.add_parser("scale")
    s.add_argument("input")
    s.add_argument("output")
    s.add_argument("--width", type=int)
    s.add_argument("--height", type=int, help="with --width, stretch to exactly that size")
    s.add_argument("--factor", type=float)
    s.add_argument("--resample", choices=("box", "nearest", "lanczos"), default="box")
    s = sub.add_parser("roll", help="slide sideways with wrap-around, to move a tiling seam to the middle")
    s.add_argument("input")
    s.add_argument("output")
    s.add_argument("--by", type=float, default=0.5, help="fraction of the width (default half)")
    s = sub.add_parser("palette")
    s.add_argument("input")
    s.add_argument("output")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--palette")
    g.add_argument("--colors", type=int)
    s.add_argument("--groups", help="with --palette: use only these named groups of colours, comma-separated")
    s.add_argument("--part", action="append", metavar="GROUPS:CONDITIONS",
                   help="with --palette: send the pixels that meet every condition to these groups instead, "
                        "for example snow:light>215,sat<40,blue>0 (light, sat, blue; repeatable, first match wins)")
    s = sub.add_parser("cutout")
    s.add_argument("input")
    s.add_argument("output")
    s.add_argument("--tolerance", type=int, default=24)
    s = sub.add_parser("sheet")
    s.add_argument("output")
    s.add_argument("images", nargs="+")
    s.add_argument("--cols", type=int, default=2)
    s.add_argument("--width", type=int, default=640)
    s = sub.add_parser("page")
    s.add_argument("output")
    s.add_argument("--pick", required=True)
    s.add_argument("--alt", action="append")
    s.add_argument("--title", required=True)
    s.add_argument("--why", required=True)
    s.add_argument("--pixelated", action="store_true", help="show pixel art with hard edges")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    {"models": cmd_models, "gen": cmd_gen, "edit": cmd_edit, "img2img": cmd_img2img, "scale": cmd_scale, "roll": cmd_roll,
     "palette": cmd_palette, "cutout": cmd_cutout, "sheet": cmd_sheet, "page": cmd_page}[args.cmd](args)


if __name__ == "__main__":
    main()

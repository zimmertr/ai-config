"""Tests for the generate-image skill's imagegen.py: the parts that need neither
llama-swap nor Pillow."""
import base64
import importlib.util
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "imagegen", os.path.join(HERE, "..", "claude", "skills", "generate-image", "imagegen.py"))
ig = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ig)


def extra_of(prompt):
    return json.loads(prompt.split("<sd_cpp_extra_args>")[1].split("</sd_cpp_extra_args>")[0])


def test_extra_args_carry_seed_negative_and_steps():
    assert ig.extra_args(7) == {"seed": 7}
    assert ig.extra_args(7, "blurry", 20) == {"seed": 7, "negative_prompt": "blurry", "sample_params": {"sample_steps": 20}}


def test_generation_request_goes_to_the_openai_route():
    path, data, ctype = ig.generation_request("qwen-image-2.1", "a lake", 3, "1024x640", negative="text")
    body = json.loads(data)
    assert path == "/v1/images/generations"
    assert ctype == "application/json"
    assert body["model"] == "qwen-image-2.1"
    assert body["size"] == "1024x640"
    assert body["prompt"].startswith("a lake <sd_cpp_extra_args>")
    assert extra_of(body["prompt"]) == {"seed": 3, "negative_prompt": "text"}


def test_edit_request_sends_every_image_as_a_file():
    path, data, ctype = ig.edit_request("qwen-image-2.1", "repaint", 1, "1024x1024", [("a.png", b"AAA"), ("b.png", b"BBB")])
    assert path == "/v1/images/edits"
    boundary = ctype.split("boundary=")[1]
    assert data.count(("--" + boundary).encode()) == 1 + 5 + 2  # closing line, five fields, two files
    assert b'name="image[]"; filename="a.png"' in data and b"AAA" in data
    assert b'name="image[]"; filename="b.png"' in data and b"BBB" in data
    assert b'name="model"\r\n\r\nqwen-image-2.1' in data


def test_img2img_uses_the_webui_route_through_upstream():
    path, data, _ = ig.img2img_request("z-image-turbo", "dusk", 9, "1024x640", b"PNG", 0.6, negative="text", steps=8)
    body = json.loads(data)
    assert path == "/upstream/z-image-turbo/sdapi/v1/img2img"
    assert body["init_images"] == [base64.b64encode(b"PNG").decode()]
    assert (body["width"], body["height"], body["seed"]) == (1024, 640, 9)
    assert body["denoising_strength"] == 0.6
    assert body["negative_prompt"] == "text" and body["steps"] == 8


def test_image_from_either_response_shape():
    raw = base64.b64encode(b"img").decode()
    assert ig.image_from_response({"images": [raw]}) == b"img"
    assert ig.image_from_response({"data": [{"b64_json": raw}]}) == b"img"


def test_read_prompt_from_a_file(tmp_path):
    p = tmp_path / "prompt.txt"
    p.write_text("  a caption \n", encoding="utf-8")
    assert ig.read_prompt("@" + str(p)) == "a caption"
    assert ig.read_prompt("plain") == "plain"


METRICS = "# HELP x\nllamaswap_gpu_util_percent 87\nllamaswap_cpu_util_percent 3\n"
IDLE = "llamaswap_gpu_util_percent 2\n"
CODER = {"running": [{"model": "qwen3.6-35b-a3b", "state": "ready"}]}


def test_gpu_percent():
    assert ig.gpu_percent(METRICS) == 87.0
    assert ig.gpu_percent("nothing here") == 0.0


@pytest.mark.parametrize("running,metrics,expected", [
    (CODER, METRICS, "qwen3.6-35b-a3b"),
    (CODER, IDLE, None),
    ({"running": [{"model": "qwen-image-2.1", "state": "ready"}]}, METRICS, None),
    ({"running": [{"model": "qwen3.6-35b-a3b", "state": "starting"}]}, METRICS, None),
    ({"running": []}, METRICS, None),
])
def test_busy_other_model(running, metrics, expected):
    assert ig.busy_other_model(running, metrics) == expected


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def test_wait_returns_at_once_when_idle():
    clock = Clock()
    assert ig.wait_for_gpu(fetch=lambda: (CODER, IDLE), sleep=clock.sleep, clock=clock) is None
    assert clock.t == 0


def test_wait_until_the_language_model_goes_idle():
    clock = Clock()
    answers = iter([(CODER, METRICS), (CODER, METRICS), (CODER, IDLE)])
    assert ig.wait_for_gpu(fetch=lambda: next(answers), sleep=clock.sleep, clock=clock) is None
    assert clock.t == 2 * ig.POLL_SECONDS


def test_wait_gives_up_after_the_limit():
    clock = Clock()
    assert ig.wait_for_gpu(fetch=lambda: (CODER, METRICS), sleep=clock.sleep, clock=clock, limit=60) == "qwen3.6-35b-a3b"
    assert clock.t >= 60


def test_parse_palette_shapes():
    assert ig.parse_palette(["#FF0000", "00ff00"]) == [(255, 0, 0), (0, 255, 0)]
    assert ig.parse_palette([[1, 2, 3, 255]]) == [(1, 2, 3)]
    assert ig.parse_palette({"colors": ["#000000"]}) == [(0, 0, 0)]
    assert ig.parse_palette({"day": [[9, 9, 9]]}) == [(9, 9, 9)]


def test_group_indices_from_groups_or_names():
    assert ig.group_indices({"groups": {"snow": [3, 4], "rock": [7]}}, ["snow", "rock"]) == [3, 4, 7]
    assert ig.group_indices({"names": {"1": "snow[0]", "2": "grass[0]", "3": "snow[1]"}}, ["snow"]) == [1, 3]
    with pytest.raises(ValueError):
        ig.group_indices(["#000000"], ["snow"])


def test_nearest_index_weights_green_most():
    palette = [(0, 0, 0), (255, 255, 255), (200, 0, 0)]
    assert ig.nearest_index((190, 10, 10), palette) == 2
    assert ig.nearest_index((240, 240, 240), palette) == 1
    # Equal distance in red and blue, but blue counts for less, so black wins over a blue shift.
    assert ig.nearest_index((0, 0, 60), [(0, 0, 0), (0, 0, 130)]) == 0


def test_page_shows_pick_runners_up_and_how_each_was_made():
    entries = {"a.png": {"model": "qwen-image-2.1", "seed": 1, "size": "1024x640", "prompt": "<b>lake</b>", "negative": "text"}}
    page = ig.build_page("Lake", "Best light.", "a.png", ["b.png", "c.png"], entries, pixelated=True)
    assert page.startswith("<title>Lake</title>")
    assert "My pick" in page and "Runner-up 1" in page and "Runner-up 2" in page
    assert page.count("How this was made") == 1  # only a.png is in the log
    assert "&lt;b&gt;lake&lt;/b&gt;" in page and "<b>lake</b>" not in page
    assert "image-rendering:pixelated" in page


def test_parser_defaults():
    args = ig.parser().parse_args(["gen", "qwen-image-2.1", "a lake"])
    assert args.size == "1024x1024"
    assert args.seeds == [1]
    args = ig.parser().parse_args(["img2img", "z-image-turbo", "p", "-i", "a.png", "--seeds", "3,4"])
    assert args.strength == 0.6 and args.seeds == [3, 4] and args.image == ["a.png"]
    assert ig.parser().parse_args(["roll", "a.png", "b.png"]).by == 0.5


def test_only_the_four_image_models_are_allowed():
    assert ig.IMAGE_MODELS == ("qwen-image-2.1", "z-image-turbo", "z-image-turbo-pixel-art", "ideogram-4")

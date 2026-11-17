# Training a style LoRA

A LoRA is a small add-on (about 80 to 160 MB) that teaches Z-Image Turbo a project's look, so its pictures start in that style instead of a stock one. This is how one was trained on the R9700 with [ai-toolkit](https://github.com/ostris/ai-toolkit), what went wrong, and what the snapshots showed. The scripts are in [lora/](lora/).

**It needs TJ's okay first, every time.** It takes the GPU from llama-swap for hours and creates things on the cluster. Ask for exactly what you'll run: the namespace, the volume, the pod, the Kubernetes-Manifests PRs, and how long.

## Setting Up

1. **Free the GPU** with a Kubernetes-Manifests PR that sets llama-swap's replicas to 0 in `ai/llama-swap/kustomization.yml`. Scaling it by hand doesn't stick: Argo puts it back, and its ApplicationSet is managed by the root app. After the merge, refresh the `llama-swap` Argo app.
2. **Start the pod** from [lora/train.yml](lora/train.yml): a namespace, a 150 GiB scratch volume and a slim Python pod on the GPU node. The node has about 37 GB of free disk, too little for a ROCm PyTorch image, so PyTorch goes into a virtualenv on the volume.
3. **Install** with [lora/setup.sh](lora/setup.sh) in the pod: PyTorch for ROCm 7.2 at the versions ai-toolkit pins, ai-toolkit at a fixed commit, and its other requirements without letting pip swap PyTorch for a CUDA build. It ends with a matrix multiply on the GPU to prove the card works.
4. **Copy the dataset in** with `kubectl cp`, as pairs of `NAME.png` and `NAME.txt`.

## What the R9700 Needs

Each of these stopped a run before its first step:

- **No `PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`.** It causes an illegal memory access when ai-toolkit merges its training adapter. If anything in the pod sets it, start every process with `env -u PYTORCH_HIP_ALLOC_CONF`.
- **`low_vram: true`** in the model block.
- **No quantization** (`quantize: false`, `quantize_te: false`). Its library fails with this PyTorch ("Couldn't swap QLinear.weight"). Unquantized, a step takes about 4.3 s and uses about 20 GB.
- **Captions cached one at a time.** ai-toolkit encodes 16 at once by default, which filled the card. `setup.sh` patches that.

## The Dataset

- **Crops of the project's own art**, scaled up with nearest-neighbour so each art pixel is several model pixels. For example - 4× for pixel art, which paints at about that size anyway. 80 crops were plenty.
- **Captions say what's in each picture and which view it is**, after a trigger word: `trlhd, pixel art, side view scene, a turquoise mountain lake below a snowy peak`. Describing the content teaches the style instead of tying it to one subject.
- **The view in the captions decides what the prompts get back.** 72 of trailhead's 83 crops were overhead map views, and prompts that asked for a map came back as generic pieces of the map. Side-view prompts kept their subjects.

## Running a Sweep

[lora/sweep.sh](lora/sweep.sh) runs each line of `/work/run/queue.txt` (`NAME SET RANK LR STEPS EVERY`) one after another with [lora/train.sh](lora/train.sh), which writes the config with [lora/config.sh](lora/config.sh). Every run saves a snapshot and draws the same test prompts every EVERY steps, so one run shows its whole course.

- **Test prompts:** a few subjects from the training set and two that are nothing like it. For example - a desert canyon and a harbour town. If those still come back as asked, the prompts still steer it.
- **Every run is at its best early.** At rank 16 and a learning rate of 1e-4, that was steps 500 to 1,250. At rank 32 it was steps 250 to 500, about twice as fast. After that, each run copied the training pictures' layout instead of learning their style. So about 750 steps at rank 32 is enough, about an hour.
- **Doubling the learning rate** made the snapshots jump between looks, and none beat the slower runs.
- **Leaving a distinctive subset out** (the Monolith crops) didn't help: that run slid into copying sooner.

To try new prompts on a snapshot, run one step from it: `PRE=<snapshot.safetensors> PF=<prompts.yaml> sh train.sh NAME SET RANK 1e-4 1 250`. Its step-0 samples are the snapshot with those prompts.

## Serving It

1. **Copy the snapshots out** before anything else, and check one checksum against the pod's.
2. **Upload the pick to a private Hugging Face repo** under TJ's account, with a short model card. The token is `huggingface.token` in `~/.claude/secrets.json`.
3. **Add a model to llama-swap** in Kubernetes-Manifests, set up like `z-image-turbo-pixel-art`: the LoRA goes in through `--lora-model-dir` and a startup `--prompt "<lora:user/repo/file:1>"`, and an `env:` line names its full `/models/hf/` path so the downloader fetches it. The cluster's `llama-swap-hf-token` must be able to read TJ's private repos. If it can't, the downloader's log says "Repository not found".
4. **Clean up:** delete the namespace (which deletes the volume), revert the PR that paused llama-swap, refresh Argo and check llama-swap is running again.
5. **Test it through llama-swap** beside plain `z-image-turbo` on the same prompt and seeds, so you can see the LoRA is applied.

**The trigger word gets drawn as text** when the LoRA is always on: "trlhd" showed up on a sign. A built-in LoRA doesn't need it, so leave it out of prompts.

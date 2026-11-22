#!/bin/sh
# Inside the trainer pod: PyTorch for ROCm 7.2 (the versions ai-toolkit pins) and ai-toolkit at a fixed commit.
set -eu
cd /work
apt-get update -qq && apt-get install -y -qq ffmpeg >/dev/null
[ -d venv ] || python -m venv venv
# The venv is made above, at run time, so shellcheck has nothing to follow.
# shellcheck source=/dev/null
. venv/bin/activate
pip install -q --upgrade pip
pip install -q torch==2.13.0+rocm7.2 torchvision==0.28.0+rocm7.2 torchaudio==2.11.0+rocm7.2 --index-url https://download.pytorch.org/whl/rocm7.2
[ -d ai-toolkit ] || git clone -q https://github.com/ostris/ai-toolkit.git
cd ai-toolkit && git checkout -q d6a18ad72da9abca3ffb67ea8e42c25764eee61a
# torch is already the ROCm build; keep pip from replacing it with a CUDA one
grep -v -E '^(torch|torchvision|torchaudio)([=<> ]|$)' requirements.txt > /work/req-norocm.txt
sed -i 's#^-r requirements_base.txt#-r /work/ai-toolkit/requirements_base.txt#' /work/req-norocm.txt
pip install -q -r /work/req-norocm.txt
# Caching captions 16 at a time filled the 32 GB card before training began; one at a time is fine.
sed -i 's/^TEXT_EMBED_CACHE_BATCH = 16/TEXT_EMBED_CACHE_BATCH = 1/' toolkit/dataloader_mixins.py
grep -q '^TEXT_EMBED_CACHE_BATCH = 1 ' toolkit/dataloader_mixins.py
python - <<'PY'
import torch
print("torch", torch.__version__, "hip", torch.version.hip, "gpu", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
x = torch.randn(4096, 4096, device="cuda", dtype=torch.bfloat16); print("matmul ok", float((x @ x).float().abs().mean()))
PY

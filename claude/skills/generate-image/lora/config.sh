#!/bin/sh
# usage: config.sh NAME SET RANK LR STEPS SAVE_EVERY PROMPT_COUNT > NAME.yaml
# env PRE=<lora.safetensors> starts from a saved LoRA (with STEPS=1 this just draws its samples); env PF=<file> swaps the prompt file.
# One Z-Image Turbo LoRA run. Snapshots and sample pictures every SAVE_EVERY steps, same seeds each time.
N=$1 SET=$2 RANK=$3 LR=$4 STEPS=$5 EVERY=$6 NP=${7:-6}
cat <<Y
job: extension
config:
  name: "$N"
  process:
    - type: sd_trainer
      training_folder: /work/output
      device: cuda:0
      network: {type: lora, linear: $RANK, linear_alpha: $RANK${PRE:+, pretrained_lora_path: $PRE}}
      save: {dtype: float16, save_every: $EVERY, max_step_saves_to_keep: 40}
      datasets:
        - folder_path: /work/data/$SET
          caption_ext: txt
          caption_dropout_rate: 0.05
          cache_latents_to_disk: true
          resolution: [1024]
      train:
        batch_size: 1
        steps: $STEPS
        gradient_accumulation: 1
        train_unet: true
        train_text_encoder: false
        gradient_checkpointing: true
        noise_scheduler: flowmatch
        timestep_type: weighted
        optimizer: adamw
        lr: $LR
        dtype: bf16
        cache_text_embeddings: true
      model:
        name_or_path: Tongyi-MAI/Z-Image-Turbo
        arch: "zimage:turbo"
        assistant_lora_path: ostris/zimage_turbo_training_adapter/zimage_turbo_training_adapter_v2.safetensors
        quantize: false
        quantize_te: false
        low_vram: true
      sample:
        sampler: flowmatch
        sample_every: $EVERY
        width: 1024
        height: 1024
        prompts:
Y
head -n "$NP" "${PF:-/work/run/prompts.yaml}" | sed 's/^/          /'
cat <<Y
        neg: ""
        seed: 42
        walk_seed: false
        guidance_scale: 1
        sample_steps: 9
meta: {name: "$N", version: "1.0"}
Y

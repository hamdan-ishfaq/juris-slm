"""
train_overnight.py - TEST RUN (5 Steps)
=======================================
Purpose: Verify that training works and saves correctly before the long run.
"""

import os
import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Model Settings
MODEL_NAME = "unsloth/Phi-3-mini-4k-instruct"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True 

# LoRA Hyperparameters
LORA_R = 64
LORA_ALPHA = 16
LORA_DROPOUT = 0.0
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", 
                  "gate_proj", "up_proj", "down_proj"]

# Training Settings (TEST MODE)
OUTPUT_DIR = "./juris_model_smart"
MAX_STEPS = 500                      # <--- CHANGED TO 5 FOR QUICK TEST
BATCH_SIZE = 2
GRADIENT_ACCUM_STEPS = 4
LEARNING_RATE = 2e-4

# ==============================================================================
# MAIN PIPELINE
# ==============================================================================

def main():
    print("=" * 70)
    print("🧪 JURIS-SLM: TEST RUN (5 Steps)")
    print("=" * 70)

    # 1. Load Model
    print("\n[1/4] Downloading Base Model (Phi-3)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=LOAD_IN_4BIT,
    )

    # 2. Add Smart Adapters
    print("\n[2/4] Attaching Large Brain Adapters (Rank 64)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=TARGET_MODULES,
        bias="none",
        use_gradient_checkpointing=True,
        random_state=3407,
    )

    # 3. Load & Format Dataset
    print("\n[3/4] Downloading & Formatting Logic Dataset...")
    dataset = load_dataset("yahma/alpaca-cleaned", split="train")

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs       = examples["input"]
        outputs      = examples["output"]
        texts = []
        for instruction, input, output in zip(instructions, inputs, outputs):
            text = f"""<|system|>
You are a helpful assistant.<|end|>
<|user|>
{instruction}
{input}<|end|>
<|assistant|>
{output}<|end|>"""
            texts.append(text)
        return { "text" : texts, }

    pass_dataset = dataset.map(formatting_prompts_func, batched=True)

    # 4. Start Test Training
    print("\n[4/4] Starting 2-Minute Test Run...")
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=pass_dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            output_dir=OUTPUT_DIR,
            max_steps=MAX_STEPS,   # Uses the 5 steps here
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUM_STEPS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=3407,
        ),
    )

    trainer.train()

    # 5. Save
    print("\n💾 Saving Model...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print("✅ TEST PASSED! Verify the folder 'juris_model_smart' exists.")

if __name__ == "__main__":
    main()
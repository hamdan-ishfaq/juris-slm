import os
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

MODEL_NAME = "microsoft/Phi-3-mini-4k-instruct"
OUTPUT_DIR = "./juris_local_proof"
MAX_SEQ_LENGTH = 1024

LORA_R = 16
LORA_ALPHA = 16
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
]

# Training tweak: slightly longer but still CPU-friendly
MAX_STEPS = 1200
BATCH_SIZE = 1
GRADIENT_ACCUM_STEPS = 2
LEARNING_RATE = 2e-4

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("🔹 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print("🔹 Loading model in 4-bit...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        torch_dtype=torch.float16,
        load_in_4bit=True,
        trust_remote_code=True
    )

    model = prepare_model_for_kbit_training(model)

    print("🔹 Applying LoRA...")
    peft_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        target_modules=TARGET_MODULES,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    print("🔹 Loading dataset...")
    dataset = load_dataset("yahma/alpaca-cleaned", split="train[:2%]")  # slightly more data

    def format_fn(examples):
        texts = []
        for ins, outp, inp in zip(
            examples["instruction"],
            examples["output"],
            examples["input"]
        ):
            texts.append(
                f"<|system|>You are a helpful assistant.<|end|>\n"
                f"<|user|>{ins}\n{inp}<|end|>\n"
                f"<|assistant|>{outp}<|end|>"
            )
        return tokenizer(
            texts,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
            padding="max_length"
        )

    tokenized = dataset.map(format_fn, batched=True, remove_columns=dataset.column_names)

    print("🔹 Preparing Trainer...")
    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        max_steps=MAX_STEPS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUM_STEPS,
        learning_rate=LEARNING_RATE,
        fp16=True,
        logging_steps=1,
        save_steps=10,
        save_total_limit=2,
        report_to="none"
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
    )

    print("🚀 Starting training...")
    trainer.train()

    print("💾 Saving model locally...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print(f"✅ Local proof training complete! Model saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()

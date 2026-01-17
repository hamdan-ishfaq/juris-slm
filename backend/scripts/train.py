# train.py
import os
import sys
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from config import config

MODEL_NAME = config.models.llm_model
OUTPUT_DIR = config.paths.model_adapters
MAX_SEQ_LENGTH = config.models.max_seq_length
LORA_R = config.training.lora_r
LORA_ALPHA = config.training.lora_alpha
TARGET_MODULES = config.training.target_modules
MAX_STEPS = config.training.max_steps
BATCH_SIZE = config.training.batch_size
GRADIENT_ACCUM_STEPS = config.training.gradient_accumulation_steps
LEARNING_RATE = config.training.learning_rate

# Enable TF32 for faster matmul on Ampere+ GPUs (e.g., RTX 4050)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = True

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("🔹 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    print("🔹 Loading model in 4-bit...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        quantization_config=bnb_config,
        torch_dtype=torch.float16,
        trust_remote_code=True,
        attn_implementation="eager"
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
    dataset = load_dataset(config.training.dataset, split="train[:2%]")  # slightly more data

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
        tf32=True,
        logging_steps=1,
        save_steps=10,
        save_total_limit=None,  # keep all checkpoints so earlier ones remain usable
        report_to="none",
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
    )

    print("🚀 Starting training...")
    trainer.train(resume_from_checkpoint=True)

    print("💾 Saving model locally...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    print(f"✅ Local proof training complete! Model saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test 4-bit LLM loading in isolation"""
import torch
import time
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

print("=" * 60)
print("ISOLATED 4-BIT MODEL LOADING TEST")
print("=" * 60)

print(f"\n1. PyTorch version: {torch.__version__}")
print(f"2. CUDA available: {torch.cuda.is_available()}")
print(f"3. CUDA version: {torch.version.cuda}")
print(f"4. GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A'}")

model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

print(f"\n5. Loading tokenizer for {model_name}...")
t0 = time.time()
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
print(f"   ✓ Tokenizer loaded in {time.time()-t0:.2f}s")

print(f"\n6. Creating BitsAndBytesConfig...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)
print(f"   ✓ Config created")

print(f"\n7. Loading model with 4-bit quantization...")
print(f"   (This should take 30-60 seconds on first load)")
t1 = time.time()

try:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        low_cpu_mem_usage=True
    )
    elapsed = time.time() - t1
    print(f"   ✓ Model loaded successfully in {elapsed:.2f}s")
    
    print(f"\n8. Model info:")
    print(f"   - Device: {model.device}")
    print(f"   - Dtype: {model.dtype}")
    
    print(f"\n9. Quick inference test...")
    inputs = tokenizer("Hello, how are you?", return_tensors="pt").to(model.device)
    t2 = time.time()
    outputs = model.generate(**inputs, max_new_tokens=20)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f"   ✓ Generated in {time.time()-t2:.2f}s: {response}")
    
    print(f"\n{'=' * 60}")
    print("✅ ALL TESTS PASSED!")
    print(f"{'=' * 60}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

import torch
print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("CUDA version:", torch.version.cuda)

try:
    import bitsandbytes as bnb
    print("bitsandbytes imported successfully")
    
    # Check if we can import the 4-bit components
    from transformers import BitsAndBytesConfig
    print("BitsAndBytesConfig imported successfully")
    
    # Try to create a 4-bit config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16
    )
    print("BitsAndBytesConfig created successfully")
    print("✅ 4-bit quantization should work!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

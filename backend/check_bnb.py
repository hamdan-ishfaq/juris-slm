import bitsandbytes
import torch
print("bitsandbytes version:", bitsandbytes.__version__)
print("CUDA available:", torch.cuda.is_available())
print("PyTorch version:", torch.__version__)
print("CUDA version (torch):", torch.version.cuda)

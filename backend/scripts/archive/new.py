import torch
i = torch.cuda.current_device()
name = torch.cuda.get_device_name(i)
capability = torch.cuda.get_device_capability(i)
print(name, capability)  # TF32 is supported if capability major >= 8 (Ampere+)
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_path = "./cache/models/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"  # 你 snapshot_download 打印出来的目录

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    dtype=torch.float16,  # 替换过时参数 torch_dtype -> dtype
    device_map="auto",
    trust_remote_code=True
).eval()

# 确保 pad_token_id 已设置以避免 "Setting `pad_token_id` to `eos_token_id`" 的提示
if getattr(model.config, "pad_token_id", None) is None:
    model.config.pad_token_id = tokenizer.eos_token_id

prompt = "你好"
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    out = model.generate(
        **inputs,
        max_new_tokens=512,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        # 显式传入 pad_token_id
        pad_token_id=model.config.pad_token_id
    )

if __name__ == "__main__":
    print(tokenizer.decode(out[0], skip_special_tokens=True))

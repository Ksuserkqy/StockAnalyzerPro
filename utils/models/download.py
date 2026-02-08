from modelscope import snapshot_download

def modelscope(model_name, cache_dir):
    model_dir = snapshot_download(
        model_name,
        cache_dir=cache_dir
    )
    return model_dir

if __name__ == "__main__":
    model = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
    download = modelscope(model, "./cache/models")
    print(download)
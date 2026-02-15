from dotenv import load_dotenv
import os

load_dotenv()

def get_api_keys():
    return {
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
        "DOUBAO_API_KEY": os.getenv("DOUBAO_API_KEY"),
    }

if __name__ == "__main__":
    keys = get_api_keys()
    print(keys)
    for name, val in keys.items():
        print(f"{name}: {'SET' if val else 'NOT SET'}")

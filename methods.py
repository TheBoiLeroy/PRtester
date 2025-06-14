from llama_cloud_services import LlamaParse
import os
from dotenv import load_dotenv


load_dotenv()
# Initialize LlamaParse
api_key = os.getenv("LLAMA_CLOUD_API_KEY")

if not api_key:
    raise ValueError("Set LLAMA_CLOUD_API_KEY in environment")

parser = LlamaParse(api_key=api_key)
print([m for m in dir(parser) if not m.startswith("_")])
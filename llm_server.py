from transformers import AutoTokenizer, AutoModelForCausalLM
from fastapi import FastAPI
import uvicorn
import torch

#MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
#print("✅ Loading model...")
#tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
#model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32)

MODEL_ID = "google/gemma-2-2b-it"
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float32,
    device_map="cpu"
)

app = FastAPI()

@app.get("/chat")
def chat(q: str):
    inputs = tokenizer(q, return_tensors="pt")
    output = model.generate(**inputs, max_new_tokens=120)
    answer = tokenizer.decode(output[0], skip_special_tokens=True)
    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7000)

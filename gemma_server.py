from fastapi import FastAPI
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch, uvicorn

MODEL_ID = "google/gemma-2-2b-it"
print("Loading Gemma 2B...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float32,
    device_map="cpu"
)

app = FastAPI()

@app.get("/chat")
def chat(q: str):
    inputs = tokenizer(q, return_tensors="pt")
    output = model.generate(
        **inputs,
        max_new_tokens=200,
        temperature=0.7,
        top_p=0.95
    )
    answer = tokenizer.decode(output[0], skip_special_tokens=True)
    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7001)

from fastapi import FastAPI
import requests

app = FastAPI()

API_KEY = "YOUR_API_KEY"

@app.get("/generate-video")
def generate_video(prompt: str):

    payload = {
        "prompt": prompt
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    response = requests.post(
        "https://api.example.com/video/generate",
        json=payload,
        headers=headers
    )

    return response.json()
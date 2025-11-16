import asyncio
import json
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from googleapis import read_emails
from openai import OpenAI

load_dotenv()
openai_key = os.environ.get("OPENAI_KEY")
print(openai_key)
client = OpenAI(api_key=openai_key)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def ping():
    return {"message": "pong", "status": "ok"}


@app.post("/api/get_emails")
async def read_user_emails(request: Request):
    try:
        data = await request.json()
        access_token = data.get("access_token")
        days = data.get("days", 2)

        if not access_token:
            return {"error": "access_token is required"}

        # Use the access token to read emails
        emails = read_emails(days=days, access_token=access_token)
        print(json.dumps(emails[0], indent="4"))
        return {"emails": emails, "count": len(emails)}

    except Exception as e:
        print("Error:", str(e))
        return {"error": str(e)}


@app.post("/api/data")
async def chat(request: Request):
    try:
        data = await request.json()
        messages = data.get("messages", [])

        # Create the stream
        stream = client.chat.completions.create(
            model="gpt-4",  # Use actual OpenAI model
            messages=messages,
            stream=True,
        )

        def generate():
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    # Format for Vercel AI SDK
                    yield f"0:{json.dumps(content)}\n"

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    except Exception as e:
        print("error: " + str(e))
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=7878, reload=True)

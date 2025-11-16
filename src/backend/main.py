import asyncio
import json
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_chat(prompt, model="gpt-5-nano"):
    response = client.responses.create(model=model, input=prompt)
    return response.output_text


def get_top_n_emails_prompt(
    email_data,
    n,
    topics="personal relations, professors, peers, time-sensitive, applications",
):
    email_prompt_template = """
    You are an intelligent email assistant with the sole task of identifying important emails for undergraduate students and sorting them loosely.
    Given the following emails:

    {email_data}

    Identify the top {n} most important emails. Important emails involve but are not limited to: "{topics}".
    The following are not important: newsletters, verifications, mailing lists
    Return exactly as a JSON array with keys:
    - "subject"
    - "sender"
    - "summary"
    - "date"

    Do not include any text outside the JSON array.
    """
    return email_prompt_template.format(email_data=email_data, n=n, topics=topics)


@app.get("/ping")
async def ping():
    return {"message": "pong", "status": "ok"}


summaryPrompt = """You are an expert email summarizer. Create ultra-concise summaries for display in small card UI components.

RULES:
- Maximum 2-3 short sentences (or 1-2 if possible)
- Lead with the core action/decision/ask
- Include only: deadlines, key numbers, critical names, required actions
- Zero fluff: no greetings, pleasantries, or obvious context
- Use fragments and abbreviated style when clear
- Prioritize: urgency > action items > decisions > FYI info

FORMAT:
[Action/Decision]: [Key details]. [Deadline/Next step if applicable].

EXAMPLES:

Email: "Hi team, I hope you're doing well. I wanted to reach out regarding the Q4 budget meeting scheduled for next Thursday at 2pm. Please review the attached spreadsheet and come prepared with your department's projections. Let me know if you have any questions. Best regards, Sarah"

Summary: Q4 budget meeting Thu 2pm. Review attached spreadsheet, bring dept projections.

---

Email: "Following up on our conversation about the Johnson account. They've agreed to the revised terms and are ready to sign. Contract value is $2.3M over 3 years. Need your approval by EOD Friday to proceed."

Summary: Johnson account approved revised terms. $2.3M/3yr contract needs your sign-off by Fri EOD.

---

Email: "The server migration initially planned for this weekend has been postponed to November 23rd due to vendor delays. IT will send updated maintenance window details early next week. No action required from your end."

Summary: Server migration moved to Nov 23 (vendor delay). No action needed."""


@app.post("/api/summarize_email")
async def summarize_email(request: Request):
    try:
        data = await request.json()
        emailBody = data.get("emailBody")
        prompt = f"{summaryPrompt} ---. Summarize the following email: {emailBody}"
        cc = client.responses.create(
            input=prompt,
            model="gpt-5-nano",
        )
        # Return as PlainTextResponse instead of just the string
        return PlainTextResponse(cc.output_text)
    except Exception as e:
        print("Error in summarize_email:", str(e))
        return {"error": str(e)}


@app.post("/api/get_emails")
async def read_user_emails(request: Request):
    try:
        data = await request.json()
        access_token = data.get("access_token")
        days = data.get("days", 1)

        if not access_token:
            return {"error": "access_token is required"}

        # Use the access token to read emails
        emails = read_emails(days=days, access_token=access_token)
        print(json.dumps(emails[0], indent="4"))
        return emails

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

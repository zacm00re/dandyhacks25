import asyncio
import json
import os
import sys
import llm_api
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from googleapis import read_emails, read_events, read_tasks
from openai import OpenAI
from pathlib import Path
import logging

load_dotenv()
openai_key = os.environ.get("OPENAI_KEY")
print(openai_key)
client = OpenAI(api_key=openai_key)
app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # ← This creates the logger variable

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


@app.get("/ping")
async def ping():
    return {"message": "pong", "status": "ok"}


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


@app.post("/api/get_events")
async def read_user_events(request: Request):
    try:
        data = await request.json()
        access_token = data.get("access_token")
        time_min = data.get("time_min")  # Optional: ISO format datetime
        time_max = data.get("time_max")  # Optional: ISO format datetime
        calendar_id = data.get("calendar_id", "all")  # Optional: defaults to "all"

        if not access_token:
            return {"error": "access_token is required"}

        # Parse time_min and time_max if provided
        from datetime import datetime

        parsed_time_min = None
        parsed_time_max = None

        if time_min:
            try:
                parsed_time_min = datetime.fromisoformat(
                    time_min.replace("Z", "+00:00")
                )
            except ValueError:
                return {"error": "Invalid time_min format. Use ISO format."}

        if time_max:
            try:
                parsed_time_max = datetime.fromisoformat(
                    time_max.replace("Z", "+00:00")
                )
            except ValueError:
                return {"error": "Invalid time_max format. Use ISO format."}

        # Use the access token to read events
        events = read_events(
            time_min=parsed_time_min,
            time_max=parsed_time_max,
            calendar_id=calendar_id,
            access_token=access_token,
        )

        if events:
            print(json.dumps(events[0], indent=4))

        return events

    except Exception as e:
        print("Error:", str(e))
        return {"error": str(e)}


@app.post("/api/get_tasks")
async def read_user_tasks(request: Request):
    try:
        data = await request.json()
        access_token = data.get("access_token")
        look_ahead_days = data.get("look_ahead_days", 7)  # Optional: defaults to 7
        tasklist_id = data.get(
            "tasklist_id", "@default"
        )  # Optional: defaults to primary list

        if not access_token:
            return {"error": "access_token is required"}

        # Use the access token to read tasks
        tasks = read_tasks(
            lookAheadDays=look_ahead_days,
            tasklist_id=tasklist_id,
            access_token=access_token,
        )

        if tasks:
            print(json.dumps(tasks[0], indent=4))

        return tasks

    except Exception as e:
        print("Error:", str(e))
        return {"error": str(e)}

@app.post("/api/data")
async def chat(request: Request):
    """
    Main endpoint:
    - Structured data (calendar/tasks/email) → converts to prose and streams
    - Everything else (chitchat, unknown) → streams ChatGPT response
    """
    data = await request.json()  # Keep it async since you're using async def
    
    messages = data.get("messages", [])
    user = data.get("user", "default_user")
    file_paths = data.get("file_paths")
    file_names = data.get("file_names")
    
    user_input = messages[-1].get("content", "") if messages else ""
    
    if not user_input:
        return {"error": "Empty message"}
    
    def generate():
        """Stream prose from agents or ChatGPT."""
        try:
            should_fallback = False
            had_agent_output = False
            
            # Try specialized agents
            for chunk in llm_api.process_user_input_stream(user_input, "jkdev" , file_paths, file_names):
                
                if chunk.get("fallback"):
                    should_fallback = True
                    logger.info("Agent failed or unknown, using ChatGPT")
                    break
                
                if "output" in chunk:
                    had_agent_output = True
                    agent = chunk.get("agent", "unknown")
                    output = chunk["output"]
                    
                    # Convert structured data to prose
                    prose = llm_api.format_structured_data_as_prose(agent, output)
                    
                    # Stream word by word (like ChatGPT does)
                    words = prose.split()
                    for i, word in enumerate(words):
                        text = word + (" " if i < len(words) - 1 else "")
                        yield f"0:{json.dumps(text)}\n"
            
            # Use ChatGPT if agent failed or couldn't classify
            if should_fallback or not had_agent_output:
                logger.info("Streaming ChatGPT response")
                for text_chunk in llm_api.chatgpt_stream(user_input, messages):
                    yield f"0:{json.dumps(text_chunk)}\n"
                    
        except Exception as e:
            logger.exception(f"Stream error: {e}")
            # Always fallback to ChatGPT on error
            for text_chunk in llm_api.chatgpt_stream(user_input, messages):
                yield f"0:{json.dumps(text_chunk)}\n"
    
    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=7878, reload=True)

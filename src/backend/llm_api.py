from openai import OpenAI
import generate_prompts
import json
import snowflake_setup
import data_preparation
from snowflake.snowpark import types as T
from snowflake.snowpark import Row
from snowflake.snowpark.functions import lit, col, array_construct, vector_cosine_distance, parse_json
import requests
import numpy as np
from dotenv import load_dotenv
import os
import googleapis
import re
import logging
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse


# Load the environment variables from your file
load_dotenv("api.env")  # or just load_dotenv() if the file is named .env

embedding_key = os.environ.get("EMBEDDER_API_KEY")
agent_key = os.environ.get("AGENT_API_KEY")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

embedding_client = OpenAI(api_key = embedding_key)
agent_client = OpenAI(api_key = agent_key)
def run_chat(prompt: str) -> str:
    """
    Send a prompt to GPT-5 Mini via OpenRouter and return the text output.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {agent_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-5-nano",
        "messages": [{"role": "user", "content": prompt}],
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()  # raise an exception for HTTP errors

    result = response.json()
    # OpenRouter GPT response text is usually in result['choices'][0]['message']['content']
    output_text = result['choices'][0]['message']['content']
    return output_text

def get_embedding(text):
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
     "Authorization": f"Bearer {embedding_key}",  # Your OpenRouter key
        "Content-Type": "application/json"
    }
    data = {
        "model": "text-embedding-3-small",
        "input": [text]
    }
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    embedding = result['data'][0]['embedding']
    return embedding
def extract_texts_from_df(df):
    rows = df.select("CONTENT").collect()
    return [r["CONTENT"] for r in rows]
def parse_json_objects_from_string(text: str):
    """
    Extracts ALL JSON objects from ANY messy string and returns them as a list of dicts.
    Works even if braces are doubled ({{ }}), list syntax is invalid, or there is extra text.
    """

    # Normalize double braces: {{ -> { , }} -> }
    normalized = text.replace("{{", "{").replace("}}", "}")

    # Extract ALL JSON objects, including multi-line ones
    # This regex matches nested braces properly, not just shallow ones.
    objects = []
    brace_stack = []
    start = None

    for i, ch in enumerate(normalized):
        if ch == '{':
            if not brace_stack:
                start = i
            brace_stack.append('{')
        elif ch == '}':
            if brace_stack:
                brace_stack.pop()
                if not brace_stack and start is not None:
                    objects.append(normalized[start:i+1])
                    start = None

    # Parse every object individually
    parsed = []
    for obj in objects:
        try:
            parsed.append(json.loads(obj))
        except json.JSONDecodeError:
            # Try fixing common issues automatically
            fixed = obj.replace("\n", " ").strip().rstrip(",")
            try:
                parsed.append(json.loads(fixed))
            except:
                raise ValueError(f"Could not parse object:\n{obj}")

    return parsed


def process_user_input(user_input, user, file_paths: list[str] | None, file_names : list[str] | None):
    orchestrator_prompt_string = generate_prompts.get_orchestrator_prompt(user_input)
    orch_response = run_chat(orchestrator_prompt_string)  # LLM call
    classification = json.loads(orch_response)
    agent_name = classification["agent"]
    raw_input = classification["raw_input"]
    if agent_name == "calendar":
        file_data = ""
        if file_paths is not None and file_names is not None:
            for i in range(len(file_paths)):
                process_uploaded_file(file_paths[i], file_names[i], user, chunk_size = 150)
                if file_paths[i]:
                    file_data = file_data + data_preparation.read(file_paths[i])
            raw_input = raw_input
            vector_input = file_data
        else:
            query_embedding = get_embedding(raw_input)
            vector_input = retrieve_top_chunks(user, query_embedding, file_filter = 'syllabus')
        calendar_prompt = generate_prompts.get_calendar_data_prompt(calendar_input=raw_input, vector_input = vector_input)
        agent_response = run_chat(calendar_prompt)  # LLM call
        events = json.loads(agent_response)
        return {"agent": "calendar", "output": events}
    elif agent_name == "email":
        query_embedding = get_embedding(raw_input)
        df = retrieve_email_chunks(user, query_embedding, top_k=2)
        content = extract_texts_from_df(df)
        email_prompt = generate_prompts.get_email_manager_prompt(email_input = raw_input, rag_email_context = content)
        agent_response = run_chat(email_prompt)
        emails = json.loads(agent_response)
        return {"agent": "email", "output": emails}
    elif agent_name == "tasks":
        file_data = ""
        if file_paths is not None and file_names is not None:
            for i in range(len(file_paths)):
                process_uploaded_file(file_paths[i], file_names[i], user, chunk_size = 150)
                if file_paths[i]:
                    file_data = file_data + data_preparation.read(file_paths[i])
            raw_input = raw_input
            vector_input = file_data
        else:
            query_embedding = get_embedding(raw_input)
            vector_input = retrieve_top_chunks(user, query_embedding, file_filter = 'syllabus')
        task_prompt = generate_prompts.get_task_prompt(user_input = raw_input, vector_input = vector_input)
        agent_response = run_chat(task_prompt)  # LLM call
        tasks = json.loads(agent_response)
        return {"agent": "tasks", "output": tasks}
    elif agent_name == "course_content":
        file_data = ""
        if file_paths is not None and file_names is not None:
            for i in range(len(file_paths)):
                process_uploaded_file(file_paths[i], file_names[i], user, chunk_size = 500)
            raw_input = raw_input
        query_embedding = get_embedding(raw_input)
        vector_input = retrieve_top_chunks(user, query_embedding)
        course_prompt = generate_prompts.get_course_prompt(user_input = raw_input, vector_input = vector_input)
        agent_response = run_chat(course_prompt)
        course_content = json.loads(agent_response)
        return {"agent": "course_content", "output": course_content}
    else:
        return {"agent": "unknown", "output": "Could not classify input"}

def process_user_input_stream(user_input, user, file_paths: list[str] | None, file_names: list[str] | None):
    """Stream agent responses with error handling."""
    try:
        orchestrator_prompt_string = generate_prompts.get_orchestrator_prompt(user_input)
        orch_response = run_chat(orchestrator_prompt_string)
        classification = json.loads(orch_response)
        agent_name = classification["agent"]
        raw_input = classification["raw_input"]
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        yield {"agent": "error", "fallback": True}
        return
    def json_stream(json_str):
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                for item in parsed:
                    yield item
            elif isinstance(parsed, dict):
                yield parsed
            else:
                yield {"output": parsed}
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            yield {"error": "Invalid JSON", "fallback": True}
    
    try:
        if agent_name in ["calendar", "tasks", "course_content"]:
            try:
                if file_paths and file_names:
                    file_data = ""
                    for i in range(len(file_paths)):
                        try:
                            chunk_size = 500 if agent_name == "course_content" else 150
                            process_uploaded_file(file_paths[i], file_names[i], user, chunk_size=chunk_size)
                            if file_paths[i]:
                                file_data += data_preparation.read(file_paths[i])
                        except Exception as e:
                            logger.error(f"File error: {e}")
                    vector_input = file_data
                else:
                    query_embedding = get_embedding(raw_input)
                    vector_input = retrieve_top_chunks(user, query_embedding, file_filter='syllabus')
            except Exception as e:
                logger.error(f"Vector retrieval error: {e}")
                yield {"agent": agent_name, "fallback": True}
                return
            
            try:
                if agent_name == "calendar":
                    prompt = generate_prompts.get_calendar_data_prompt(calendar_input=raw_input, vector_input=vector_input)
                    agent_response = run_chat(prompt)
                    events = parse_json_objects_from_string(agent_response)
                    for i in events:
                        googleapis.build_event_from_data(i)
                elif agent_name == "tasks":
                    prompt = generate_prompts.get_task_prompt(user_input=raw_input, vector_input=vector_input)
                    task_response = run_chat(prompt)
                    tasks = parse_json_objects_from_string(task_response)
                    for i in tasks:
                        googleapis.build_task_from_data(i)
                else:
                    prompt = generate_prompts.get_course_prompt(user_input=raw_input, vector_input=vector_input)
                agent_response = run_chat(prompt)
                
                for item in json_stream(agent_response):
                    if "error" in item:
                        yield {"agent": agent_name, "fallback": True}
                    else:
                        yield {"agent": agent_name, "output": item}
            except Exception as e:
                logger.error(f"Agent error: {e}")
                yield {"agent": agent_name, "fallback": True}
                return
        
        elif agent_name == "email":
            try:
                query_embedding = get_embedding(raw_input)
                df = retrieve_email_chunks(user, query_embedding, top_k=2)
                content = extract_texts_from_df(df)
                prompt = generate_prompts.get_email_manager_prompt(email_input=raw_input, rag_email_context=content)
                agent_response = run_chat(prompt)
                
                for item in json_stream(agent_response):
                    if "error" in item:
                        yield {"agent": "email", "fallback": True}
                    else:
                        yield {"agent": "email", "output": item}
            except Exception as e:
                logger.error(f"Email agent error: {e}")
                yield {"agent": "email", "fallback": True}
                return
        
        else:
            yield {"agent": "unknown", "fallback": True}
            
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        yield {"agent": "error", "fallback": True}

def format_structured_data_as_prose(agent_name: str, data) -> str:
    """Convert structured JSON data to natural language prose."""
    
    if agent_name == "calendar":
        if isinstance(data, list):
            if not data:
                return "I couldn't find any calendar events."
            
            text = f"I found {len(data)} calendar event{'s' if len(data) > 1 else ''}:\n\n"
            
            for i, event in enumerate(data, 1):
                title = event.get("title", "Untitled event")
                date = event.get("date", "No date")
                time = event.get("time", "")
                location = event.get("location", "")
                description = event.get("description", "")
                
                text += f"{i}. {title}\n"
                text += f"   When: {date}"
                if time:
                    text += f" at {time}"
                text += "\n"
                if location:
                    text += f"   Where: {location}\n"
                if description:
                    text += f"   {description}\n"
                    text += "\n"
            return text
        
        elif isinstance(data, dict):
            title = data.get("title", "Event")
            date = data.get("date", "")
            return f"Event: {title} on {date}"
    
    elif agent_name == "tasks":
        if isinstance(data, list):
            if not data:
                return "I couldn't find any tasks."
            
            text = f"Here are {len(data)} task{'s' if len(data) > 1 else ''}:\n\n"
            
            for i, task in enumerate(data, 1):
                title = task.get("title", "Untitled task")
                due = task.get("due_date", "")
                priority = task.get("priority", "")
                status = task.get("status", "")
                
                text += f"{i}. {title}"
                if priority:
                    text += f" [{priority.upper()}]"
                text += "\n"
                
                if due:
                    text += f"   Due: {due}\n"
                if status:
                    text += f"   Status: {status}\n"
                text += "\n"
            
            return text
        
        elif isinstance(data, dict):
            return f"Task: {data.get('title', 'Untitled')}"
    
    elif agent_name == "email":
        if isinstance(data, list):
            if not data:
                return "I couldn't find any relevant emails."
            
            text = f"I found {len(data)} relevant email{'s' if len(data) > 1 else ''}:\n\n"
            
            for i, email in enumerate(data, 1):
                subject = email.get("subject", "No subject")
                sender = email.get("from", "Unknown sender")
                date = email.get("date", "")
                summary = email.get("summary", "")
                
                text += f"{i}. {subject}\n"
                text += f"   From: {sender}"
                if date:
                    text += f" ({date})"
                text += "\n"
                if summary:
                    text += f"   {summary}\n"
                text += "\n"
            
            return text
        
        elif isinstance(data, dict):
            subject = data.get("subject", "No subject")
            sender = data.get("from", "Unknown")
            return f"Email from {sender}: {subject}"
    
    elif agent_name == "course_content":
        if isinstance(data, dict):
            text = "Here's the course information:\n\n"
            for key, value in data.items():
                formatted_key = key.replace('_', ' ').title()
                text += f"{formatted_key}:\n{value}\n\n"
            return text
        else:
            return str(data)
    
    # Fallback: just return JSON as string
    return json.dumps(data, indent=2)


def chatgpt_stream(user_input: str, messages: list):
    """Fallback to ChatGPT for chitchat and unknown queries."""
    try:
        chat_messages = messages.copy()
        system_msg = {
            "role": "system",
            "content": "You are a helpful assistant."
        }
        chat_messages.insert(0, system_msg)
        
        stream = agent_client.chat.completions.create(
            model="gpt-4",
            messages=chat_messages,
            stream=True,
        ) 
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        logger.error(f"ChatGPT error: {e}")
        yield f"Error: {str(e)}"

@app.post("/api/data")
def chat(request: Request):
    """
    Main endpoint:
    - Structured data (calendar/tasks/email) → converts to prose and streams
    - Everything else (chitchat, unknown) → streams ChatGPT response
    """
    import asyncio
    body = asyncio.run(request.json())
    
    messages = body.get("messages", [])
    user = body.get("user", "default_user")
    file_paths = body.get("file_paths")
    file_names = body.get("file_names")
    
    user_input = messages[-1].get("content", "") if messages else ""
    
    if not user_input:
        return {"error": "Empty message"}
    
    def generate():
        """Stream prose from agents or ChatGPT."""
        try:
            should_fallback = False
            had_agent_output = False
            
            # Try specialized agents
            for chunk in process_user_input_stream(user_input, user, file_paths, file_names):
                
                if chunk.get("fallback"):
                    should_fallback = True
                    logger.info("Agent failed or unknown, using ChatGPT")
                    break
                
                if "output" in chunk:
                    had_agent_output = True
                    agent = chunk.get("agent", "unknown")
                    output = chunk["output"]
                    
                    # Convert structured data to prose
                    prose = format_structured_data_as_prose(agent, output)
                    
                    # Stream word by word (like ChatGPT does)
                    words = prose.split()
                    for i, word in enumerate(words):
                        text = word + (" " if i < len(words) - 1 else "")
                        yield f"0:{json.dumps(text)}\n"
            
            # Use ChatGPT if agent failed or couldn't classify
            if should_fallback or not had_agent_output:
                logger.info("Streaming ChatGPT response")
                for text_chunk in chatgpt_stream(user_input, messages):
                    yield f"0:{json.dumps(text_chunk)}\n"
                    
        except Exception as e:
            logger.exception(f"Stream error: {e}")
            # Always fallback to ChatGPT on error
            for text_chunk in chatgpt_stream(user_input, messages):
                yield f"0:{json.dumps(text_chunk)}\n"
    
    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")







def process_uploaded_file(file_path, file_name, user, chunk_size=500):
    session = snowflake_setup.create_snowpark_session({
        "user": user,
        "password": "B2BSaaS",
        "account": "DYLPKSL-VW53358",
        "role": f"USER_{user}_ROLE",
        "database": "DANDY_2025",
        "schema": f"USER_{user}",
        "warehouse": "MY_WH"
    })
    session.sql("USE ROLE USER_JKDEV_ROLE").collect()
    table_name = f"DANDY_2025.USER_{user.upper()}.study_chunks"

    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            chunk_id INT AUTOINCREMENT PRIMARY KEY,
            file_name STRING,
            "user" STRING,
            content STRING,
            embedding VARIANT
        )
    """).collect()

    data = data_preparation.read_and_chunk(file_path, chunk_size=chunk_size)
    rows = []

    for chunk in data:
        text = chunk.get("text", "")
        embedding_vec = get_embedding(text)
        row = Row(
            content=text,
            file_name=file_name,
            user=user,
            embedding=json.dumps(embedding_vec)  # JSON string
        )
        rows.append(row)

    df = session.create_dataframe(rows)
    # Correct parse_json usage
    df = df.with_column("embedding", parse_json(col("embedding")))
    df.write.save_as_table(table_name, mode="append")


def process_email_json(file_path, file_name, user):
    session = snowflake_setup.create_snowpark_session({
        "user": f"{user}",
        "password": "B2BSaaS",
        "account": "DYLPKSL-VW53358",
        "role": f"USER_{user}_ROLE",
        "database": "DANDY_2025",
        "schema": f"USER_{user}",
        "warehouse": "MY_WH"
    })
    session.sql("USE ROLE USER_JKDEV_ROLE").collect()
    session.sql("USE DATABASE DANDY_2025").collect()
    session.sql(f"CREATE SCHEMA IF NOT EXISTS USER_{user.upper()}").collect()
    table_name = f"DANDY_2025.USER_{user.upper()}.study_chunks"
    session.sql(f"USE SCHEMA USER_{user.upper()}").collect()
    session.sql(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            chunk_id INT AUTOINCREMENT PRIMARY KEY,
            file_name STRING,
            "user" STRING,
            content STRING,
            embedding ARRAY
        )
    """).collect()
    with open(file_path, "r") as f:
        emails = json.load(f)
    rows = []
    for email in emails:
        text = email.get("body", "")  # Use 'body' as content
        embedding_vec = get_embedding(text)  # Your embedding function
        row = Row(
            content=text,
            file_name=file_name,
            user=user,
            embedding=embedding_vec
        )
        rows.append(row)
    df = session.create_dataframe(rows)
    df.write.save_as_table(table_name, mode="append")

def get_top_n_emails_prompt(email_data, topics, n):
    email_prompt_template = """
    You are an intelligent email assistant. Given the following emails:

    {email_data}

    Identify the top {n} most important emails based in order for undergraduate students on relevance to the topics: "{topics}".
    Return exactly as a JSON array with keys:
    - "subject"
    - "sender"
    - "summary"

    Do not include any text outside the JSON array.
    """
    return email_prompt_template.format(email_data = email_data, topics = topics, n = n)

def retrieve_email_chunks(user, query_embedding, top_k=5):
    session = snowflake_setup.create_snowpark_session({
        "user": user,
        "password": "B2BSaaS",
        "account": "DYLPKSL-VW53358",
        "role": f"USER_{user}_ROLE",
        "database": "DANDY_2025",
        "schema": f"USER_{user}",
        "warehouse": "MY_WH"
    })
    session.sql("USE ROLE USER_JKDEV_ROLE").collect()
    table_name = f"DANDY_2025.USER_{user.upper()}.study_chunks"
    query_vec_json = json.dumps(query_embedding)

    df = session.sql(f"""
        SELECT chunk_id, file_name, content,
               1 - (embedding <=> PARSE_JSON('{query_vec_json}')) AS similarity
        FROM {table_name}
        WHERE file_name ILIKE '%email%'
        ORDER BY similarity DESC
        LIMIT {top_k}
    """)

    return df.collect()

def retrieve_top_chunks(user, query_embedding, top_k=5, file_filter: str | None = None):
    session = snowflake_setup.create_snowpark_session({
        "user": user,
        "password": "B2BSaaS",
        "account": "DYLPKSL-VW53358",
        "role": f"USER_{user}_ROLE",
        "database": "DANDY_2025",
        "schema": f"USER_{user}",
        "warehouse": "MY_WH"
    })
    rows = session.table("STUDY_CHUNKS").select("chunk_id", "file_name", "content", "embedding").collect()

    def cosine_similarity(a, b):
        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    similarities = []
    for row in rows:
        # Apply file filter
        if file_filter and file_filter.lower() not in row["FILE_NAME"].lower():
            continue

        emb = row["EMBEDDING"]
        if isinstance(emb, str):
            emb = json.loads(emb)
        elif isinstance(emb, dict) or isinstance(emb, list):
            emb = list(emb)

        sim = cosine_similarity(query_embedding, emb)
        similarities.append({
            "chunk_id": row["CHUNK_ID"],
            "file_name": row["FILE_NAME"],
            "content": row["CONTENT"],
            "embedding": emb,
            "similarity": sim
        })

    top_chunks = sorted(similarities, key=lambda x: x["similarity"], reverse=True)[:top_k]
    return top_chunks


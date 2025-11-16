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



# Load the environment variables from your file
load_dotenv("api.env")  # or just load_dotenv() if the file is named .env

embedding_key = os.environ.get("EMBEDDER_API_KEY")
agent_key = os.environ.get("AGENT_API_KEY")


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


def process_user_input_stream(user_input, user, file_paths: list[str] | None, file_names: list[str] | None):
    orchestrator_prompt_string = generate_prompts.get_orchestrator_prompt(user_input)
    orch_response = run_chat(orchestrator_prompt_string)
    classification = json.loads(orch_response)
    agent_name = classification["agent"]
    raw_input = classification["raw_input"]

    def json_stream(json_str):
        """Yield each item in a JSON array or dict as a separate dict."""
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                for item in parsed:
                    yield item
            elif isinstance(parsed, dict):
                yield parsed
            else:
                yield {"output": parsed}
        except json.JSONDecodeError:
            yield {"error": "Invalid JSON from LLM"}

    if agent_name in ["calendar", "tasks", "course_content"]:
        if file_paths and file_names:
            file_data = ""
            for i in range(len(file_paths)):
                process_uploaded_file(file_paths[i], file_names[i], user, chunk_size=150 if agent_name != "course_content" else 500)
                if file_paths[i]:
                    file_data += data_preparation.read(file_paths[i])
            vector_input = file_data
        else:
            query_embedding = get_embedding(raw_input)
            vector_input = retrieve_top_chunks(user, query_embedding, file_filter='syllabus')

        if agent_name == "calendar":
            prompt = generate_prompts.get_calendar_data_prompt(calendar_input=raw_input, vector_input=vector_input)
        elif agent_name == "tasks":
            prompt = generate_prompts.get_task_prompt(user_input=raw_input, vector_input=vector_input)
        else:  # course_content
            prompt = generate_prompts.get_course_prompt(user_input=raw_input, vector_input=vector_input)

        agent_response = run_chat(prompt)
        for item in json_stream(agent_response):
            yield {"agent": agent_name, "output": item}

    elif agent_name == "email":
        query_embedding = get_embedding(raw_input)
        df = retrieve_email_chunks(user, query_embedding, top_k=2)
        content = extract_texts_from_df(df)
        prompt = generate_prompts.get_email_manager_prompt(email_input=raw_input, rag_email_context=content)
        agent_response = run_chat(prompt)
        for item in json_stream(agent_response):
            yield {"agent": "email", "output": item}
    else:
        yield {"agent": "unknown", "output": "Could not classify input"}






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

for chunk in process_user_input_stream("Make flashcards about RNA", "jkdev", None, None):
    print(chunk)
   

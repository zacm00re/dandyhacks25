
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

def get_calendar_data_prompt(calendar_input, vector_input):
    calendar_agent_prompt = """
You are a calendar assistant AI.
Your job is to read the user input and:
1. Determine whether the user wants to add or remove events.
2. Extract each event's:
   - title
   - start_time
   - end_time
   - any additional notes
   - date (if the user specifies a relative date like 'today', 'tomorrow', or 'next Monday', convert it to ISO format YYYY-MM-DD)
   - repeat (if no custom repeat sequence is mentioned, default to 'weekly')
3. If the user input references a syllabus, use relevant content from the {vector_input} to inform your response. Otherwise, proceed without any external context.
4. Note: Focus **only on events, classes, and meetings**. Ignore assignments, tasks, or other non-calendar items.
5. Return a JSON array where each element contains:
{{
  "action": "add" or "remove",
  "title": "...",
  "start_time": "...",
  "end_time": "...",
  "location": "...",
  "notes": "...",
  "date": "YYYY-MM-DD or null",
  "repeat": "daily/weekly/monthly/etc."
}}
Example:
User input: "Schedule lab today from 3 PM to 4 PM."
Assume current date is 2025-11-14.
Output:
[
  {{"action": "add", "title": "Lab", "start_time": "15:00", "end_time": "16:00", "location" : "Hutchinson 432", "notes": "", "date": "2025-11-14", "repeat": null}}
]

Now parse the following user input and return the structured JSON:
"{calendar_input}"
"""
    return calendar_agent_prompt.format(calendar_input = calendar_input, vector_input = vector_input)

def get_email_manager_prompt(email_input, rag_email_context):
    email_manager_prompt = """
You are an intelligent email assistant orchestrator. Your job is to read the user input and:

1. Decide what the user wants to do:
   - "reply" → draft a reply email.
   - "new" → draft a new email.

2. If the task is "reply" and relevant email context is available (provided via RAG), use that content to inform your reply. Otherwise, follow user instructions directly.

3. Return a JSON object with these fields:

{
  "task": "reply" | "new",
  "emails_used": [list of email IDs or titles used for context, empty if none],
  "response": "The text of the drafted email, concise and professional."
}

User input: "{user_input}"
Relevant emails (from retrieval, if any):
\"\"\"{rag_email_context}\"\"\"

Instructions / special requirements: "{instruction}"

Return only valid JSON, no extra text.
"""
    return email_manager_prompt.format(user_input = email_input, rag_email_context = rag_email_context)

def get_orchestrator_prompt(user_input):
    orchestrator_prompt = """
You are an AI orchestrator for a student productivity assistant.
Your job is to read the user's input and classify it into one of the following categories (agents):
- calendar
- email
- tasks
- course_content

Instructions:
1. Only classify the input; do not attempt to perform the action.
2. Respond with a JSON object containing:
   {{
     "agent": <one of the five categories>,
     "raw_input": "<the original user input>"
   }}
Example:
User input: "Schedule lab from 6 PM to 7 PM and class from 8 PM to 9 PM."
Output:
{{
  "agent": "calendar",
  "raw_input": "Schedule lab from 6 PM to 7 PM and class from 8 PM to 9 PM."
}}

User input: "{user_input}"
"""
    return orchestrator_prompt.format(user_input = user_input)


def get_task_prompt(user_input, vector_input):
    tasks_prompt_template = """
You are a tasks/assignments assistant AI.
Your job is to read the user input and:
1. Determine whether the user wants to add, complete, or remove tasks.
2. Extract each task's:
   - title
   - notes
   - date (if the user specifies a relative date like 'today', 'tomorrow', or 'next Monday', convert it to ISO format YYYY-MM-DD)
   - repeat (if no custom repeat sequence is mentioned, default to null)
Note: Focus **only on tasks or assignments**. Ignore events, classes, or meetings.
3. If the user input references a syllabus, use relevant content from the {vector_input} to inform your response. Otherwise, proceed without any external context.
4. Return a JSON array where each element contains:
{{
  "action": "add" | "complete" | "remove",
  "title": "...",
  "notes": "...",
  "date": "YYYY-MM-DD or null",
  "repeat": null
}}
Example:
User input: "Finish lab report by tomorrow and mark reading assignment as done."
Assume today is 2025-11-14.
Output:
[
  {{"action": "add", "title": "Finish lab report", "notes": "", "date": "2025-11-15", "repeat": null}},
  {{"action": "complete", "title": "Reading assignment", "notes": "", "date": null, "repeat": null}}
]

Now parse the following user input and return the structured JSON:
"{user_input}"
"""
    return tasks_prompt_template.format(user_input = user_input, vector_input = vector_input)

def get_course_prompt(user_input, vector_input):
    course_prompt_template = """You are an intelligent course content assistant AI.
Your job is to read the student input and:

1. Determine the type of request:
   - "flashcards" → generate study flashcards from the content.
   - "problem_solution" → provide step-by-step solutions to a problem.
   - "explanation" → explain a concept or topic in simple, clear terms.
   - "summary" → summarize a section of the course material.

2. Use the provided course content context (from syllabus, lecture notes, or textbook excerpts) to generate the response.

3. Return a JSON object with the following fields:
{{
  "task_type": "flashcards" | "problem_solution" | "explanation" | "summary",
  "response": "The generated flashcards, solution, explanation, or summary, concise and clear."
}}

Example:
Student input: "Can you make flashcards for the key concepts in Lecture 2 on genetics?"
Course content:
Chapter 2: Genetics
- DNA structure
- Mendelian inheritance
- Gene expression

Output:
{{
  "task_type": "flashcards",
  "response": [
    {{"question": "What is the structure of DNA?", "answer": "Double helix with complementary base pairs"}},
    {{"question": "What is Mendelian inheritance?", "answer": "Patterns of inheritance described by Gregor Mendel"}},
    {{"question": "What is gene expression?", "answer": "Process by which information from a gene is used to synthesize functional products"}}
  ]
}}

Now parse the following student input using the course content and return the structured JSON:
Student input: "{student_input}"
Course content context:
{course_content_context} """

    return course_prompt_template.format(student_input = user_input, course_content_context = vector_input)

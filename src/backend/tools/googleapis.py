import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load variables from .env if present
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
]


def _get_credentials():
    creds = None
    token_path = "token.json"
    # crede?ntials_path = "credentials.json"
    credentials = json.dumps(os.getenv("GOOGLE_CREDS"))

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not (credentials):
                raise FileNotFoundError(
                    "credentials not found. Create OAuth credentials for the Google Calendar API and place the file next to this script."
                )
            flow = InstalledAppFlow.from_client_config(credentials, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return creds


def get_events_service():
    creds = _get_credentials()
    return build("calendar", "v3", credentials=creds)


def get_tasks_service():
    creds = _get_credentials()
    return build("tasks", "v1", credentials=creds)


def get_gmail_service():
    creds = _get_credentials()
    return build("gmail", "v1", credentials=creds)


def build_event_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    title = data.get("title") or "Untitled"
    notes = data.get("notes") or ""
    date_str = data["date"]
    start_str = data["start_time"]
    end_str = data["end_time"]

    event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_time = datetime.strptime(start_str, "%H:%M").time()
    end_time = datetime.strptime(end_str, "%H:%M").time()

    local_tz = datetime.now().astimezone().tzinfo
    start_dt = datetime.combine(event_date, start_time).replace(tzinfo=local_tz)
    end_dt = datetime.combine(event_date, end_time).replace(tzinfo=local_tz)

    # Convert to UTC and include explicit timeZone to satisfy Calendar API
    start_utc = start_dt.astimezone(timezone.utc)
    end_utc = end_dt.astimezone(timezone.utc)

    event: Dict[str, Any] = {
        "summary": title,
        "description": notes,
        "start": {
            "dateTime": start_utc.isoformat().replace("+00:00", "Z"),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_utc.isoformat().replace("+00:00", "Z"),
            "timeZone": "UTC",
        },
    }

    repeat = data.get("repeat")
    if isinstance(repeat, str) and repeat.strip():
        event["recurrence"] = [f"RRULE:FREQ={repeat.strip().upper()}"]

    return event


def add_event(
    data: Dict[str, Any], calendar_id: str = "primary", service=None
) -> Dict[str, Any]:
    event_body = build_event_from_data(data)
    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        print("[DRY_RUN] Would create event:")
        print(json.dumps(event_body, indent=2))
        return {"dryRun": True, "event": event_body}

    if service is None:
        service = get_events_service()

    created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    print("Event created:", created.get("htmlLink"))
    return created


def read_emails(days: int = 2, service=None) -> list:
    """
    Read all emails from the last X days.

    Args:
        days: Number of days to look back (default: 7)
        service: Gmail service instance (optional)

    Returns:
        List of email data dictionaries with id, subject, from, date, and snippet
    """

    from datetime import timedelta

    if service is None:
        service = get_gmail_service()

    # Calculate the date X days ago
    cutoff_date = datetime.now() - timedelta(days=days)
    query = f"after:{cutoff_date.strftime('%Y/%m/%d')} category:primary"

    # dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    # if dry_run:
    #     print(f"[DRY_RUN] Would fetch emails from last {days} days with query: {query}")
    #     return {"dryRun": True, "query": query}

    emails = []

    try:
        # List messages matching the query
        results = service.users().messages().list(userId="me", q=query).execute()
        messages = results.get("messages", [])

        print(f"Found {len(messages)} emails from the last {days} days")

        # Fetch details for each message
        for msg in messages:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )

            # headers = msg_data['payload']['headers']
            # subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            # from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
            # date = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown')

            # email_info = {
            #     'id': msg['id'],
            #     'subject': subject,
            #     'from': from_email,
            #     'date': date,
            #     'snippet': msg_data.get('snippet', '')
            # }

            emails.append(msg_data)

        return emails

    except Exception as e:
        print(f"Error reading emails: {e}")
        return []


def write_email(data: Dict[str, Any], service=None) -> Dict[str, Any]:
    """
    Send an email using the Gmail API.
    Expects data dict with keys: to, cc, bcc, subject, body
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    if service is None:
        service = get_gmail_service()

    to = data.get("to", "").strip()
    cc = data.get("cc", "").strip()
    bcc = data.get("bcc", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()

    if not to or not subject or not body:
        raise ValueError(
            "'to', 'subject', and 'body' are required fields for sending email."
        )

    # Build MIME message
    message = MIMEMultipart()
    message["to"] = to
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    message["subject"] = subject
    message.attach(MIMEText(body, "plain"))

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    msg_body = {"raw": raw_message}

    if dry_run:
        print("[DRY_RUN] Would send email:")
        print(
            json.dumps(
                {"to": to, "cc": cc, "bcc": bcc, "subject": subject, "body": body},
                indent=2,
            )
        )
        return {"dryRun": True, "email": msg_body}

    sent = service.users().messages().send(userId="me", body=msg_body).execute()
    print("Email sent! Message ID:", sent.get("id"))
    return sent


def build_task_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a Google Tasks task resource from input data.
    Expected keys:
    - title (str): required
    - notes (str): optional
    - due_date (YYYY-MM-DD) or date (YYYY-MM-DD): optional (no time expected)
    """
    title = (data.get("title") or "Untitled").strip()
    notes = data.get("notes") or ""

    # Determine due date (no time expected)
    due_date_str = data.get("due_date") or data.get("date")

    task: Dict[str, Any] = {
        "title": title,
    }
    if notes:
        task["notes"] = notes

    if due_date_str:
        try:
            date_obj = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            # Treat tasks as date-only: set to start of day in local timezone
            time_obj = datetime.strptime("00:00", "%H:%M").time()
            local_tz = datetime.now().astimezone().tzinfo
            due_local = datetime.combine(date_obj, time_obj).replace(tzinfo=local_tz)
            # Keep local offset to preserve the calendar day in clients
            task["due"] = due_local.isoformat()
        except ValueError:
            # Ignore invalid due date silently; task will be created without due
            pass

    return task


def add_task(
    data: Dict[str, Any], tasklist_id: str = "@default", service=None
) -> Dict[str, Any]:
    """
    Create a Google Task in the specified task list (default: primary "@default").
    Respects DRY_RUN env var.
    """
    task_body = build_task_from_data(data)
    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        print("[DRY_RUN] Would create task:")
        print(json.dumps(task_body, indent=2))
        return {"dryRun": True, "task": task_body}

    if service is None:
        service = get_tasks_service()

    created = service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()
    print("Task created:", created.get("id"))
    return created


if __name__ == "__main__":
    # with open("input.json", "r") as file:
    #     data = json.load(file)

    emails = read_emails(days=2)
    print(json.dumps(emails[0], indent=4))
    # for key, value in emails[0].items():
    #     print(f"{key}: {value}")
    # for email in emails:
    #     print(email)

    # write_email(data)

    # if data.get("action") == "add":
    #     add_task(data)
    # else:
    #     print("Unsupported or missing action:", data.get("action"))

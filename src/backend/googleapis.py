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


def get_gmail_service_from_token(access_token: str):
    """
    Create a Gmail service using an access token from frontend OAuth.
    """
    credentials = Credentials(token=access_token)
    return build("gmail", "v1", credentials=credentials)


def get_events_service_from_token(access_token: str):
    """
    Create a Calendar service using an access token from frontend OAuth.
    """
    credentials = Credentials(token=access_token)
    return build("calendar", "v3", credentials=credentials)


def get_tasks_service_from_token(access_token: str):
    """
    Create a Tasks service using an access token from frontend OAuth.
    """
    credentials = Credentials(token=access_token)
    return build("tasks", "v1", credentials=credentials)


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


def read_emails(days: int = 2, service=None, access_token: str = None) -> list:
    """
    Read all emails from the last X days.
    Args:
        days: Number of days to look back (default: 2)
        service: Gmail service instance (optional)
        access_token: Access token from frontend OAuth (optional)
    Returns:
        List of email data dictionaries with sender, subject, date, snippet, and body
    """
    import base64
    from datetime import timedelta

    # If access_token is provided, create service from it
    if access_token and service is None:
        service = get_gmail_service_from_token(access_token)

    cutoff_date = datetime.now() - timedelta(days=days)
    query = f"after:{cutoff_date.strftime('%Y/%m/%d')}"
    emails = []

    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=50)
            .execute()
        )
        messages = results.get("messages", [])

        print(f"Found {len(messages)} emails from the last {days} days")

        for msg in messages:
            msg_data = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )

            # Extract headers
            headers = msg_data["payload"]["headers"]

            # Helper function to get header value
            def get_header(name):
                for header in headers:
                    if header["name"].lower() == name.lower():
                        return header["value"]
                return None

            # Extract sender, subject, and date
            sender = get_header("From")
            subject = get_header("Subject")
            date = get_header("Date")

            # Get snippet (short preview)
            snippet = msg_data.get("snippet", "")

            # Extract body
            body = ""
            payload = msg_data.get("payload", {})

            if "parts" in payload:
                # Email has multiple parts (HTML, plain text, etc.)
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain":
                        if "data" in part.get("body", {}):
                            body = base64.urlsafe_b64decode(
                                part["body"]["data"]
                            ).decode("utf-8")
                            break
                    elif part["mimeType"] == "text/html" and not body:
                        # Fallback to HTML if no plain text
                        if "data" in part.get("body", {}):
                            body = base64.urlsafe_b64decode(
                                part["body"]["data"]
                            ).decode("utf-8")
            else:
                # Simple email with body directly in payload
                if "data" in payload.get("body", {}):
                    body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                        "utf-8"
                    )

            email_info = {
                "id": msg["id"],
                "sender": sender,
                "subject": subject,
                "date": date,
                "snippet": snippet,
                "body": body,
            }

            emails.append(email_info)

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


def read_events(
    time_min=None,
    time_max=None,
    calendar_id="all",
    service=None,
    access_token: str = None,
) -> list:
    """
    Read calendar events within a time range.

    Args:
        time_min: Start time for events (default: today at midnight)
        time_max: End time for events (default: today at 23:59:59)
        calendar_id: Calendar ID or "all" for all calendars (default: "all")
        service: Calendar service instance (optional)
        access_token: Access token from frontend OAuth (optional)

    Returns:
        List of normalized event dictionaries
    """
    # If access_token is provided, create service from it
    if access_token and service is None:
        service = get_events_service_from_token(access_token)
    elif service is None:
        service = get_events_service()

    # Default to today's events
    if time_min is None:
        time_min = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if time_max is None:
        time_max = datetime.now().replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

    # Convert to UTC
    time_min_utc = time_min.astimezone(timezone.utc).isoformat()
    time_max_utc = time_max.astimezone(timezone.utc).isoformat()

    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        print(f"[DRY_RUN] Would fetch events from {time_min} to {time_max}")
        return {"dryRun": True, "timeMin": time_min_utc, "timeMax": time_max_utc}

    # Determine which calendars to query
    calendar_ids = []
    if calendar_id == "all":
        # Get all calendars
        try:
            calendar_list = service.calendarList().list().execute()
            calendar_ids = [cal["id"] for cal in calendar_list.get("items", [])]
            print(f"Reading from {len(calendar_ids)} calendars")
        except Exception as e:
            print(f"Error fetching calendar list: {e}")
            return []
    elif isinstance(calendar_id, list):
        calendar_ids = calendar_id
    else:
        calendar_ids = [calendar_id]

    # Fetch events from each calendar
    all_events = []
    try:
        for cal_id in calendar_ids:
            try:
                events_result = (
                    service.events()
                    .list(
                        calendarId=cal_id,
                        timeMin=time_min_utc,
                        timeMax=time_max_utc,
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )

                events = events_result.get("items", [])
                # Add calendar ID to each event for reference
                for event in events:
                    event["calendarId"] = cal_id
                all_events.extend(events)
            except Exception as e:
                print(f"Error reading calendar {cal_id}: {e}")
                continue

        # Normalize to event.json-like structure (without 'action')
        def to_local(dt_iso: str):
            try:
                # Handle trailing Z
                if dt_iso.endswith("Z"):
                    dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
                else:
                    dt = datetime.fromisoformat(dt_iso)
                return dt.astimezone()
            except Exception:
                return None

        normalized = []
        for ev in all_events:
            start = ev.get("start", {})
            end = ev.get("end", {})
            title = ev.get("summary") or "Untitled"
            description = ev.get("description") or ""
            location = ev.get("location") or ""

            date_val = None
            start_time_val = ""
            end_time_val = ""

            if "dateTime" in start:
                sdt_local = to_local(start["dateTime"])
                edt_local = to_local(end.get("dateTime")) if "dateTime" in end else None
                if sdt_local:
                    date_val = sdt_local.date().isoformat()
                    start_time_val = sdt_local.strftime("%H:%M")
                if edt_local:
                    end_time_val = edt_local.strftime("%H:%M")
            elif "date" in start:
                # All-day event
                date_val = start["date"]
                start_time_val = ""
                end_time_val = ""
            else:
                # Fallback: unknown format
                date_val = datetime.now().date().isoformat()

            normalized.append(
                {
                    "title": title,
                    "start_time": start_time_val,
                    "end_time": end_time_val,
                    "location": location,
                    "description": description,
                    "date": date_val,
                }
            )

        # Sort normalized events by date + start_time
        normalized.sort(key=lambda x: (x.get("date") or "", x.get("start_time") or ""))
        print(f"Found {len(normalized)} events across {len(calendar_ids)} calendar(s)")
        return normalized

    except Exception as e:
        print(f"Error reading events: {e}")
        return []


def read_tasks(
    lookAheadDays: int = 7,
    tasklist_id: str = "@default",
    service=None,
    access_token: str = None,
) -> list:
    """
    Read all tasks for the next week including today.

    Args:
        lookAheadDays: Number of days to look ahead (default: 7)
        tasklist_id: Task list ID to read from (default: "@default" for primary list)
        service: Tasks service instance (optional)
        access_token: Access token from frontend OAuth (optional)

    Returns:
        List of task dictionaries with title, notes, and date
    """
    from datetime import timedelta

    # If access_token is provided, create service from it
    if access_token and service is None:
        service = get_tasks_service_from_token(access_token)
    elif service is None:
        service = get_tasks_service()

    # Calculate date range: today through 7 days from now
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today + timedelta(days=lookAheadDays)

    # Convert to RFC 3339 timestamp (Tasks API format)
    due_min = today.isoformat() + "Z"
    due_max = week_end.isoformat() + "Z"

    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        print(f"[DRY_RUN] Would fetch tasks from {today.date()} to {week_end.date()}")
        return {"dryRun": True, "dueMin": due_min, "dueMax": due_max}

    try:
        # Fetch all tasks from the specified list
        results = (
            service.tasks()
            .list(tasklist=tasklist_id, showCompleted=True, showHidden=False)
            .execute()
        )

        all_tasks = results.get("items", [])

        # Filter tasks that have due dates within our range
        filtered_tasks = []
        tasks_without_due = []

        for task in all_tasks:
            due_str = task.get("due")
            if due_str:
                try:
                    # Parse the due date (RFC 3339 format)
                    due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                    # Check if within range
                    if today <= due_dt.replace(tzinfo=None) <= week_end:
                        filtered_tasks.append(task)
                except ValueError:
                    pass
            else:
                # Include tasks without due dates
                tasks_without_due.append(task)

        # Combine: tasks with due dates in range + tasks without due dates
        result_tasks = filtered_tasks + tasks_without_due

        # Helpers: date parsing and simple recurrence expansion (weekly/daily)
        def to_local_date(due_str: str) -> str:
            try:
                if not due_str:
                    return ""
                # Treat midnight UTC as a date-only field to avoid shifting a day back
                if (
                    len(due_str) >= 10
                    and due_str[0].isdigit()
                    and due_str[4] == "-"
                    and due_str[7] == "-"
                ):
                    date_part = due_str[:10]
                else:
                    date_part = None

                # Explicit midnight UTC patterns
                if due_str.endswith("T00:00:00Z") or due_str.endswith("T00:00:00.000Z"):
                    return due_str[:10]

                dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                # If it's midnight in any tz and we had a date_part, keep the literal date
                if dt.hour == 0 and dt.minute == 0 and date_part:
                    return date_part
                return dt.astimezone().date().isoformat()
            except Exception:
                # Fallback to raw date part if present
                try:
                    return due_str[:10]
                except Exception:
                    return ""

        def expand_weekly_dates(
            bydays: list[str], start_date, end_date, interval: int = 1
        ):
            # bydays like ['MO','FR']
            wmap = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
            want = {wmap[d] for d in bydays if d in wmap}
            cur = start_date
            out = []
            # Find the Monday of the current week as a base to step by interval weeks
            # Then for each week in range, add desired weekdays
            from datetime import timedelta as _td

            # Normalize to the start week (Monday) for stepping
            week_anchor = cur - _td(days=cur.weekday())
            while week_anchor <= end_date:
                for wd in sorted(want):
                    d = week_anchor + _td(days=wd)
                    if start_date <= d <= end_date:
                        out.append(d)
                week_anchor += _td(days=7 * max(1, interval))
            return sorted(out)

        def parse_recurrence(task: dict) -> list[dict]:
            rec = task.get("recurrence")
            if not rec:
                return []
            if isinstance(rec, str):
                rules = [rec]
            else:
                rules = [r for r in rec if isinstance(r, str)]
            if not rules:
                return []

            # Only basic support: FREQ=WEEKLY with BYDAY and optional INTERVAL, and FREQ=DAILY
            from datetime import timedelta as _td

            out_dates = set()
            for r in rules:
                r_up = r.upper()
                if not r_up.startswith("RRULE:"):
                    continue
                parts = {
                    kv.split("=")[0]: kv.split("=")[1]
                    for kv in r_up[6:].split(";")
                    if "=" in kv
                }
                freq = parts.get("FREQ")
                interval = int(parts.get("INTERVAL", "1") or "1")
                if freq == "WEEKLY":
                    byday = parts.get("BYDAY", "")
                    bydays = [d.strip() for d in byday.split(",") if d.strip()]
                    for d in expand_weekly_dates(
                        bydays, today.date(), week_end.date(), interval=interval
                    ):
                        out_dates.add(d)
                elif freq == "DAILY":
                    d = today.date()
                    while d <= week_end.date():
                        out_dates.add(d)
                        d += _td(days=interval)
                # Other frequencies can be added as needed
            # Convert to list of normalized task dicts (title/notes/date)
            title = (task.get("title") or "Untitled").strip()
            notes = task.get("notes") or ""
            return [
                {
                    "title": title,
                    "notes": notes,
                    "date": d.isoformat(),
                }
                for d in sorted(out_dates)
            ]

        # Normalize explicit tasks and expand simple recurrences
        normalized = []
        seen = set()  # dedupe by (title,date)
        for t in result_tasks:
            title = (t.get("title") or "Untitled").strip()
            notes = t.get("notes") or ""
            due = t.get("due")
            date_str = to_local_date(due) if due else ""
            if date_str:
                key = (title, date_str)
                if key not in seen:
                    seen.add(key)
                    normalized.append(
                        {"title": title, "notes": notes, "date": date_str}
                    )

            # Expand recurring rules into concrete dates in range
            for occ in parse_recurrence(t):
                key = (occ["title"], occ["date"])
                if key not in seen:
                    seen.add(key)
                    normalized.append(occ)

        # Sort by date then title
        normalized.sort(key=lambda x: (x.get("date") or "", x.get("title") or ""))
        print(
            f"Found {len(normalized)} tasks for the next week ({len(filtered_tasks)} with due dates, {len(tasks_without_due)} without)"
        )
        return normalized

    except Exception as e:
        print(f"Error reading tasks: {e}")
        return []


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

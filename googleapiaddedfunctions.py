def read_events(time_min=None, time_max=None, calendar_id="all", service=None) -> list:
    if service is None:
        service = get_events_service()
        
    # Default to today's events
    if time_min is None:
        time_min = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if time_max is None:
        time_max = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        
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
            calendar_ids = [cal['id'] for cal in calendar_list.get('items', [])]
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
                events_result = service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min_utc,
                    timeMax=time_max_utc,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                # Add calendar ID to each event for reference
                for event in events:
                    event['calendarId'] = cal_id
                all_events.extend(events)
            except Exception as e:
                print(f"Error reading calendar {cal_id}: {e}")
                continue
        
        # Normalize to event.json-like structure (without 'action')
        def to_local(dt_iso: str):
            try:
                # Handle trailing Z
                if dt_iso.endswith('Z'):
                    dt = datetime.fromisoformat(dt_iso.replace('Z', '+00:00'))
                else:
                    dt = datetime.fromisoformat(dt_iso)
                return dt.astimezone()
            except Exception:
                return None

        def parse_repeat(rec):
            try:
                if not rec:
                    return None
                rules = rec if isinstance(rec, list) else [rec]
                for r in rules:
                    if not isinstance(r, str):
                        continue
                    if 'FREQ=' in r:
                        freq = r.split('FREQ=', 1)[1].split(';', 1)[0].strip()
                        return freq.lower()
            except Exception:
                pass
            return None

        normalized = []
        for ev in all_events:
            start = ev.get('start', {})
            end = ev.get('end', {})
            title = ev.get('summary') or 'Untitled'
            description = ev.get('description') or ''
            location = ev.get('location') or ''

            date_val = None
            start_time_val = ''
            end_time_val = ''

            if 'dateTime' in start:
                sdt_local = to_local(start['dateTime'])
                edt_local = to_local(end.get('dateTime')) if 'dateTime' in end else None
                if sdt_local:
                    date_val = sdt_local.date().isoformat()
                    start_time_val = sdt_local.strftime('%H:%M')
                if edt_local:
                    end_time_val = edt_local.strftime('%H:%M')
            elif 'date' in start:
                # All-day event
                date_val = start['date']
                start_time_val = ''
                end_time_val = ''
            else:
                # Fallback: unknown format
                date_val = datetime.now().date().isoformat()

            normalized.append({
                'title': title,
                'start_time': start_time_val,
                'end_time': end_time_val,
                'location': location,
                'description': description,
                'date': date_val,
            })

        # Sort normalized events by date + start_time
        normalized.sort(key=lambda x: (x.get('date') or '', x.get('start_time') or ''))
        print(f"Found {len(normalized)} events across {len(calendar_ids)} calendar(s)")
        return normalized
            
    except Exception as e:
        print(f"Error reading events: {e}")
        return []

def read_tasks(lookAheadDays: int = 7, tasklist_id: str = "@default", service=None) -> list:
    """
    Read all tasks for the next week including today.
    
    Args:
        tasklist_id: Task list ID to read from (default: "@default" for primary list)
        service: Tasks service instance (optional)
    
    Returns:
        List of task dictionaries with id, title, notes, due date, status, etc.
    """
    from datetime import timedelta
    
    if service is None:
        service = get_tasks_service()
    
    # Calculate date range: today through 7 days from now
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = today + timedelta(days=lookAheadDays)
    
    # Convert to RFC 3339 timestamp (Tasks API format)
    due_min = today.isoformat() + 'Z'
    due_max = week_end.isoformat() + 'Z'
    
    dry_run = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    
    if dry_run:
        print(f"[DRY_RUN] Would fetch tasks from {today.date()} to {week_end.date()}")
        return {"dryRun": True, "dueMin": due_min, "dueMax": due_max}
    
    try:
        # Fetch all tasks from the specified list
        results = service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=True,
            showHidden=False
        ).execute()
        
        all_tasks = results.get('items', [])
        
        # Filter tasks that have due dates within our range
        filtered_tasks = []
        tasks_without_due = []
        
        for task in all_tasks:
            due_str = task.get('due')
            if due_str:
                try:
                    # Parse the due date (RFC 3339 format)
                    due_dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
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
                if len(due_str) >= 10 and due_str[0].isdigit() and due_str[4] == '-' and due_str[7] == '-':
                    date_part = due_str[:10]
                else:
                    date_part = None

                # Explicit midnight UTC patterns
                if due_str.endswith("T00:00:00Z") or due_str.endswith("T00:00:00.000Z"):
                    return due_str[:10]

                dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
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

        def expand_weekly_dates(bydays: list[str], start_date, end_date, interval: int = 1):
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
            rec = task.get('recurrence')
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
                if not r_up.startswith('RRULE:'):
                    continue
                parts = {kv.split('=')[0]: kv.split('=')[1] for kv in r_up[6:].split(';') if '=' in kv}
                freq = parts.get('FREQ')
                interval = int(parts.get('INTERVAL', '1') or '1')
                if freq == 'WEEKLY':
                    byday = parts.get('BYDAY', '')
                    bydays = [d.strip() for d in byday.split(',') if d.strip()]
                    for d in expand_weekly_dates(bydays, today.date(), week_end.date(), interval=interval):
                        out_dates.add(d)
                elif freq == 'DAILY':
                    d = today.date()
                    while d <= week_end.date():
                        out_dates.add(d)
                        d += _td(days=interval)
                # Other frequencies can be added as needed
            # Convert to list of normalized task dicts (title/notes/date)
            title = (task.get('title') or 'Untitled').strip()
            notes = task.get('notes') or ""
            return [{
                'title': title,
                'notes': notes,
                'date': d.isoformat(),
            } for d in sorted(out_dates)]

        # Normalize explicit tasks and expand simple recurrences
        normalized = []
        seen = set()  # dedupe by (title,date)
        for t in result_tasks:
            title = (t.get('title') or 'Untitled').strip()
            notes = t.get('notes') or ""
            due = t.get('due')
            date_str = to_local_date(due) if due else ""
            if date_str:
                key = (title, date_str)
                if key not in seen:
                    seen.add(key)
                    normalized.append({'title': title, 'notes': notes, 'date': date_str})

            # Expand recurring rules into concrete dates in range
            for occ in parse_recurrence(t):
                key = (occ['title'], occ['date'])
                if key not in seen:
                    seen.add(key)
                    normalized.append(occ)

        # Sort by date then title
        normalized.sort(key=lambda x: (x.get('date') or '', x.get('title') or ''))
        print(f"Found {len(normalized)} tasks for the next week ({len(filtered_tasks)} with due dates, {len(tasks_without_due)} without)")
        return normalized
        
    except Exception as e:
        print(f"Error reading tasks: {e}")
        return []

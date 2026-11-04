import json
import os
import smtplib
from email.message import EmailMessage
 
from map_compare import is_in_sync, simplify
 
HERE = os.path.dirname(os.path.abspath(__file__))
SENT_PATH = os.path.join(HERE, "sent.json")
SETTINGS_PATH = os.path.join(HERE, "settings.json")
 
 
def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)
 
 
def _label(way_id, ways):
    # "Path 123 (Main Walk)" if the way has a name tag, else "Path 123"
    name = ways.get(way_id, {}).get("tags", {}).get("name")
    return f"Path {way_id} ({name})" if name else f"Path {way_id}"
 
 
def _link(way_id):
    return f"https://www.openstreetmap.org/way/{way_id}"
 
 
def build_message(changes, fresh_data=None, saved_data=None):
    new = simplify(fresh_data) if fresh_data else {}
    old = simplify(saved_data) if saved_data else {}
 
    lines = ["A change in mapping has been detected on George Mason University's "
             "campus delivery routes.", ""]
 
    for way in changes["added"]:
        lines.append(f"{_label(way, new)} has been added. {_link(way)}")
 
    for way in changes["removed"]:
        lines.append(f"{_label(way, old)} no longer appears in the map data. "
                     f"{_link(way)}")
 
    for way in changes["changed"]:
        line = f"{_label(way, new)} has changed"
        before = old.get(way, {}).get("tags", {}).get("highway")
        after = new.get(way, {}).get("tags", {}).get("highway")
        if before and after and before != after:
            line += f" (type: {before} -> {after})"
        lines.append(f"{line}. {_link(way)}")
 
    lines += ["", "Do not reply to this message; it is generated from an automated "
              "account that is not monitored."]
    return "\n".join(lines)
 
 
def notify(changes, fresh_data=None, saved_data=None):
    """Email the changes. Pass the two Overpass maps too, to include path names
    and type changes (e.g. footway -> steps) in the email."""
    if is_in_sync(changes):
        return
 
    # Repeat guard: skip only if this exact diff was the last one sent
    if _load_json(SENT_PATH) == changes:
        return
 
    settings = _load_json(SETTINGS_PATH)
    if settings is None:
        raise FileNotFoundError(f"Missing {SETTINGS_PATH}")
 
    msg = EmailMessage()
    msg["Subject"] = "Campus delivery route change detected"
    msg["From"] = settings["sender"]
    msg["To"] = ", ".join(settings["recipients"])
    msg.set_content(build_message(changes, fresh_data, saved_data))
 
    with smtplib.SMTP_SSL(settings["smtp_host"], settings["smtp_port"]) as server:
        server.login(settings["sender"], os.environ["MAP_NOTIFY_SMTP_PASSWORD"])
        server.send_message(msg)
 
    # Only recorded after a successful send
    with open(SENT_PATH, "w") as f:
        json.dump(changes, f) 
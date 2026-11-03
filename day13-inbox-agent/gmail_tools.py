"""Day 13: small helpers that log in to Gmail and read your inbox.

They can only READ. The login asks Google for read-only access,
so nothing here can send, change or delete an email.
"""

import base64
import time
from email.message import EmailMessage
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HERE = Path(__file__).parent
CREDENTIALS_FILE = HERE / "credentials.json"
TOKEN_FILE = HERE / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def connect():
    """Log in to Gmail and return a connection to it.

    The first time, a browser window opens so you can say yes.
    After that, the saved token.json is used instead.
    """
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))
        if not creds.has_scopes(SCOPES):
            creds = None  # an old token without the new permission: log in again
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def list_emails(gmail, hours=24, limit=25):
    """Return the emails that arrived in the inbox in the last few hours."""
    since = int(time.time()) - hours * 3600
    result = gmail.users().messages().list(
        userId="me", q=f"in:inbox after:{since}", maxResults=limit
    ).execute()
    emails = []
    for item in result.get("messages", []):
        message = gmail.users().messages().get(
            userId="me", id=item["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
        emails.append({
            "id": message["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", ""),
            "unread": "UNREAD" in message.get("labelIds", []),
            "preview": message.get("snippet", ""),
        })
    return emails


def find_text(part):
    """Look through an email's parts and return the first plain-text one."""
    data = part.get("body", {}).get("data")
    if part.get("mimeType") == "text/plain" and data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for inner in part.get("parts", []):
        text = find_text(inner)
        if text:
            return text
    return ""


def read_email(gmail, email_id, max_chars=4000):
    """Return one email as text: who sent it, the subject, and the message."""
    message = gmail.users().messages().get(userId="me", id=email_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in message["payload"].get("headers", [])}
    text = find_text(message["payload"]) or message.get("snippet", "")
    return (f"From: {headers.get('From', '')}\n"
            f"Subject: {headers.get('Subject', '(no subject)')}\n"
            f"Date: {headers.get('Date', '')}\n\n"
            f"{text[:max_chars]}")

def get_headers(gmail, email_id):
    """Return who sent one email, its subject, and the details a reply needs."""
    message = gmail.users().messages().get(
        userId="me", id=email_id, format="metadata",
        metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References"],
    ).execute()
    headers = {h["name"].lower(): h["value"] for h in message["payload"].get("headers", [])}
    return {
        "from": headers.get("from", ""),
        "reply_to": headers.get("reply-to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "message_id": headers.get("message-id", ""),
        "references": headers.get("references", ""),
        "thread_id": message["threadId"],
    }


def create_reply_draft(gmail, email_id, reply_text):
    """Save a reply to one email as a draft in Gmail. It does NOT send it."""
    original = get_headers(gmail, email_id)
    subject = original["subject"]
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    reply = EmailMessage()
    reply["To"] = original["reply_to"] or original["from"]
    reply["Subject"] = subject
    if original["message_id"]:
        reply["In-Reply-To"] = original["message_id"]
        reply["References"] = (original["references"] + " " + original["message_id"]).strip()
    reply.set_content(reply_text)

    raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
    draft = gmail.users().drafts().create(
        userId="me", body={"message": {"raw": raw, "threadId": original["thread_id"]}}
    ).execute()
    return draft["id"]
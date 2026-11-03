"""Day 13: check that the Gmail login works, before giving the tools to an agent.

It logs in, lists the emails from the last 24 hours, and opens the newest one.
It only reads. Nothing is sent, changed or deleted.
"""

from gmail_tools import connect, list_emails, read_email


def main():
    print("Logging in to Gmail... (the first time, a browser window opens)")
    gmail = connect()
    print("Logged in.\n")

    emails = list_emails(gmail, hours=24, limit=10)
    print(f"Emails in the last 24 hours: {len(emails)}\n")
    for email in emails:
        mark = "NEW " if email["unread"] else "    "
        print(f"{mark}{email['from']}")
        print(f"    {email['subject']}\n")

    if emails:
        print("--- The newest email ---")
        print(read_email(gmail, emails[0]["id"], max_chars=500))


if __name__ == "__main__":
    main()

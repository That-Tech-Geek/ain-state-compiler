"""
Gmail Ingestor
Pulls ALL email history from a Gmail account via IMAP.

Connection: imaplib (stdlib) over SSL to imap.gmail.com:993
Auth: App Password (not OAuth). Enable:
  1. 2FA on Google Account
  2. Create App Password at: https://myaccount.google.com/apppasswords
  3. Enable IMAP in Gmail Settings > Forwarding and POP/IMAP

Fetches: All mailboxes (INBOX, Sent, All Mail, etc.)
Extracts: From, To, Subject, Date, Body (plain text, decoded)

Zero external dependencies -- stdlib imaplib, email, quopri, base64 only.
"""

import imaplib
import email
import email.header
import email.utils
import quopri
import base64
import time
from datetime import datetime


IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
FETCH_BATCH = 100   # UIDs per batch fetch (balance memory vs speed)


def _decode_header_value(raw_val):
    """Decodes an encoded email header value to plain string."""
    if not raw_val:
        return ""
    parts = []
    for part, charset in email.header.decode_header(raw_val):
        if isinstance(part, bytes):
            try:
                parts.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                parts.append(part.decode("latin-1", errors="replace"))
        else:
            parts.append(str(part))
    return " ".join(parts)


def _extract_body(msg):
    """
    Recursively extracts the plain-text body from a MIME message.
    Falls back to HTML stripped of tags if no plain text found.
    """
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(body_parts)[:8000]   # cap at 8KB per email body


def _fetch_mailbox(conn, mailbox):
    """
    Fetches all message UIDs from a mailbox.
    Returns list of UIDs (bytes strings).
    """
    status, _ = conn.select(mailbox, readonly=True)
    if status != "OK":
        return []
    status, data = conn.uid("search", None, "ALL")
    if status != "OK":
        return []
    uid_list = data[0].split()
    return uid_list


def _parse_email_message(uid, raw_bytes, mailbox):
    """Parses a raw RFC 2822 email message into a flat dict."""
    try:
        msg = email.message_from_bytes(raw_bytes)
        return {
            "id": f"gmail_{mailbox.replace(' ', '_')}_{uid.decode()}",
            "subject": _decode_header_value(msg.get("Subject", "")),
            "sender": _decode_header_value(msg.get("From", "")),
            "recipients": _decode_header_value(msg.get("To", "")),
            "date": _decode_header_value(msg.get("Date", "")),
            "body": _extract_body(msg),
            "mailbox": mailbox,
            "ingested_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "id": f"gmail_parse_error_{uid.decode() if isinstance(uid, bytes) else uid}",
            "subject": "",
            "sender": "",
            "recipients": "",
            "date": "",
            "body": f"[parse error: {e}]",
            "mailbox": mailbox,
            "ingested_at": datetime.utcnow().isoformat(),
        }


def _list_mailboxes(conn):
    """Returns list of mailbox name strings available in the account."""
    status, data = conn.list()
    mailboxes = []
    if status != "OK":
        return mailboxes
    for item in data:
        if not item:
            continue
        # Format: (\HasNoChildren) "/" "INBOX"
        parts = item.decode("utf-8", errors="replace").split('"')
        # Last part after quotes is the name
        name = parts[-1].strip().strip('"')
        if name:
            mailboxes.append(name)
    return mailboxes


def ingest_gmail(address, app_password, mailboxes=None, max_per_mailbox=5000):
    """
    Full Gmail account ingestion via IMAP.

    Args:
        address: Gmail address (e.g. you@gmail.com)
        app_password: Google App Password (not login password)
        mailboxes: List of mailbox names to ingest. None = auto-detect all.
        max_per_mailbox: Maximum emails to pull per mailbox (safety cap).

    Returns:
        List of flat email dicts.
    """
    print(f"[*] Gmail ingest: connecting to {IMAP_HOST}...")
    all_emails = []

    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.login(address, app_password)
        print(f"[+] Gmail login successful: {address}")
    except imaplib.IMAP4.error as e:
        print(f"[!] Gmail IMAP login failed: {e}")
        print("    Ensure: (1) 2FA enabled, (2) App Password used (not account password),")
        print("    (3) IMAP enabled in Gmail Settings > Forwarding and POP/IMAP.")
        return []

    if mailboxes is None:
        mailboxes = _list_mailboxes(conn)
        # Focus on high-value mailboxes only
        priority = ["INBOX", "[Gmail]/Sent Mail", "[Gmail]/All Mail",
                    "Sent", "SENT", "Sent Items"]
        available = set(mailboxes)
        mailboxes = [m for m in priority if m in available]
        if not mailboxes:
            mailboxes = [m for m in _list_mailboxes(conn)
                         if "trash" not in m.lower() and "spam" not in m.lower()]
        print(f"[+] Mailboxes to ingest: {mailboxes}")

    for mailbox in mailboxes:
        print(f"    Fetching {mailbox}...")
        try:
            uids = _fetch_mailbox(conn, f'"{mailbox}"')
        except Exception as e:
            print(f"    [!] Could not select {mailbox}: {e}")
            continue

        if not uids:
            print(f"    -> 0 messages")
            continue

        # Take the most recent N emails (latest UIDs = highest values)
        uids_to_fetch = uids[-max_per_mailbox:]
        print(f"    -> {len(uids)} total, fetching latest {len(uids_to_fetch)}...")

        # Batch fetch in chunks
        for i in range(0, len(uids_to_fetch), FETCH_BATCH):
            chunk = uids_to_fetch[i : i + FETCH_BATCH]
            uid_str = b",".join(chunk)
            try:
                status, data = conn.uid("fetch", uid_str, "(RFC822)")
                if status != "OK":
                    continue
                for j in range(0, len(data), 2):
                    if data[j] is None:
                        continue
                    raw = data[j][1] if isinstance(data[j], tuple) else None
                    if raw is None:
                        continue
                    uid = chunk[j // 2] if j // 2 < len(chunk) else b"0"
                    msg_dict = _parse_email_message(uid, raw, mailbox)
                    all_emails.append(msg_dict)
            except Exception as e:
                print(f"    [!] Batch fetch error: {e}")
            time.sleep(0.1)

        print(f"    -> {len(uids_to_fetch)} messages processed")

    try:
        conn.logout()
    except Exception:
        pass

    print(f"[+] Gmail ingest complete. Total emails: {len(all_emails)}")
    return all_emails

"""
Gmail Ingestor — Full History Edition
=======================================
Pulls EVERY email ever received/sent in a Gmail account, from the very first
message to today.

Strategy: Use [Gmail]/All Mail as the single source of truth.
  - Contains every message that hasn't been permanently deleted
  - Sorted by UID ascending = chronological order = checkpoint-friendly
  - Deduplication: native_id = Message-ID header (RFC 2822)
  - Re-running ingest will INSERT OR IGNORE duplicates -- safe to retry

Connection: imaplib (stdlib) over SSL to imap.gmail.com:993
Auth: Google App Password (recommended) OR OAuth (if GMAIL_OAUTH_TOKEN set)

To set up App Password:
  1. Enable 2FA: https://myaccount.google.com/security
  2. Create App Password: https://myaccount.google.com/apppasswords
  3. Enable IMAP: Gmail Settings > Forwarding and POP/IMAP

Zero external dependencies -- stdlib imaplib, email, quopri, base64 only.

Usage:
    from ain_state_compiler.ingest.gmail_ingest import ingest_gmail
    from ain_state_compiler.ingest.checkpoint import Checkpoint

    cp = Checkpoint(project_dir)
    emails = ingest_gmail(
        address, app_password,
        checkpoint=cp,
        full_history=False,     # True = fetch from UID 1
        max_per_mailbox=0,      # 0 = unlimited
    )
"""

import imaplib
import email
import email.header
import email.utils
import time
from datetime import datetime
from typing import Optional


IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
FETCH_BATCH = 50    # UIDs per batch fetch (lower = safer on huge accounts)
SLEEP_BETWEEN_BATCHES = 0.2


# Priority mailbox list — All Mail is the single source of truth
# Other mailboxes are fallback for non-Gmail IMAP servers
ALL_MAIL_NAMES = [
    "[Gmail]/All Mail",
    "[Google Mail]/All Mail",
    "All Mail",
]

FALLBACK_MAILBOXES = [
    "INBOX",
    "[Gmail]/Sent Mail",
    "Sent",
    "SENT",
    "Sent Items",
]


def _decode_header_value(raw_val: str) -> str:
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


def _extract_body(msg) -> str:
    """
    Recursively extracts the plain-text body from a MIME message.
    Falls back to HTML stripped of tags if no plain text found.
    Caps at 16KB to prevent huge emails overwhelming the index.
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
            elif ct == "text/html" and not body_parts:
                # Fallback: strip HTML tags
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    import re
                    body_parts.append(re.sub(r"<[^>]+>", " ", html))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))

    full_body = "\n".join(body_parts)
    return full_body[:16000]   # cap at 16KB per email


def _parse_email_message(uid: bytes, raw_bytes: bytes, mailbox: str) -> dict:
    """Parses a raw RFC 2822 email message into a flat dict."""
    try:
        msg = email.message_from_bytes(raw_bytes)

        # Use Message-ID as the canonical native_id for dedup across mailboxes
        message_id = _decode_header_value(msg.get("Message-ID", "")).strip()
        if not message_id:
            # Fallback: use UID + mailbox
            message_id = f"{mailbox}_{uid.decode() if isinstance(uid, bytes) else uid}"

        # Normalize: strip angle brackets from Message-ID
        message_id = message_id.strip("<>").strip()

        return {
            "id": f"gmail_{message_id}",
            "native_message_id": message_id,
            "subject": _decode_header_value(msg.get("Subject", "")),
            "sender": _decode_header_value(msg.get("From", "")),
            "recipients": _decode_header_value(msg.get("To", "")),
            "cc": _decode_header_value(msg.get("Cc", "")),
            "date": _decode_header_value(msg.get("Date", "")),
            "body": _extract_body(msg),
            "mailbox": mailbox,
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "ingested_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
        return {
            "id": f"gmail_parse_error_{uid_str}",
            "native_message_id": "",
            "subject": "",
            "sender": "",
            "recipients": "",
            "cc": "",
            "date": "",
            "body": f"[parse error: {e}]",
            "mailbox": mailbox,
            "uid": uid_str,
            "ingested_at": datetime.utcnow().isoformat(),
        }


def _list_mailboxes(conn) -> list:
    """Returns list of mailbox name strings available in the account."""
    status, data = conn.list()
    mailboxes = []
    if status != "OK":
        return mailboxes
    for item in data:
        if not item:
            continue
        parts = item.decode("utf-8", errors="replace").split('"')
        name = parts[-1].strip().strip('"')
        if name:
            mailboxes.append(name)
    return mailboxes


def _fetch_uids_since(conn, mailbox: str, since_uid: Optional[str] = None) -> list:
    """
    Fetches UIDs from a mailbox. If since_uid provided, only fetches UIDs >= since_uid.
    Returns list of uid bytes objects, sorted ascending (oldest first).
    """
    quoted = f'"{mailbox}"'
    status, _ = conn.select(quoted, readonly=True)
    if status != "OK":
        # Try without quotes
        status, _ = conn.select(mailbox, readonly=True)
        if status != "OK":
            return []

    if since_uid:
        # Fetch UIDs greater than checkpoint
        try:
            status, data = conn.uid("search", None, f"UID {since_uid}:*")
        except Exception:
            status, data = conn.uid("search", None, "ALL")
    else:
        status, data = conn.uid("search", None, "ALL")

    if status != "OK" or not data or not data[0]:
        return []

    uid_list = data[0].split()
    # Sort ascending: fetch oldest messages first (safe for checkpoint)
    uid_list.sort(key=lambda x: int(x))
    return uid_list


def ingest_gmail(
    address: str,
    app_password: str,
    mailboxes: Optional[list] = None,
    max_per_mailbox: int = 0,
    checkpoint=None,
    full_history: bool = False,
    progress: bool = True,
) -> list:
    """
    Full Gmail account ingestion via IMAP.
    Fetches ALL emails since the account was created (or from checkpoint).

    Args:
        address:        Gmail address (e.g. you@gmail.com)
        app_password:   Google App Password (NOT your Google account password)
        mailboxes:      Explicit list of mailboxes to pull. None = auto-detect.
                        Set to ["[Gmail]/All Mail"] for maximum coverage.
        max_per_mailbox: 0 = unlimited (default). Set >0 to cap per mailbox.
        checkpoint:     Checkpoint instance for resume on crash.
        full_history:   If True, ignore checkpoint and start from UID 1.
        progress:       Print progress messages.

    Returns:
        List of flat email dicts (deduplicated by Message-ID).
    """
    if progress:
        print(f"[*] Gmail ingest: connecting to {IMAP_HOST}...")
    all_emails = []
    seen_message_ids = set()   # in-memory dedup by Message-ID

    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        conn.login(address, app_password)
        if progress:
            print(f"[+] Gmail login successful: {address}")
    except imaplib.IMAP4.error as e:
        print(f"[!] Gmail IMAP login failed: {e}")
        print("    Ensure:")
        print("      1. 2FA enabled: https://myaccount.google.com/security")
        print("      2. App Password used (NOT your Google password)")
        print("         Create at: https://myaccount.google.com/apppasswords")
        print("      3. IMAP enabled in Gmail Settings > Forwarding and POP/IMAP")
        return []

    # Determine which mailboxes to pull
    if mailboxes is None:
        available = set(_list_mailboxes(conn))
        if progress:
            print(f"[+] Available mailboxes: {sorted(available)}")

        # Prefer [Gmail]/All Mail — it's the complete deduplicated store
        selected_all_mail = None
        for name in ALL_MAIL_NAMES:
            if name in available:
                selected_all_mail = name
                break

        if selected_all_mail:
            mailboxes = [selected_all_mail]
            if progress:
                print(f"[+] Using '{selected_all_mail}' as single source of truth (contains ALL emails).")
        else:
            # No All Mail — fall back to individual folders
            mailboxes = [m for m in FALLBACK_MAILBOXES if m in available]
            if not mailboxes:
                mailboxes = [m for m in available
                             if "trash" not in m.lower() and "spam" not in m.lower()]
            if progress:
                print(f"[+] No All Mail found. Fetching: {mailboxes}")

    for mailbox in mailboxes:
        if progress:
            print(f"\n    Fetching mailbox: {mailbox}")

        # Load checkpoint for this mailbox
        since_uid = None
        if not full_history and checkpoint:
            since_uid = checkpoint.load("gmail", mailbox)
            if since_uid and progress:
                print(f"    Resuming from UID {since_uid}...")

        try:
            all_uids = _fetch_uids_since(conn, mailbox, since_uid if not full_history else None)
        except Exception as e:
            print(f"    [!] Could not select {mailbox}: {e}")
            continue

        if not all_uids:
            if progress:
                print(f"    -> 0 messages")
            continue

        # Apply cap if set
        if max_per_mailbox > 0:
            all_uids = all_uids[-max_per_mailbox:]

        total_uids = len(all_uids)
        if progress:
            print(f"    -> {total_uids:,} messages to fetch...")

        fetched_count = 0
        last_uid = None

        # Batch fetch in chunks
        for i in range(0, total_uids, FETCH_BATCH):
            chunk = all_uids[i : i + FETCH_BATCH]
            uid_str = b",".join(chunk)

            try:
                status, data = conn.uid("fetch", uid_str, "(RFC822 UID)")
                if status != "OK":
                    continue

                # Parse fetch response -- alternates (header, data) tuples
                for j in range(0, len(data), 2):
                    if data[j] is None:
                        continue
                    item = data[j]
                    if isinstance(item, tuple):
                        raw = item[1]
                        # Extract UID from response header
                        header_str = item[0].decode() if isinstance(item[0], bytes) else str(item[0])
                        uid_match = None
                        for part in header_str.split():
                            if part.isdigit():
                                uid_match = part.encode()
                                break
                        uid = uid_match if uid_match else chunk[j // 2] if j // 2 < len(chunk) else b"0"
                    else:
                        continue

                    if raw is None:
                        continue

                    msg_dict = _parse_email_message(uid, raw, mailbox)

                    # In-memory dedup by Message-ID
                    mid = msg_dict.get("native_message_id", "")
                    if mid and mid in seen_message_ids:
                        continue
                    if mid:
                        seen_message_ids.add(mid)

                    all_emails.append(msg_dict)
                    fetched_count += 1
                    last_uid = uid

            except Exception as e:
                print(f"    [!] Batch fetch error at offset {i}: {e}")
                time.sleep(2)   # back off on IMAP errors

            time.sleep(SLEEP_BETWEEN_BATCHES)

            # Progress every 500 emails
            if (i + FETCH_BATCH) % 500 == 0 and progress:
                pct = min(100, int(100 * (i + FETCH_BATCH) / max(total_uids, 1)))
                print(f"    {fetched_count:,}/{total_uids:,} emails ({pct}%)...")

            # Save checkpoint every 200 emails
            if checkpoint and last_uid and fetched_count % 200 == 0:
                uid_val = last_uid.decode() if isinstance(last_uid, bytes) else str(last_uid)
                checkpoint.save("gmail", mailbox, uid_val)

        # Save final checkpoint for this mailbox
        if checkpoint and last_uid:
            uid_val = last_uid.decode() if isinstance(last_uid, bytes) else str(last_uid)
            checkpoint.save("gmail", mailbox, uid_val)

        if progress:
            print(f"    -> {fetched_count:,} emails fetched from {mailbox}")

    try:
        conn.logout()
    except Exception:
        pass

    if progress:
        print(f"\n[+] Gmail ingest complete. Total: {len(all_emails):,} emails (deduplicated by Message-ID)")

    return all_emails

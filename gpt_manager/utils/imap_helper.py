"""
IMAP을 사용하여 이메일함에서 OpenAI 인증 코드를 추출합니다.
기존 reset_gpt_accounts_parallel.py의 get_openai_code() 함수를 그대로 분리한 것입니다.
"""
import re
import time
import imaplib
import email
import email.utils
from datetime import datetime, timezone, timedelta
from email.header import decode_header


def get_openai_code(email_user, email_pass, target_email, login_timestamp=None, max_retries=10, delay=5, log_callback=None):
    """IMAP을 사용하여 이메일함에서 OpenAI 인증 코드를 추출합니다."""
    def log(tag, msg):
        if log_callback:
            log_callback(tag, msg)

    tag = target_email.split('@')[0] if '@' in target_email else target_email
    log(tag, f"📧 이메일 인증 코드 확인 중...")

    if login_timestamp is None:
        login_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)

    for attempt in range(max_retries):
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_user, email_pass)
            mail.select('"[Gmail]/&yATMtLz0rQDVaA-"')

            status, messages = mail.search(None, 'ALL')
            if status != "OK":
                mail.logout()
                time.sleep(delay)
                continue

            mail_ids = messages[0].split()
            if not mail_ids:
                mail.logout()
                time.sleep(delay)
                continue

            found_code = None
            for mail_id in reversed(mail_ids[-20:]):
                status, msg_data = mail.fetch(mail_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        sender = str(msg.get("From", "")).lower()
                        if "openai" not in sender and "chatgpt" not in sender and target_email.lower() not in sender:
                            continue

                        # ★ 수신자(To) 확인 — 병렬 처리 시 다른 계정의 코드 혼동 방지
                        to_header = str(msg.get("To", "")).lower()
                        delivered_to = str(msg.get("Delivered-To", "")).lower()
                        x_original_to = str(msg.get("X-Original-To", "")).lower()
                        if (target_email.lower() not in to_header
                            and target_email.lower() not in delivered_to
                            and target_email.lower() not in x_original_to):
                            continue

                        try:
                            mail_date = email.utils.parsedate_to_datetime(msg.get("Date"))
                            if mail_date < login_timestamp:
                                continue
                        except Exception:
                            pass

                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True).decode(errors='replace')
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors='replace')

                        body = re.sub(r'<style[^>]*>.*?</style>', ' ', body, flags=re.DOTALL|re.IGNORECASE)
                        body = re.sub(r'<[^>]+>', ' ', body)
                        body = re.sub(r'#\d{6}', ' ', body)

                        match = re.search(r'(?<!\d)(\d{6})(?!\d)', body)
                        if match:
                            found_code = match.group(1)
                            break

                if found_code:
                    break

            mail.logout()

            if found_code:
                return found_code
        except Exception as e:
            log(tag, f"⚠️ 이메일 확인 중 오류: {e}")

        log(tag, f"⏳ 인증 코드 대기 중... ({attempt + 1}/{max_retries})")
        time.sleep(delay)

    log(tag, "❌ 인증 코드를 찾을 수 없습니다.")
    return None

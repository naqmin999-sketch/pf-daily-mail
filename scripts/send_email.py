"""
PF Daily Market Intelligence — 이메일 발송
SMTP를 통해 HTML 리포트를 지정 수신자에게 발송합니다.
Gmail 앱 비밀번호 또는 사내 SMTP 서버 사용.
"""
import os
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent.parent
REPORT_DIR = BASE_DIR / "reports"


def send_report(html_path=None):
    sender        = os.getenv("EMAIL_SENDER", "")
    password      = os.getenv("EMAIL_PASSWORD", "")
    recipients_raw = os.getenv("EMAIL_RECIPIENTS", "")
    smtp_host     = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.getenv("EMAIL_SMTP_PORT", "587"))

    if not sender or not password or not recipients_raw:
        print("  [SKIP] 이메일 설정 없음 — .env 에 EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECIPIENTS 필요")
        return False

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if html_path is None:
        today     = datetime.date.today().isoformat()
        html_path = REPORT_DIR / f"{today}_report.html"

    html_path = Path(html_path)
    if not html_path.exists():
        print(f"  [ERROR] 리포트 파일 없음: {html_path}")
        return False

    html_content = html_path.read_text(encoding="utf-8")
    today_str    = datetime.date.today().strftime("%Y년 %m월 %d일")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[PF Daily] {today_str} 시황 브리핑"
    msg["From"]    = sender
    msg["To"]      = ", ".join(recipients)

    plain = (
        f"PF Daily Market Intelligence — {today_str}\n"
        "HTML 이메일을 지원하는 메일 클라이언트에서 확인하세요.\n"
        f"리포트 파일: {html_path}"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"  → 이메일 발송 완료: {', '.join(recipients)}")
        return True
    except Exception as e:
        print(f"  [ERROR] 이메일 발송 실패: {e}")
        return False


if __name__ == "__main__":
    send_report()

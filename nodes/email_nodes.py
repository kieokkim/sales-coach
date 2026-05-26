import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger(__name__)


def email_send_node(state: dict) -> dict:
    errors = list(state.get("errors", []))
    email_sent = False

    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_PASSWORD", "")

    if not sender or not password:
        logger.warning("EMAIL_SENDER / EMAIL_PASSWORD 미설정, 이메일 발송 생략")
        return {**state, "email_sent": False, "errors": errors}

    recipients = state.get("recipient_emails", [])
    if not recipients:
        env_recipients = os.getenv("EMAIL_RECIPIENTS", "")
        recipients = [r.strip() for r in env_recipients.replace(",", "\n").splitlines() if r.strip()]

    if not recipients:
        logger.warning("수신자 이메일 없음, 발송 생략")
        return {**state, "email_sent": False, "errors": errors}

    try:
        report_date = state.get("report_date", "")
        output_options = state.get("output_options", ["html", "excel"])

        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"[판매일보] {report_date} 매출 리포트"
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        html_report = state.get("html_report", "")
        if "html" in output_options and html_report:
            msg.attach(MIMEText(html_report, "html", "utf-8"))
        else:
            msg.attach(MIMEText(f"[판매일보] {report_date} 매출 리포트를 첨부 파일로 확인하세요.", "plain", "utf-8"))

        excel_path = state.get("excel_path", "")
        if "excel" in output_options and excel_path and Path(excel_path).exists():
            with open(excel_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="xlsx")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=f"sales_report_{report_date}.xlsx",
                )
                msg.attach(attachment)

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        email_sent = True
        logger.info(f"이메일 발송 완료 → {recipients}")
    except Exception as e:
        logger.warning(f"이메일 발송 실패: {e}")
        errors.append(f"이메일 발송 실패: {e}")

    return {**state, "email_sent": email_sent, "errors": errors}

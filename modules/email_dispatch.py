# modules/email_dispatch.py
# Sends payslip PDF via Outlook/Office 365 SMTP
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587

def send_payslip_email(sender_email, sender_password, recipient_email,
                       emp_name, month_name, year, pdf_buf, pdf_filename):
    """
    Send payslip PDF as attachment via Outlook SMTP.
    pdf_buf: io.BytesIO object from generate_payslip()
    """
    msg = MIMEMultipart()
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    msg["Subject"] = f"Salary Slip — {month_name} {year}"

    body = f"""Dear {emp_name},

Please find attached your salary slip for {month_name} {year}.

This is a system-generated email. Please do not reply to this message.
For any queries, contact the HR department.

Regards,
HR & Payroll Team
"""
    msg.attach(MIMEText(body, "plain"))

    # Attach PDF
    pdf_buf.seek(0)
    part = MIMEBase("application", "octet-stream")
    part.set_payload(pdf_buf.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

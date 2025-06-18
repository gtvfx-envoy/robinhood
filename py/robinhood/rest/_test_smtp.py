import json
import smtplib
from email.mime.text import MIMEText

def _get_smtp_settings():
    """ """
    SERVICE_FILE = "//THO_CLOUD/gavyn/service/smtp.json"
    with open(SERVICE_FILE, 'r') as data_file:
        data = json.load(data_file)
    return data

SMTP_SETTINGS = _get_smtp_settings()

SMTP_SERVER = SMTP_SETTINGS.get("server")
SMTP_PORT = SMTP_SETTINGS.get("port")
EMAIL_SENDER = SMTP_SETTINGS.get("sender")
EMAIL_PASSWORD = SMTP_SETTINGS.get("password")
EMAIL_RECIPIENT = SMTP_SETTINGS.get("recipient")

def send_test_email():
    msg = MIMEText("This is a test email from your trading bot!")
    msg["Subject"] = "SMTP Test"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

send_test_email()

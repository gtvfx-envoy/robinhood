import smtplib
from email.mime.text import MIMEText

def send_email_alert(subject, body, smtp_settings):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_settings["sender"]
        msg["To"] = smtp_settings["recipient"]

        with smtplib.SMTP(smtp_settings["server"], smtp_settings["port"]) as server:
            server.starttls()
            server.login(smtp_settings["sender"], smtp_settings["password"])
            server.sendmail(smtp_settings["sender"], smtp_settings["recipient"], msg.as_string())

    except Exception as e:
        print(f"Failed to send email alert: {e}")

def send_text_alert(phone_number, message, twilio_client):
    try:
        twilio_client.messages.create(
            body=message,
            from_='your_twilio_number',
            to=phone_number
        )
    except Exception as e:
        print(f"Failed to send text alert: {e}")
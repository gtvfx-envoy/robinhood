import json
import smtplib
from email.mime.text import MIMEText


def _get_smtp_settings():
    """Loads SMTP settings from a JSON file."""
    SERVICE_FILE = "//THO_CLOUD/gavyn/service/smtp.json" # Path to your SMTP config
    try:
        with open(SERVICE_FILE, 'r') as data_file:
            data = json.load(data_file)
        return data
    except FileNotFoundError:
        print(f"Error: SMTP settings file not found at {SERVICE_FILE}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {SERVICE_FILE}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while loading SMTP settings: {e}")
        return None


class Notifier:
    def __init__(self, smtp_settings=None, twilio_config=None):
        if smtp_settings:
            self.smtp_settings = smtp_settings
        else:
            # Call your function to get SMTP settings
            self.smtp_settings = _get_smtp_settings()

        # If using Twilio, initialize the client
        # if twilio_config:
        #     self.twilio_client = Client(twilio_config["account_sid"], twilio_config["auth_token"])
        # else:
        #     self.twilio_client = None

    def send_email(self, subject, body):
        if not self.smtp_settings:
            print("SMTP settings not configured or failed to load.")
            return
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.smtp_settings["sender"]
            msg["To"] = self.smtp_settings["recipient"] # Or make recipient a parameter

            with smtplib.SMTP(self.smtp_settings["server"], self.smtp_settings["port"]) as server:
                server.starttls()
                server.login(self.smtp_settings["sender"], self.smtp_settings["password"])
                server.sendmail(self.smtp_settings["sender"], self.smtp_settings["recipient"], msg.as_string())
            print("Email alert sent successfully.")
        except KeyError as e:
            print(f"Failed to send email: Missing key {e} in SMTP settings.")
        except Exception as e:
            print(f"Failed to send email alert: {e}")

    def send_sms(self, phone_number, message):
        # if not self.twilio_client:
        #     print("Twilio client not configured.")
        #     return
        # try:
        #     self.twilio_client.messages.create(
        #         body=message,
        #         from_='your_twilio_number', # This should be part of twilio_config
        #         to=phone_number
        #     )
        #     print("SMS alert sent successfully.")
        # except Exception as e:
        #     print(f"Failed to send text alert: {e}")
        print(f"SMS functionality for {phone_number} with message '{message}' would be here (Twilio client not implemented in this snippet).")


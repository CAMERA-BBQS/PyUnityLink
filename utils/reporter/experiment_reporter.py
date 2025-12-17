# Experiment night reporter
import os
import schedule
import threading
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

class ExperimentReporter:
    def __init__(self, ui_instance, email_config):
        self.ui = ui_instance
        self.email_config = email_config

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        base_dir = os.path.join(project_root, "logs")
        self.report_log_dir = os.path.join(base_dir, "email_report")

        # Ensure all log directories exist
        for directory in [self.report_log_dir]:
            os.makedirs(directory, exist_ok=True)

        # Schedule the report to run every day at 9:30 PM
        schedule.every().day.at("21:30").do(self.send_report)
        #schedule.every(1).minutes.do(self.send_report)     # (TESTING) sends reports after 1 min

        # Run schedule in a background thread
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def _run_scheduler(self):
        while True:
            schedule.run_pending()
            time.sleep(30)
    
    def reset_ui_counter(self):
        # Reset UI counters
        self.ui.triggered_count = 0
        self.ui.responded_count = 0
        self.ui.completed_count = 0
        self.ui.ignored_count = 0

        self.ui.triggered_label.config(text="Triggered: 0")
        self.ui.responded_label.config(text="Responded: 0")
        self.ui.completed_label.config(text="Completed: 0")
        self.ui.ignored_label.config(text="Ignored: 0")

        self.ui.update_report_counter()

        self.ui.connection_manager.log_timestamped(f"EMA Counter reset for today.")


    def send_report(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        unsent_path = os.path.join(self.report_log_dir, f"{date_str}.unsent.txt")
        sent_path = os.path.join(self.report_log_dir, f"{date_str}.sent.txt")

        if not os.path.exists(unsent_path):
            print(self.report_log_dir)
            print(date_str)
            print(unsent_path)
            print(sent_path)
            self.ui.connection_manager.log_timestamped(f"No unsent report found for today: {date_str}.")
            return

        try:
            with open(unsent_path, "r") as f:
                content = f.read().strip()
                counts = {k.strip(): int(v.strip()) for k, v in (pair.split(":") for pair in content.split(","))}
        except Exception as e:
            self.ui.connection_manager.log_timestamped(f"Failed to read report file: {e}")
            return

        subject = f"Daily EMA Report - {date_str}"
        body = (
            "Automated daily summary for today's EMA sessions:\n\n"
            f"Total EMAs Triggered: {counts.get('Triggered', 0)}\n"
            f"  - Responded: {counts.get('Responded', 0)}\n"
            f"    - Of those responded, {counts.get('Completed', 0)} were fully completed.\n"
            f"  - Ignored: {counts.get('Ignored', 0)}\n\n"
            f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "Please do not reply to this email."
        )

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.email_config['sender']
        msg['To'] = ", ".join(self.email_config['recipient'])

        try:
            with smtplib.SMTP_SSL(self.email_config['smtp_server'], self.email_config['port']) as server:
                server.login(self.email_config['sender'], self.email_config['password'])
                server.send_message(msg)
            self.ui.connection_manager.log_timestamped(f"[{datetime.now()}] - Email sent successfully.")
            os.rename(unsent_path, sent_path)
            self.reset_ui_counter()
        except Exception as e:
            self.ui.connection_manager.log_timestamped(f"[{datetime.now()}] - Failed to send email: {e}")

    def send_email(self, subject, body):
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.email_config['sender']
        msg['To'] = ", ".join(self.email_config['recipient'])
        
        try:
            with smtplib.SMTP_SSL(self.email_config['smtp_server'], self.email_config['port']) as server:
                server.login(self.email_config['sender'], self.email_config['password'])
                server.send_message(msg)
            self.ui.connection_manager.log_timestamped(f"[{datetime.now()}] - Alert email sent successfully.")
        except Exception as e:
            self.ui.connection_manager.log_timestamped(f"[{datetime.now()}] - Failed to send alert email: {e}")
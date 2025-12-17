import tkinter as tk
from ui.ui_handler import UI
from connection.connection_handler import ConnectionManager
from utils.qrcode.qrcode_display import QRCodeDisplay
from utils.reporter.experiment_reporter import ExperimentReporter

if __name__ == '__main__':
    ui = UI(None)

    email_config = {
        "smtp_server": "smtp.gmail.com",
        "port": 465,
        # Email and Password for sending daily summary email
        "sender": "",
        "password": "",
        "recipient": [""]
    }
    reporter = ExperimentReporter(ui_instance=ui, email_config=email_config)

    conn_manager = ConnectionManager(ui, ui.update_next_notification_time, reporter)
    ui.connection_manager = conn_manager


    ui.start()
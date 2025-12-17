import tkinter as tk
import os
from datetime import datetime
from utils.qrcode.qrcode_display import QRCodeDisplay

class UI:
    def __init__(self, conn_manager):
        self.root = tk.Tk()
        self.root.title("EMA Control Hub")
        self.connection_manager = conn_manager
        self.qr_display = QRCodeDisplay(self.root)

        self.is_bci_enabled = tk.BooleanVar(value=False)
        self.is_testmode_enabled = tk.BooleanVar(value=True)

        self.last_notification_time = None

        self.triggered_count = 0
        self.responded_count = 0
        self.completed_count = 0
        self.ignored_count = 0

        """
        # Create and configure the input field and label
        label = tk.Label(self.root, text="Enter Subject ID:")
        label.pack()

        self.entry = tk.Entry(self.root, width=50)
        self.entry.pack()

        # Bind the Enter key to the send_message function
        self.entry.bind('<Return>', lambda event: self.send_message())
        """

        # show last notification time
        self.last_start_label = tk.Label(self.root, text="Session Start: N/A")
        self.last_start_label.pack(pady=10)

        # show next notification time
        self.next_start_label = tk.Label(self.root, text="Next Notification: N/A")
        self.next_start_label.pack(pady=10)

        # game counter ui
        counter_frame = tk.Frame(self.root)
        counter_frame.pack(pady=10)

        self.triggered_label = tk.Label(counter_frame, text="Triggered: 0")
        self.triggered_label.grid(row=0, column=0, padx=10)

        self.responded_label = tk.Label(counter_frame, text="Responded: 0")
        self.responded_label.grid(row=0, column=1, padx=10)

        self.completed_label = tk.Label(counter_frame, text="Completed: 0")
        self.completed_label.grid(row=0, column=2, padx=10)

        self.ignored_label = tk.Label(counter_frame, text="Ignored: 0")
        self.ignored_label.grid(row=0, column=3, padx=10)

        # Load today's counter values from file
        date_str = datetime.now().strftime("%Y-%m-%d")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        report_log_dir = os.path.join(project_root, "logs", "email_report")
        os.makedirs(report_log_dir, exist_ok=True)
        file_path = os.path.join(report_log_dir, f"{date_str}.unsent.txt")

        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write("Triggered: 0, Responded: 0, Completed: 0, Ignored: 0")

        try:
            with open(file_path, "r") as f:
                content = f.read()
                for part in content.split(","):
                    key, val = part.strip().split(":")
                    count = int(val.strip())
                    if "Triggered" in key:
                        self.triggered_count = count
                    elif "Responded" in key:
                        self.responded_count = count
                    elif "Completed" in key:
                        self.completed_count = count
                    elif "Ignored" in key:
                        self.ignored_count = count
        except Exception as e:
            print(f"Failed to load counters from file: {e}")

        self.triggered_label.config(text=f"Triggered: {self.triggered_count}")
        self.responded_label.config(text=f"Responded: {self.responded_count}")
        self.completed_label.config(text=f"Completed: {self.completed_count}")
        self.ignored_label.config(text=f"Ignored: {self.ignored_count}")

        # button for "START" signal
        start_button = tk.Button(self.root, text="Start EMA Sequence", command=self.send_start_signal)
        start_button.pack(padx=5)

        # button for "CANCEL" signal
        cancel_button = tk.Button(self.root, text="Skip Current EMA", command=self.send_skip_signal)
        cancel_button.pack(padx=5)

        # Create a label for battery level
        self.battery_level_label = tk.Label(self.root, text="Battery Status: N/A")
        self.battery_level_label.pack(pady=10)

         # button for "Check battery" signal
        checkBattery_button = tk.Button(self.root, text="Check Battery", command=self.check_battery_status)
        checkBattery_button.pack(pady=10)

        # Create a frame for the BCI toggle and label
        bci_frame = tk.Frame(self.root)
        bci_frame.pack(pady=10)

        # Create a toggle for BCI Connection
        bci_toggle = tk.Checkbutton(bci_frame, text="Enable BCI2000", variable=self.is_bci_enabled)
        bci_toggle.pack(side=tk.LEFT)

        # Create a toggle for Test Mode
        test_toggle = tk.Checkbutton(bci_frame, text="Test Mode", variable=self.is_testmode_enabled)
        test_toggle.pack(side=tk.LEFT)

        # Buttons for photodiode flicker test
        photodiode_frame = tk.Frame(self.root)
        photodiode_frame.pack(pady=10)

        flicker_start_button = tk.Button(photodiode_frame, text="Start Photodiode Test", command=self.start_photodiode_test)
        flicker_start_button.pack(side=tk.LEFT, padx=5)

        flicker_stop_button = tk.Button(photodiode_frame, text="Stop Photodiode Test", command=self.stop_photodiode_test)
        flicker_stop_button.pack(side=tk.LEFT, padx=5)

        self.center_window()

        # Set up the Tkinter close event to stop the server
        self.root.protocol("WM_DELETE_WINDOW", self.stop_server)

    def set_connection_manager(self, conn_manager):
        """Sets the connection manager to interact with."""
        self.connection_manager = conn_manager

    def send_message(self):
        message = self.entry.get()
        if message and self.connection_manager:
            self.connection_manager.send_message(message)
            self.entry.delete(0, tk.END)

    def send_start_signal(self):
        if self.connection_manager:
            current_time = datetime.now()
            self.last_start_label.config(text=f"Session Start: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

            next_schedule_time = self.connection_manager.scheduler.schedule_start()
            self.update_next_notification_time(next_schedule_time)

    def send_skip_signal(self):
        if self.connection_manager:
            self.connection_manager.send_skip_signal()
            self.increment_ignored()

    def update_last_notification_time(self, current_time):
        self.last_start_label.config(text=f"Last Notification: {current_time}")

    def check_battery_status(self):
        if self.connection_manager:
            battery_level = self.connection_manager.check_battery()
            self.battery_level_label.config(text=f"Battery Level: {battery_level}%")

    def update_next_notification_time(self, next_time):
        if isinstance(next_time, datetime):
            if self.last_notification_time:
                self.last_start_label.config(text=f"Last Notification: {self.last_notification_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.next_start_label.config(text=f"Next Notification: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            self.next_start_label.config(text="Next Notification: N/A")
    
    def increment_triggered(self):
        self.triggered_count += 1
        self.triggered_label.config(text=f"Triggered: {self.triggered_count}")
        self.update_report_counter()

    def increment_responded(self):
        self.responded_count += 1
        self.responded_label.config(text=f"Responded: {self.responded_count}")
        self.update_report_counter()

    def increment_completed(self):
        self.completed_count += 1
        self.completed_label.config(text=f"Completed: {self.completed_count}")
        self.update_report_counter()

    def increment_ignored(self):
        self.ignored_count += 1
        self.ignored_label.config(text=f"Ignored: {self.ignored_count}")
        self.update_report_counter()

    def update_report_counter(self):
        date_str = datetime.now().strftime("%Y-%m-%d")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        report_log_dir = os.path.join(project_root, "logs", "email_report")
        os.makedirs(report_log_dir, exist_ok=True)

        file_path = os.path.join(report_log_dir, f"{date_str}.unsent.txt")

        content = f"Triggered: {self.triggered_count}, Responded: {self.responded_count}, Completed: {self.completed_count}, Ignored: {self.ignored_count}"
        with open(file_path, "w") as f:
            f.write(content)


    def update_qr_code(self):
        """Call QR update method from outside."""
        if self.qr_display:
            self.qr_display.update_qr()

    def stop_server(self):
        if self.connection_manager:
            self.connection_manager.stop_server()
        self.root.quit()

    def start(self):
        self.root.mainloop()

    def center_window(self, width=450, height=400):
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = (screen_width - width) // 4
        y = (screen_height - height) // 4
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def start_photodiode_test(self):
        if self.connection_manager:
            self.connection_manager.start_photodiode_flicker_test()

    def stop_photodiode_test(self):
        if self.connection_manager:
            self.connection_manager.stop_photodiode_flicker_test()

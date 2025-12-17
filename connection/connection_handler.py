import socket
import threading
import select
import time
import os
from datetime import datetime, time as dt_time
from utils.scheduler.scheduler import Scheduler
from utils.audio.audio_alert import AudioAlert
#from utils.bci2000.bci2000_handler import BCI2000Handler

class ConnectionManager:

    def __init__(self, ui_instance, update_ui_callback, reporter_instance):
        self.server_running = True
        self.connection = None
        self.address = None
        self.ui = ui_instance
        self.update_ui_callback = update_ui_callback

        # Initialize Scheduler
        self.scheduler = Scheduler(self, update_ui_callback)

        # Initialize AudioAlert
        self.audio_alert = AudioAlert(alert_interval=120, skip_callback=self.send_skip_signal, ui_instance= self.ui, log_timestamped=self.log_timestamped)

        # Set up the Python server
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's Algorithm
        self.server.bind(('localhost', 4100))
        #self.server.bind(('192.168.1.152', 4100))
        #self.server.bind(('192.168.0.101', 4100))
        #self.server.bind(('192.168.0.103', 4100))
        #self.server.bind(('192.168.1.164', 4100))
        #self.server.bind(('192.168.10.20', 4100))
        self.server.listen(1)

        # Get script path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        log_base_dir = os.path.join(project_root, "logs")
        server_log_dir = os.path.join(log_base_dir, "server_log")
        self.ema_log_dir = os.path.join(log_base_dir, "ema_log")
        self.latency_log_dir = os.path.join(log_base_dir, "latency_log")

        # Ensure all log directories exist
        for directory in [log_base_dir, server_log_dir, self.ema_log_dir, self.latency_log_dir]:
            os.makedirs(directory, exist_ok=True)

        # Generate unique log file names
        self.server_log_file = os.path.join(server_log_dir, f"server_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        self.ema_log_file = None
        self.latency_log_file = None

        # Define the Nighttime period
        self.night_start = datetime.strptime("21:30", "%H:%M").time()   # 9:30 pm
        self.night_end = datetime.strptime("08:30", "%H:%M").time()     # 8:30 am

        # Start a background thread to accept connections
        self.connection_thread = threading.Thread(target=self.accept_connections, daemon=True)
        self.connection_thread.start()

        # Live check thread
        self.live_check_running = False
        self.live_check_interval = 3
        self.liveCheckIdCounter = 0
        self.liveCheckIdLimit = 1000
        self.last_live_check_id = None 
        self.last_live_check_time = None  # Store timestamp for latency check
        self.last_live_check_ack_time = time.time()   # Track the lastest LIVE_CHECK_ACK received time
        self.live_check_thread = None #threading.Thread(target=self.live_check_loop, daemon=True)

        # Battery check thread
        self.battery_check_interval = 1800  # 30 minutes in seconds
        self.battery_check_thread = threading.Thread(target=self.battery_check_loop, daemon=True)
        self.battery_check_thread.start()

        # Message buffer for incoming data from EMA
        self.buffer = ""

        # Experiment Reporter
        self.reporter = reporter_instance

        # Photodiode flicker test running flag
        self.photodiode_test_running = False

        # BCI2000 component
        #self.bci_handler = BCI2000Handler(self.log_bci_timestamped, self.reporter.send_email)

        # Start BCI2000 connection check thread
        self.bci_check_interval = 1800  # 30 mins
        self.bci_check_thread = threading.Thread(target=self.bci_check_loop, daemon=True)
        self.bci_check_thread.start()

    # accept new connections and handle disconnections
    def accept_connections(self):
        # TODO: handle reconnect on server side
    
        try:
            while self.server_running:
                readable, _, _ = select.select([self.server], [], [], 0.1)
                if self.server in readable:
                    if self.connection is None:
                        self.log_timestamped("Waiting for a new client to connect...")
                        self.connection, self.address = self.server.accept()
                        self.log_timestamped(f"Connected to {self.address}")
                        #self.connection.sendall("Server Initiated".encode('utf-8'))
                        #self.log_timestamped("Sent INIT message to Unity client")
                        
                        self.last_live_check_ack_time = time.time()

                        # Start live check once a connection is established
                        #if self.live_check_thread is None or not self.live_check_thread.is_alive():
                        ##    time.sleep(1)
                        #    self.live_check_running = True
                        #    self.live_check_thread = threading.Thread(target=self.live_check_loop, daemon=True)
                        #    self.live_check_thread.start()
                        
                        # First battery check on connection
                        #self.check_battery()
                    else:
                        try:
                            data = self.connection.recv(1024)
                            if not data:
                                self.handle_disconnection()
                        except (ConnectionResetError, BrokenPipeError):
                            self.handle_disconnection()
                if self.connection:
                    try:
                        data = self.connection.recv(4096).decode('utf-8')
                        if data:
                            self.process_received_message(data)
                        else:
                            self.handle_disconnection()
                    except (ConnectionResetError, BrokenPipeError):
                        self.handle_disconnection()
                else:
                    continue
        except OSError:
            self.log_timestamped("Server socket closed on OSError.")
            time.sleep(1)
            self.log_timestamped("Server waiting for new connection")

    # send messages to unity
    def send_message(self, message):
        if self.connection:
            self.connection.sendall(message.encode('utf-8'))
            self.log_timestamped(f"Sent message to iPad: {message}")
        else:
            self.log_timestamped("No client connected!")

    def send_start_signal(self):
        self.ui.update_qr_code()

        if self.connection:
            # Get log file name from BCI2000
            if self.ui.is_bci_enabled.get():
                bciSubject = self.bci_handler.get_bci_subjectName() + self.bci_handler.get_bci_subjectID()
                self.ema_log_file = os.path.join(self.ema_log_dir, f"{bciSubject}_EMA_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

                with open(self.ema_log_file, "w") as log_file:
                    log_file.write(f"New EMA session log started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            else:
                self.ema_log_file = os.path.join(self.ema_log_dir, f"EMA_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

            # Send the appropriate signal based on the mode
            if self.ui.is_testmode_enabled.get():
                self.connection.sendall("EMA_START_Test".encode('utf-8'))
                self.log_timestamped(f"Initiated an EMA session [Test]")
            else:
                self.connection.sendall("EMA_START_Live".encode('utf-8'))
                self.log_timestamped(f"Initiated an EMA session [Live]")
            
            self.ui.increment_triggered();
            self.audio_alert.play_audio()
            self.log_timestamped(f"Audio alert - Start")
            
        else:
            self.log_timestamped("EMA Start Error: No client connected!")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.reporter.send_email(
                subject="EMA Start Failed - No Client Connected",
                body=f"The server attempted to trigger a EMA session, but no iPad client was connected at {timestamp}"
            )
        
        self.scheduler.schedule_start()
        #next_schedule_time = 
        #self.log_timestamped(f"Next EMA session scheduled at: {next_schedule_time}")

    def send_skip_signal(self):
        if self.connection:
            self.audio_alert.stop_audio()
            self.log_timestamped(f"Audio alert - Stop")
            self.connection.sendall("EMA_SKIP".encode('utf-8'))
            self.log_timestamped("EMA session comfirmed or cancelled")
        else:
            self.log_timestamped("No client connected!")

    def process_received_message(self, message):
        self.buffer += message
        while "\n" in self.buffer:  # Split at newlines
            message_line, self.buffer = self.buffer.split("\n", 1)
            message_line = message_line.strip()  # Remove any leading/trailing spaces or newlines

            if message_line == "CLIENT_READY":
                self.log_timestamped("iPad ready for the study")
                if self.live_check_thread is None or not self.live_check_thread.is_alive():
                    self.live_check_running = True
                    self.live_check_thread = threading.Thread(target=self.live_check_loop, daemon=True)
                    self.live_check_thread.start()
            elif message_line == "EMA_Session_ACK":
                self.audio_alert.stop_audio()
                self.log_timestamped(f"Stop audio alert")
                self.log_timestamped(f"EMA_ACK: First 3 questions completed.")
                self.ui.increment_responded()
            elif message_line == "Session_Complete":
                self.log_timestamped(f"Current session completed.")
                self.ui.increment_completed()
            elif message_line.startswith("BATTERY"):
                message_parts = message_line.split(":")
                if len(message_parts) >= 3:
                    battery_level = float(message_parts[1].strip())
                    battery_status = message_parts[2].strip()
                    self.log_timestamped(f"Battery Level: {int(battery_level*100)}, Status: {battery_status}")
                    if self.ui:
                        self.ui.battery_level_label.config(text=f"Battery: {int(battery_level*100)}% ({battery_status})")
            elif message_line.startswith("LIVE_CHECK_ACK"):
                # Extract the live check ID from the response
                message_parts = message_line.split(":")
                if len(message_parts) > 1:
                    ack_id = message_parts[1].replace("LIVE_CHECK", "").strip()
                    # Check if the ACK matches the last sent ID
                    if ack_id == self.last_live_check_id:
                        latency_ms = None
                        if len(message_parts) >= 4 and message_parts[2] == "LATENCY":
                            try:
                                latency_ms = float(message_parts[3].strip())
                            except ValueError:
                                pass
                            #time.sleep(0.1)
                            self.log_timestamped(f"Received LIVE_CHECK_ACK:{ack_id} - Latency: {latency_ms:.3f} ms")
                        self.last_live_check_ack_time = time.time()
                    else:
                        #time.sleep(0.1)
                        self.log_timestamped(f"Received LIVE_CHECK_ACK with unexpected ID: {ack_id}")
                else:
                    self.log_timestamped(f"Invalid LIVE_CHECK_ACK received")
            elif message_line.startswith("BCI_Sync:"):
                if self.ui.is_bci_enabled.get():
                    #self.bci_handler.process_bci_data(message_line)
                    #self.log_timestamped(f"Forwarded BCI_Sync message: {message}")
                #else:
                    self.log_timestamped(f"BCI data received but ignored (BCI disabled): {message}")
            else:
                self.log_ema_message(message_line)

    # Periodically sends a live check signal
    def live_check_loop(self):
        clock_time = datetime.now().time()

        # If during nighttime, change live_check_interval to 15 mins
        # Else use 3 secs
        #if self.night_start <= clock_time or clock_time <= self.night_end:
        #    self.live_check_interval = 900
        #    timeout_threshold = 1400
        #else:
            #self.live_check_interval = 3
        timeout_threshold = 100

        if self.server_running and self.live_check_running and self.connection:
            current_time = time.time()

            # Check if the last LIVE_CHECK_ACK was received within the timeout threshold
            if (current_time - self.last_live_check_ack_time) > timeout_threshold:
                self.log_timestamped("No LIVE_CHECK_ACK received in time, assuming iPad disconnected.")
                self.handle_disconnection()
                return  # Stop sending live checks
            
            # Generate a unique ID for the live check
            self.last_live_check_id = str(self.liveCheckIdCounter)
            current_timestamp_ms = int(time.time() * 1000)
            live_check_message = f"LIVE_CHECK:{self.last_live_check_id}:{current_timestamp_ms}"

            try:
                self.last_live_check_time = time.time()
                self.connection.sendall(live_check_message.encode('utf-8'))
                #time.sleep(0.1)
                self.log_timestamped(f"Sent LIVE_CHECK to iPad:{self.last_live_check_id}")

                # Increment the counter and reset it if needed
                self.liveCheckIdCounter = (self.liveCheckIdCounter + 1) % self.liveCheckIdLimit
            except Exception as e:
                self.log_timestamped(f"Error sending live check: {e}")
                
            threading.Timer(self.live_check_interval, self.live_check_loop).start()

    def check_battery(self):
        if self.connection:
            self.connection.sendall("BATTERY".encode('utf-8'))
            self.log_timestamped("Checking iPad Battery Status")
        else:
            self.log_timestamped("Battery Check Error: No client connected!")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.reporter.send_email(
                subject="Battery Check Failed - No Client Connected",
                body=f"The server attempted to check the battery level of the iPad, but no iPad client was connected at {timestamp}"
            )

    def battery_check_loop(self):
        while self.server_running:
            time.sleep(self.battery_check_interval)
            if self.connection:
                self.check_battery()
            else:
                self.log_timestamped("Battery check skipped: No client connected.")

    def bci_check_loop(self):
        while self.server_running:
            now = datetime.now().time()
            start = dt_time(9, 0)   # 9:00 AM
            end = dt_time(21, 0)    # 9:00 PM

            if start <= now <= end and self.ui.is_bci_enabled.get():
                try:
                    name = self.bci_handler.get_bci_subjectName()
                    self.log_bci_timestamped(f"Periodic BCI2000 check: Subject ID: {name}")
                except Exception as e:
                    self.log_bci_timestamped(f"Error during BCI2000 check: {e}")

            time.sleep(self.bci_check_interval)

    # Handles client disconnection
    def handle_disconnection(self):
        """Handles client disconnection."""
        if self.connection:
            self.log_timestamped(f"Client {self.address} disconnected.")
            self.connection.close()
            self.connection = None
            self.live_check_running = False

    def get_next_start_time(self):
        return self.next_start_time

    def stop_server(self):
        self.server_running = False
        self.live_check_running = False
        if self.connection:
            self.connection.close()
            self.connection = None
        if self.server:
            self.server.close()
            self.server = None
        self.log_timestamped("Server stopped")

    # Log and save server messages with timestamp
    def log_timestamped(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + f".{datetime.now().microsecond // 1000:03d}"
        server_log_message = f"{timestamp} - {message}"
        print(server_log_message)
        with open(self.server_log_file, "a") as log_file:
            log_file.write(server_log_message + "\n")

    def log_bci_timestamped(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + f".{datetime.now().microsecond // 1000:03d}"
        server_log_message = f"{timestamp} - {message}"
        #print(server_log_message)
        with open(self.server_log_file, "a") as log_file:
            log_file.write(server_log_message + "\n")
    
    # Log and save EMA messages with timestamp
    def log_ema_message(self, message):
        if not self.ema_log_file:
            self.log_timestamped("Warning: Attempted to log EMA message before EMA session started.")
            return  
        with open(self.ema_log_file, "a") as log_file:
            log_file.write(message.strip() + "\n")

    # Photodiode Latency Test
    def start_photodiode_flicker_test(self):
        if not self.connection:
            self.log_timestamped("Photodiode test aborted: No client connected.")
            return

        # Generate latency log file name if not already set
        if not self.latency_log_file:
            self.latency_log_file = os.path.join(self.latency_log_dir, f"photodiode_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        self.log_timestamped("Starting photodiode flicker test: Freq 2Hz)...")

        flicker_interval = 1.0  # 0.5 Hz => 2s per cycle => 1s per on/off

        self.photodiode_test_running = True

        def flicker_loop():
            try:
                self.connection.sendall("FLASH_START\n".encode('utf-8'))
                self.log_latency_timestamped("Sent photodiode signal: FLASH_START")
            except Exception as e:
                self.log_latency_timestamped(f"Error sending FLASH_START: {e}")
                return

            state = False  # Start with off
            while self.photodiode_test_running and self.connection:
                state = not state
                signal = "FLASH_ON" if state else "FLASH_OFF"
                try:
                    self.connection.sendall(f"{signal}\n".encode('utf-8'))
                    color = "WHITE" if signal == "FLASH_ON" else "BLACK"
                    self.log_latency_timestamped(f"Sent photodiode signal: {signal} - Screen color: {color}")
                    # BCI event marking after logging the latency timestamp
                    if self.ui.is_bci_enabled.get():
                        if not self.bci_handler.bci.connected:
                            self.bci_handler.bci.Connect()
                            self.bci_handler.bci.connected = True
                        if signal == "FLASH_ON":
                            self.bci_handler.bci.SetEventVariable("EmaColor", 1)    # 1 for white
                        else:
                            self.bci_handler.bci.SetEventVariable("EmaColor", 2)    # 2 for black
                except Exception as e:
                    self.log_latency_timestamped(f"Error sending photodiode signal: {e}")
                    break
                time.sleep(flicker_interval)

            try:
                self.connection.sendall("FLASH_END\n".encode('utf-8'))
                self.log_latency_timestamped("Sent photodiode signal: FLASH_END")
            except Exception as e:
                self.log_latency_timestamped(f"Error sending FLASH_END: {e}")

            self.photodiode_test_running = False

        threading.Thread(target=flicker_loop, daemon=True).start()

    def stop_photodiode_flicker_test(self):
        self.photodiode_test_running = False
        if self.connection:
            try:
                self.connection.sendall("FLASH_END\n".encode('utf-8'))
                self.log_latency_timestamped("Sent photodiode signal: FLASH_END")
            except Exception as e:
                self.log_latency_timestamped(f"Error sending FLASH_END: {e}")
        else:
            self.log_latency_timestamped("No client connected!")


    def log_latency_timestamped(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + f".{datetime.now().microsecond // 1000:03d}"
        log_message = f"{timestamp} - {message}"
        print(log_message)
        with open(self.latency_log_file, "a") as log_file:
            log_file.write(log_message + "\n")
import os
import time
import threading
from datetime import datetime

class AudioAlert:
    def __init__(self, alert_interval = 120, skip_callback = None, ui_instance = None, log_timestamped = None):
        self.audio_file = "audio_alert.wav"
        self._alert_interval = alert_interval
        self.end_playing = False
        self.play_thread = None
        self.skip_callback = skip_callback
        self.ui = ui_instance
        self.log_timestamped = log_timestamped
    
    def play_audio(self):
        """Start playing audio in a separate thread."""
        if self.play_thread and self.play_thread.is_alive():
            return  # Prevent multiple instances

        self.end_playing = False
        self.play_thread = threading.Thread(target=self._play_audio_loop, daemon=True)
        self.play_thread.start()

    def _play_audio_loop(self):
        """Plays audio in a loop until stopped."""
        start_time = time.time()
        self.log_timestamped("Audio started")

        while not self.end_playing and (time.time() - start_time) < self._alert_interval:
            #os.system(f'afplay {self.audio_file}')  # MacOS
            # os.system(f'start {self.audio_file}')  # Windows
            time.sleep(0.5)  # Avoid tight loop

        if not self.end_playing:
            self.ui.increment_ignored()
        self.log_timestamped("Audio stopped")
        
        if self.skip_callback:
            self.skip_callback()

        self.end_playing = True

    def stop_audio(self):
        """Stop the audio playback."""
        self.end_playing = True
        self.play_thread = None


    """
    def play_audio(self):
        self.end_playing = False  # Reset each time audio starts
        start_time = time.time()
        self.log_timestamped("Audio played")
        while not self.end_playing and (time.time() - start_time) < self.alert_interval:
            # os.system(f'start {self.audio_file}')  # Windows
            # os.system(f'afplay {self.audio_file}')  # MacOS
            time.sleep(0.5)
        self.log_timestamped("Audio stopped")
    
    def stop_audio(self):
        self.log_timestamped("Audio stopped")
        self.end_playing = True
    
    
    @staticmethod
    def log_timestamped(message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} - [AudioAlert] {message}")

    """
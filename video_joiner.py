import os
import subprocess
import time
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal

class VideoJoinerThread(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, video_manager, target_duration_min, no_audio, output_file):
        super().__init__()
        self.video_manager = video_manager
        self.target_duration_min = target_duration_min
        self.no_audio = no_audio
        self.output_file = output_file
        self.is_running = True

    def run(self):
        temp_list_file = None
        try:
            self.log_signal.emit("Starting random video selection...")
            selected_videos = []
            current_duration = 0
            target_duration_sec = self.target_duration_min * 60
            
            # Select videos randomly
            while True:
                if not self.is_running:
                    break
                
                # If target duration is set and reached, stop
                if target_duration_sec > 0 and current_duration >= target_duration_sec:
                    self.log_signal.emit(f"Target duration reached: {current_duration/60:.2f} min")
                    break
                
                if target_duration_sec == 0 and not self.video_manager.unused_videos:
                     self.log_signal.emit("All videos in current cycle selected.")
                     break

                video = self.video_manager.get_next_video()
                if video:
                    # Use cached duration from manager
                    duration = self.video_manager.get_duration(video)
                    
                    if duration <= 0:
                        self.log_signal.emit(f"Skipping invalid video (duration=0): {os.path.basename(video)}")
                        continue
                        
                    selected_videos.append(video)
                    current_duration += duration
                    self.log_signal.emit(f"Selected: {os.path.basename(video)} ({duration:.2f}s) - Total: {current_duration/60:.2f} min")
                else:
                    self.log_signal.emit("No more videos available.")
                    break
            
            if not selected_videos:
                self.finished_signal.emit(False, "No videos selected.")
                return

            self.log_signal.emit(f"Prepared {len(selected_videos)} videos for joining.")
            
            # Create temp file for ffmpeg list
            fd, temp_list_file = tempfile.mkstemp(suffix=".txt", text=True)
            # Close the low-level fd immediately, we will open with python context manager or just write to it using the fd
            # Actually os.fdopen is good.
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                for video in selected_videos:
                    escaped_path = video.replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")
            
            self.run_simple_concat(temp_list_file)

        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False, str(e))
        finally:
            if temp_list_file and os.path.exists(temp_list_file):
                try:
                    os.remove(temp_list_file)
                except:
                    pass

    def stop(self):
        self.is_running = False

    def run_simple_concat(self, temp_list_file):
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', temp_list_file,
        ]
        
        if self.no_audio:
            cmd.append('-an')
        
        cmd.extend(['-c', 'copy', '-y', self.output_file])
        
        self.execute_ffmpeg(cmd)

    def execute_ffmpeg(self, cmd):
        self.log_signal.emit(f"Running FFmpeg...")
        print(f"Executing: {' '.join(cmd)}")
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='replace'
        )
        
        # Read stderr character by character to handle \r
        buffer = ""
        while True:
            char = process.stderr.read(1)
            if not char and process.poll() is not None:
                break
            
            if char:
                buffer += char
                if char in ['\n', '\r']:
                    line = buffer.strip()
                    if line:
                        print(f"FFmpeg: {line}") # Print to console for debugging
                        if "time=" in line or "Error" in line or "error" in line:
                             self.log_signal.emit(f"FFmpeg: {line}")
                    buffer = ""
            else:
                # No char available yet, wait a bit to avoid busy loop
                # But read(1) is blocking by default unless we use non-blocking IO.
                # In standard python subprocess with pipes, read(1) blocks.
                # So we won't hit this 'else' unless EOF (which is handled by 'if not char').
                pass
            
            if not self.is_running:
                process.terminate()
                break
            
        if process.returncode == 0:
            self.log_signal.emit("Joining complete!")
            self.finished_signal.emit(True, "Success")
        else:
            self.log_signal.emit(f"FFmpeg process finished with code {process.returncode}")
            self.finished_signal.emit(False, f"FFmpeg failed with code {process.returncode}")

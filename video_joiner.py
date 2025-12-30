import os
import subprocess
import time
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal

class VideoJoinerThread(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, video_manager, target_duration_sec, no_audio, output_folder, video_count):
        super().__init__()
        self.video_manager = video_manager
        self.target_duration_sec = target_duration_sec
        self.no_audio = no_audio
        self.output_folder = output_folder
        self.video_count = video_count
        self.is_running = True

    def run(self):
        try:
            successful_count = 0
            
            for i in range(self.video_count):
                if not self.is_running:
                    self.log_signal.emit("Process cancelled by user.")
                    break
                
                self.log_signal.emit(f"\\n=== Generating video {i+1}/{self.video_count} ===")
                
                # Generate output filename
                timestamp = int(time.time())
                output_file = os.path.join(self.output_folder, f"output_{timestamp}_{i+1}.mp4")
                
                # Generate single video
                success = self.generate_single_video(output_file)
                
                if success:
                    successful_count += 1
                    self.progress_signal.emit(i + 1)
                    self.log_signal.emit(f"✓ Video {i+1} completed: {os.path.basename(output_file)}")
                else:
                    self.log_signal.emit(f"✗ Video {i+1} failed")
                    if not self.is_running:
                        break
                
                # Small delay between videos
                if i < self.video_count - 1:
                    time.sleep(0.5)
            
            if successful_count == self.video_count:
                self.finished_signal.emit(True, str(successful_count))
            elif successful_count > 0:
                self.finished_signal.emit(True, f"{successful_count}/{self.video_count}")
            else:
                self.finished_signal.emit(False, "No videos were generated successfully")
                
        except Exception as e:
            self.log_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(False, str(e))

    def generate_single_video(self, output_file):
        temp_list_file = None
        try:
            selected_videos = []
            current_duration = 0
            
            # Select videos randomly
            while True:
                if not self.is_running:
                    return False
                
                # If target duration is set and reached, stop
                if self.target_duration_sec > 0 and current_duration >= self.target_duration_sec:
                    self.log_signal.emit(f"Target duration reached: {current_duration:.2f}s")
                    break
                
                if self.target_duration_sec == 0 and not self.video_manager.unused_videos:
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
                    self.log_signal.emit(f"Selected: {os.path.basename(video)} ({duration:.2f}s) - Total: {current_duration:.2f}s")
                else:
                    self.log_signal.emit("No more videos available.")
                    break
            
            if not selected_videos:
                self.log_signal.emit("No videos selected for this output.")
                return False

            self.log_signal.emit(f"Prepared {len(selected_videos)} videos for joining.")
            # Create temp file for ffmpeg list
            # Use output_folder for temp file to avoid permission issues with FFmpeg on Windows
            fd, temp_list_file = tempfile.mkstemp(suffix=".txt", prefix="ffmpeg_list_", dir=self.output_folder, text=True)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                for video in selected_videos:
                    # FFmpeg concat requires forward slashes on Windows and proper escaping
                    # Replace backslash with forward slash
                    normalized_path = video.replace(os.sep, '/')
                    # Escape single quotes
                    escaped_path = normalized_path.replace("'", "'\\\\''") 
                    f.write(f"file '{escaped_path}'\n")
            
            # Use forward slashes for the list file path itself too, just in case
            temp_list_file = temp_list_file.replace(os.sep, '/')
            return self.run_simple_concat(temp_list_file, output_file)

        except Exception as e:
            self.log_signal.emit(f"Error in generate_single_video: {str(e)}")
            return False
        finally:
            if temp_list_file and os.path.exists(temp_list_file):
                try:
                    os.remove(temp_list_file)
                except:
                    pass

    def stop(self):
        self.is_running = False

    def run_simple_concat(self, temp_list_file, output_file):
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', temp_list_file,
        ]
        
        # Fast codec copy (works well with same-format videos)
        if self.no_audio:
            cmd.append('-an')
        cmd.extend(['-c', 'copy'])
        
        # Fix timestamp issues
        cmd.extend([
            '-fflags', '+genpts',           # Generate presentation timestamps
            '-avoid_negative_ts', 'make_zero',  # Fix negative timestamps
        ])
        
        cmd.extend(['-y', output_file])
        
        return self.execute_ffmpeg(cmd)

    def execute_ffmpeg(self, cmd):
        self.log_signal.emit(f"Running FFmpeg...")
        
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Execute FFmpeg command
        return self._try_ffmpeg(cmd, startupinfo)
    
    def _try_ffmpeg(self, cmd, startupinfo):
        """Try to execute FFmpeg command and return success status"""
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='replace'
        )
        
        # Read stderr to monitor progress
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                line = line.strip()
                if "time=" in line or "Error" in line or "error" in line:
                    self.log_signal.emit(f"FFmpeg: {line}")
            
            if not self.is_running:
                process.terminate()
                return False
        
        return process.returncode == 0

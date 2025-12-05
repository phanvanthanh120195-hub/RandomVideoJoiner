import os
import random
import subprocess
import concurrent.futures

class VideoManager:
    def __init__(self):
        self.all_videos = []
        self.unused_videos = []
        self.used_videos = []
        self.durations = {} # Cache for video durations

    def load_videos(self, folder_path):
        self.all_videos = []
        self.unused_videos = []
        self.used_videos = []
        self.durations = {}
        
        try:
            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.mp4')]
            self.all_videos = files
            
            # Pre-fetch durations in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # We map the get_duration function to all files
                # We don't strictly need the results right now, but this populates the cache
                list(executor.map(self.get_duration, self.all_videos))

            # Initial shuffle
            self.reset_cycle()
            return len(self.all_videos)
        except Exception as e:
            print(f"Error loading videos: {e}")
            return 0

    def reset_cycle(self):
        self.unused_videos = list(self.all_videos)
        random.shuffle(self.unused_videos)
        self.used_videos = []

    def get_next_video(self):
        if not self.all_videos:
            return None
        
        if not self.unused_videos:
            self.reset_cycle()
            
        if self.unused_videos:
            video = self.unused_videos.pop()
            self.used_videos.append(video)
            return video
        return None
        
    def get_duration(self, file_path):
        if file_path in self.durations:
            return self.durations[file_path]
            
        try:
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-show_entries', 'format=duration', 
                '-of', 'default=noprint_wrappers=1:nokey=1', 
                file_path
            ]
            # Add timeout to prevent hanging
            # Use creationflags=subprocess.CREATE_NO_WINDOW on Windows to avoid popping up consoles if not already handled
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                timeout=5,
                startupinfo=startupinfo
            )
            duration = float(result.stdout.strip())
            self.durations[file_path] = duration
            return duration
        except Exception as e:
            # print(f"Error getting duration for {os.path.basename(file_path)}: {e}")
            return 0

import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QCheckBox, 
                             QProgressBar, QTextEdit, QMessageBox, QSpinBox)
from video_manager import VideoManager
from video_joiner import VideoJoinerThread

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Random Video Joiner (Optimized)")
        self.setGeometry(100, 100, 600, 500)
        
        self.video_manager = VideoManager()
        self.folder_path = ""
        self.output_folder_path = ""
        
        self.init_ui()
        
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Folder Selection
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Input Folder")
        self.btn_select_folder = QPushButton("Select Input Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.btn_select_folder)
        folder_layout.addWidget(self.folder_label)
        layout.addLayout(folder_layout)
        
        # Output Folder Selection
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Folder")
        self.btn_select_output = QPushButton("Select Output Folder")
        self.btn_select_output.clicked.connect(self.select_output_folder)
        output_layout.addWidget(self.btn_select_output)
        output_layout.addWidget(self.output_label)
        layout.addLayout(output_layout)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.chk_no_audio = QCheckBox("Xuất video không có âm thanh (Mute)")
        controls_layout.addWidget(self.chk_no_audio)
        
        # Target Duration Input
        self.spin_duration = QSpinBox()
        self.spin_duration.setRange(0, 9999) # 0 means unlimited (join all)
        self.spin_duration.setValue(0)
        self.spin_duration.setSuffix(" s")
        self.spin_duration.setToolTip("Set 0 to join all available videos")
        controls_layout.addWidget(QLabel("Target Duration:"))
        controls_layout.addWidget(self.spin_duration)
        
        # Number of Videos to Export
        self.spin_video_count = QSpinBox()
        self.spin_video_count.setRange(1, 100)
        self.spin_video_count.setValue(1)
        self.spin_video_count.setSuffix(" video(s)")
        self.spin_video_count.setToolTip("Number of videos to export")
        controls_layout.addWidget(QLabel("Number of Videos:"))
        controls_layout.addWidget(self.spin_video_count)
        
        layout.addLayout(controls_layout)
        
        self.btn_join = QPushButton("Render Videos")
        self.btn_join.clicked.connect(self.start_joining)
        layout.addWidget(self.btn_join)
        
        self.btn_cancel = QPushButton("Cancel / Stop")
        self.btn_cancel.clicked.connect(self.cancel_joining)
        self.btn_cancel.setEnabled(False)
        layout.addWidget(self.btn_cancel)
        
        # Progress and Log
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder")
        if folder:
            self.folder_path = folder
            self.folder_label.setText(folder)
            self.log(f"Loading videos from {folder}...")
            # Use QApplication.processEvents() to show the log immediately if needed, 
            # but since load_videos is blocking (though parallelized), UI might freeze briefly.
            # For 1000s of videos, parallelization helps significantly.
            count = self.video_manager.load_videos(folder)
            
            self.log(f"Loaded {count} videos.")
            self.btn_join.setEnabled(count > 0)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder_path = folder
            self.output_label.setText(f"Output: {folder}")
        else:
            self.output_folder_path = ""
            self.output_label.setText("Output Folder: Same as Source")

    def log(self, message):
        self.log_text.append(message)
        # Scroll to bottom
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_joining(self):
        if not self.folder_path:
            return
            
        # Check if we have unused videos.
        if not self.video_manager.unused_videos:
            self.video_manager.reset_cycle()
            
        target_duration_sec = self.spin_duration.value()
        no_audio = self.chk_no_audio.isChecked()
        video_count = self.spin_video_count.value()
        
        # Determine output folder
        base_out_folder = self.output_folder_path if self.output_folder_path else self.folder_path
        if not base_out_folder:
            base_out_folder = self.folder_path
            
        # Create 'Output' subfolder
        out_folder = os.path.join(base_out_folder, "Output")
        if not os.path.exists(out_folder):
            try:
                os.makedirs(out_folder)
            except Exception as e:
                self.log(f"Error creating Output folder: {e}")
                out_folder = base_out_folder # Fallback
        
        self.btn_join.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setRange(0, video_count)
        self.progress_bar.setValue(0)
        
        self.thread = VideoJoinerThread(self.video_manager, target_duration_sec, no_audio, out_folder, video_count)
        self.thread.log_signal.connect(self.log)
        self.thread.progress_signal.connect(self.progress_bar.setValue)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()
        
    def cancel_joining(self):
        if hasattr(self, 'thread') and self.thread.isRunning():
            self.thread.stop()
            self.log("Stopping process... please wait.")
            self.btn_cancel.setEnabled(False)
            
    def on_finished(self, success, message):
        self.btn_join.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        if success:
            QMessageBox.information(self, "Thành công", f"Đã xuất thành công {message} video(s)!")
            self.log(f"Cycle Status: {len(self.video_manager.unused_videos)} unused, {len(self.video_manager.used_videos)} used.")
        else:
            if "terminated" in message or "stopped" in message.lower():
                 QMessageBox.warning(self, "Cancelled", "Process was cancelled by user.")
            else:
                 QMessageBox.critical(self, "Error", f"Failed: {message}")

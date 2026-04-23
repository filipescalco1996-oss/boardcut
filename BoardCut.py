import sys
import os
import json
import random
import logging
import subprocess
import urllib.request # Para verificar updates
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, 
    QLabel, QProgressBar, QMessageBox, QTextEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal, QObject

# --- CONFIGURAÇÕES GERAIS ---
VERSION = "0.0.1b"
APP_NAME = "BoardCut"
COMPANY = "MarReis Studios"
# URL onde você colocaria um arquivo .txt apenas com o número da versão (ex: 0.0.2)
UPDATE_URL = "https://seu-link-aqui.com/version.txt" 

class ProcessingSignals(QObject):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal()

class VideoProcessor:
    def __init__(self, config):
        self.config = config

    def validate_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except:
            return False

    def process_video(self, input_path, output_path, credits_path, mode):
        if "Horizontal" in mode:
            v_filter = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1'
        else:
            v_filter = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1'

        cmd = [
            'ffmpeg', '-y', '-i', str(input_path), '-i', str(credits_path),
            '-filter_complex',
            f'[0:v]{v_filter}[v0];[1:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v1];'
            f'[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a0];'
            f'[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1];'
            f'[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]',
            '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k', str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

class BoardCutApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(950, 700)
        
        # Garantir pastas
        for d in ["enviar_para_tiktok", "output", "thumbnails", "assets"]:
            Path(d).mkdir(exist_ok=True)

        self.load_config()
        self.processor = VideoProcessor(self.config)
        self.init_ui()
        self.refresh_video_list()
        
        # Checar update ao iniciar
        Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        """Verifica se existe uma nova versão online"""
        try:
            # Remova o comentário abaixo quando tiver uma URL real de versão
            # response = urllib.request.urlopen(UPDATE_URL, timeout=5)
            # online_version = response.read().decode('utf-8').strip()
            # if online_version > VERSION:
            #    self.log_message(f"📢 Nova versão disponível: {online_version}! Baixe no site oficial.")
            pass
        except:
            self.log_message("⚠️ Não foi possível verificar atualizações (sem conexão).")

    def load_config(self):
        path = Path("config.json")
        if not path.exists():
            self.config = {"hashtags": ["#fyp"], "schedule_times": ["10:00"], "post_credits": "assets/pos_creditos.mp4", "video_mode": "Horizontal (Bordas Pretas)"}
        else:
            with open(path, "r") as f: self.config = json.load(f)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header
        header = QLabel(f"🚀 {APP_NAME} - TikTok Preprocessor")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #3498db; margin-bottom: 10px;")
        layout.addWidget(header)

        # Formato e Botões
        top_layout = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Horizontal (Bordas Pretas)", "Vertical (Preencher Tela)"])
        top_layout.addWidget(QLabel("Ajuste:"))
        top_layout.addWidget(self.combo_mode)
        
        self.btn_start = QPushButton("Processar Vídeos")
        self.btn_start.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")
        top_layout.addWidget(self.btn_start)
        layout.addLayout(top_layout)

        # Lista e Logs
        self.video_list = QListWidget()
        layout.addWidget(self.video_list)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        layout.addWidget(self.log_display)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # --- RODAPÉ MARREIS STUDIOS ---
        footer_layout = QHBoxLayout()
        footer_text = f"{COMPANY} [ {VERSION} ]"
        self.lbl_footer = QLabel(footer_text)
        self.lbl_footer.setAlignment(Qt.AlignRight)
        self.lbl_footer.setStyleSheet("color: #7f8c8d; font-style: italic; padding-top: 5px;")
        footer_layout.addWidget(self.lbl_footer)
        layout.addLayout(footer_layout)

        self.btn_start.clicked.connect(self.start_processing)

    def log_message(self, message):
        self.log_display.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def refresh_video_list(self):
        self.video_list.clear()
        for file in Path("enviar_para_tiktok").iterdir():
            if file.suffix.lower() in ['.mp4', '.mov', '.avi']:
                self.video_list.addItem(f"📹 {file.name}")

    def start_processing(self):
        self.btn_start.setEnabled(False)
        Thread(target=self.run_tasks, daemon=True).start()

    def run_tasks(self):
        input_dir = Path("enviar_para_tiktok")
        videos = [f for f in input_dir.iterdir() if f.suffix.lower() in {'.mp4', '.mov', '.avi'}]
        
        for i, video_path in enumerate(videos):
            try:
                self.log_message(f"Processando: {video_path.name}")
                out = Path("output") / f"final_{video_path.stem}.mp4"
                self.processor.process_video(video_path, out, self.config['post_credits'], self.combo_mode.currentText())
                self.progress_bar.setValue(int(((i+1)/len(videos))*100))
            except Exception as e:
                self.log_message(f"❌ Erro: {e}")
        
        self.log_message("✨ Concluído!")
        self.btn_start.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BoardCutApp()
    window.show()
    sys.exit(app.exec())

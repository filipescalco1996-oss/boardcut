import sys
import os
import json
import random
import logging
import subprocess
import urllib.request # Módulo nativo para acessar a web
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QFileDialog, 
    QLabel, QProgressBar, QMessageBox, QTextEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer

# --- CONFIGURAÇÕES GERAIS ---
VERSION = "0.0.2b"
APP_NAME = "BoardCut"
COMPANY = "MarReis Studios"

# !!! COLE SEU LINK RAW AQUI ENTRE AS ASPAS !!!
UPDATE_URL = "SEU_LINK_RAW_AQUI" 

class ProcessingSignals(QObject):
    progress = Signal(int)
    log = Signal(str)
    update_found = Signal(str) # Sinal para avisar a UI sobre o update

class BoardCutApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {COMPANY}")
        self.resize(950, 700)
        
        # Garantir pastas de trabalho
        for d in ["enviar_para_tiktok", "output", "thumbnails", "assets"]:
            Path(d).mkdir(exist_ok=True)

        self.load_config()
        self.processor = VideoProcessor(self.config)
        self.signals = ProcessingSignals()
        
        self.init_ui()
        self.refresh_video_list()
        
        # Conectar sinal de update à função de aviso
        self.signals.update_found.connect(self.show_update_dialog)
        
        # Iniciar checagem de update 2 segundos após abrir (para não travar o início)
        QTimer.singleShot(2000, self.start_update_check)

    def start_update_check(self):
        """Inicia a verificação em uma thread separada"""
        Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        """Lógica de comparação de versão"""
        try:
            # Tenta ler o link RAW
            with urllib.request.urlopen(UPDATE_URL, timeout=10) as response:
                online_version = response.read().decode('utf-8').strip()
                
                # Se a versão online for diferente da local (estamos assumindo que será maior)
                if online_version != VERSION:
                    self.signals.update_found.emit(online_version)
                else:
                    logging.info("O BoardCut está atualizado.")
        except Exception as e:
            logging.warning(f"Falha ao checar update: {e}")

    def show_update_dialog(self, new_version):
        """Abre o popup avisando o usuário"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Atualização Disponível!")
        msg.setText(f"Uma nova versão do BoardCut foi encontrada!\n\n"
                    f"Versão Atual: {VERSION}\n"
                    f"Nova Versão: {new_version}")
        msg.setInformativeText("Deseja continuar usando a versão atual ou baixar a nova?")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        self.log_message(f"📢 Update disponível: {new_version}. Verifique com a MarReis Studios.")

    # --- RESTANTE DAS FUNÇÕES (IGUAIS ÀS ANTERIORES) ---
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

        # Layout de Título
        header = QLabel(f"🚀 {APP_NAME}")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #2ecc71;")
        layout.addWidget(header)

        # Formato e Botões
        top_layout = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Horizontal (Bordas Pretas)", "Vertical (Preencher Tela)"])
        top_layout.addWidget(QLabel("Modo de Vídeo:"))
        top_layout.addWidget(self.combo_mode)
        
        self.btn_start = QPushButton("🚀 Iniciar BoardCut")
        self.btn_start.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 10px;")
        top_layout.addWidget(self.btn_start)
        layout.addLayout(top_layout)

        self.video_list = QListWidget()
        layout.addWidget(self.video_list)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        layout.addWidget(self.log_display)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Rodapé MarReis Studios
        footer = QLabel(f"{COMPANY} [ {VERSION} ]")
        footer.setAlignment(Qt.AlignRight)
        footer.setStyleSheet("color: #95a5a6; font-size: 10px; margin-top: 5px;")
        layout.addWidget(footer)

        self.btn_start.clicked.connect(self.start_processing)

    def log_message(self, message):
        self.log_display.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def refresh_video_list(self):
        self.video_list.clear()
        input_dir = Path("enviar_para_tiktok")
        for file in input_dir.iterdir():
            if file.suffix.lower() in ['.mp4', '.mov', '.avi']:
                self.video_list.addItem(f"📹 {file.name}")

    def start_processing(self):
        self.btn_start.setEnabled(False)
        self.log_display.clear()
        Thread(target=self.run_tasks, daemon=True).start()

    def run_tasks(self):
        input_dir = Path("enviar_para_tiktok")
        videos = [f for f in input_dir.iterdir() if f.suffix.lower() in {'.mp4', '.mov', '.avi'}]
        
        for i, video_path in enumerate(videos):
            try:
                self.log_message(f"Trabalhando em: {video_path.name}")
                out = Path("output") / f"final_{video_path.stem}.mp4"
                self.processor.process_video(video_path, out, self.config['post_credits'], self.combo_mode.currentText())
                self.progress_bar.setValue(int(((i+1)/len(videos))*100))
            except Exception as e:
                self.log_message(f"❌ Erro: {e}")
        
        self.log_message("✨ Processo Finalizado!")
        self.btn_start.setEnabled(True)

class VideoProcessor:
    def __init__(self, config):
        self.config = config

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BoardCutApp()
    window.show()
    sys.exit(app.exec())

"""
Módulo para captura e processamento de códigos de barras
"""

import time
import cv2
import av
import streamlit as st
from streamlit_webrtc import VideoProcessorBase
from pyzbar import pyzbar
from config import BARCODE_CONFIG

class BarcodeVideoProcessor(VideoProcessorBase):
    """Processador de vídeo para leitura de códigos de barras"""
    
    def __init__(self):
        """Inicialização do processador de vídeo"""
        self.barcode_data = None
        self.barcode_type = None
        self.last_detection_time = 0
        self.detection_interval = BARCODE_CONFIG["detection_interval"]
        
    def recv(self, frame):
        """
        Processa cada frame de vídeo recebido
        
        Args:
            frame: Frame de vídeo capturado pela webcam
            
        Returns:
            av.VideoFrame: Frame processado com marcação de código de barras
        """
        img = frame.to_ndarray(format="bgr24")
        
        # Verificar se já passou o intervalo de detecção
        current_time = time.time()
        if current_time - self.last_detection_time >= self.detection_interval:
            # Decodificar barcodes
            barcodes = pyzbar.decode(img)
            
            for barcode in barcodes:
                # Extrair e formatar os dados do barcode
                barcode_data = barcode.data.decode("utf-8")
                barcode_type = barcode.type
                
                # Desenhando uma caixa ao redor do código de barras
                (x, y, w, h) = barcode.rect
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Desenhando o texto do código de barras e seu tipo
                text = f"{barcode_data} ({barcode_type})"
                cv2.putText(img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (0, 255, 0), 2)
                
                self.barcode_data = barcode_data
                self.barcode_type = barcode_type
                self.last_detection_time = current_time
                
                # Enviando dados para a sessão do Streamlit
                st.session_state.last_barcode = barcode_data
                st.session_state.barcode_detected = True
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")
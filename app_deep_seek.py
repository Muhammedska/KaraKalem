# Hata kodu: 0xC0000409 -> Stack buffer overflow (yani bellek taşması)
# Bu, PyQt5 uygulamalarında genellikle pencere yönetimi, screenshot işlemi ya da boyutsal çakışmalarda oluşur.
# Kodun optimize edilmiş ve yorumlarla zenginleştirilmiş hali aşağıdadır:

import sys
import os
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import win32api
import win32con
import win32gui
from PIL import ImageGrab


class Ui(QMainWindow):
    def __init__(self):
        super().__init__()

        # .ui dosyasının varlığını kontrol et
        ui_path = './data/undockapp.ui'
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        uic.loadUi(ui_path, self)

        # Arka planı yarı saydam yap ve mor çerçeve uygula
        self.setStyleSheet("""
            QMainWindow {
                background-color: rgba(255, 255, 255, 200);
                border: 2px solid magenta;
                border-radius: 10px;
            }
        """)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Buton bağlantıları
        self.quit.clicked.connect(self.close)
        self.pen.clicked.connect(self.start_paint)
        self.ss.clicked.connect(self.start_fullscreen_paint)
        self.eraser.clicked.connect(self.close)

        # Renk butonları
        self.red.clicked.connect(lambda: self.set_color(Qt.red))
        self.blue.clicked.connect(lambda: self.set_color(Qt.blue))
        self.green.clicked.connect(lambda: self.set_color(Qt.green))
        self.black.clicked.connect(lambda: self.set_color(Qt.black))

        # Varsayılan renk ve kalem boyutu
        self.active_color = Qt.red
        self.active_size = 5
        self.hwnd = None

        self.color_indicator = self.findChild(QLabel, "colorIndicator")
        self.size_combo = self.findChild(QComboBox, "sizeCombo")

        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {self.active_color.name()}; border-radius: 5px;")

        if self.size_combo:
            self.size_combo.addItems(["1px", "3px", "5px", "7px", "10px", "15px", "20px"])
            self.size_combo.setCurrentIndex(2)
            self.size_combo.currentIndexChanged.connect(self.set_size)

    def showEvent(self, event):
        super().showEvent(event)
        self.hwnd = int(self.winId())
        self.setup_window_transparency()

    def setup_window_transparency(self):
        # Transparan pencere ayarı
        if not self.hwnd:
            return

        try:
            ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            ex_style |= win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex_style)
            win32gui.SetLayeredWindowAttributes(
                self.hwnd,
                win32api.RGB(255, 0, 128),  # Fuchsia renk
                0,
                win32con.LWA_COLORKEY
            )
        except Exception as e:
            print(f"Transparency ayarlanamadı: {e}")

    def set_color(self, color):
        # Aktif rengi ayarla
        self.active_color = color
        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {color.name()}; border-radius: 5px;")

    def set_size(self, index):
        sizes = [1, 3, 5, 7, 10, 15, 20]
        if 0 <= index < len(sizes):
            self.active_size = sizes[index]

    def start_paint(self):
        self.hide()
        self.capture_screenshot()
        self.paint_window = PaintWindow(self.active_color, self.active_size, self)
        self.paint_window.show()

    def start_fullscreen_paint(self):
        self.hide()
        self.capture_screenshot()
        self.paint_window = PaintWindow(self.active_color, self.active_size, self)
        self.paint_window.showFullScreen()

    def capture_screenshot(self):
        try:
            screenshot = ImageGrab.grab()
            screenshot.save('./curr_screen_cozeltisoftware.png', 'PNG')
        except Exception as e:
            print(f"Screenshot alınamadı: {e}")


class PaintWindow(QMainWindow):
    def __init__(self, brush_color, brush_size, main_window):
        super().__init__()
        # ... mevcut kodlarınız ...

        # Yeni eklemeler
        self.tool_window = ToolWindow(self)  # Araç penceresi oluştur
        self.tool_window.show()

    # Yeni fonksiyonlar ekle
    def set_brush_color(self, color):
        self.brush_color = color

    def set_brush_size(self, size):
        self.brush_size = size

    def closeEvent(self, event):
        self.tool_window.close()  # Ana pencere kapanırken araç penceresini de kapat
        super().closeEvent(event)


# Yeni araç penceresi sınıfı
class ToolWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paint_window = parent  # PaintWindow referansı
        self.setWindowTitle("Kalem Araçları")
        self.setFixedSize(250, 150)

        # Pencerenin şeffaf olmamasını sağla
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # Widget'ları oluştur
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout()

        # Fırça boyutu seçimi
        size_label = QLabel("Fırça Boyutu:")
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(self.paint_window.brush_size)
        self.size_slider.valueChanged.connect(self.update_brush_size)

        # Renk seçimi
        color_label = QLabel("Renk Seçimi:")
        color_layout = QHBoxLayout()

        colors = [
            ("Siyah", Qt.black),
            ("Kırmızı", Qt.red),
            ("Mavi", Qt.blue),
            ("Yeşil", Qt.green),
            ("Sarı", Qt.yellow)
        ]

        for text, color in colors:
            btn = QPushButton(text)
            btn.setStyleSheet(f"background-color: {color.name()}")
            btn.clicked.connect(lambda _, c=color: self.set_color(c))
            color_layout.addWidget(btn)

        # Düzenlemeler
        layout.addWidget(size_label)
        layout.addWidget(self.size_slider)
        layout.addWidget(color_label)
        layout.addLayout(color_layout)
        self.setLayout(layout)

    def update_brush_size(self, size):
        self.paint_window.set_brush_size(size)

    def set_color(self, color):
        self.paint_window.set_brush_color(color)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Ui()
    win.show()
    sys.exit(app.exec_())

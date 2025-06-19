import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QPushButton, QColorDialog)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QPainter, QPen, QImage, QColor


class PaintWindow(QMainWindow):
    def __init__(self, brush_color=Qt.black, brush_size=5, main_window=None):
        super().__init__()
        self.brush_color = brush_color
        self.brush_size = brush_size
        self.main_window = main_window
        self.drawing = False
        self.lastPoint = QPoint()

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # Ekran boyutunu ayarla
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())

        # Arka plan resmini yükle
        self.load_screenshot()

        # ToolWindow oluştur
        self.tool_window = ToolWindow(self)
        self.tool_window.show()

    def load_screenshot(self):
        path = './curr_screen_cozeltisoftware.png'
        if not os.path.exists(path):
            self.image = QImage(self.size(), QImage.Format_ARGB32)
            self.image.fill(Qt.white)
        else:
            img = QImage(path)
            self.image = img.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.lastPoint = event.pos()
            self.painter = QPainter(self.image)
            self.painter.setPen(QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.painter.drawLine(self.lastPoint, event.pos())
            self.lastPoint = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            if hasattr(self, 'painter'):
                self.painter.end()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
            if self.main_window:
                self.main_window.show()

    def set_brush_color(self, color):
        self.brush_color = color

    def set_brush_size(self, size):
        self.brush_size = size

    def closeEvent(self, event):
        if hasattr(self, 'tool_window') and self.tool_window:
            self.tool_window.close()
        super().closeEvent(event)


class ToolWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paint_window = parent
        self.setWindowTitle("Kalem Araçları")
        self.setFixedSize(300, 180)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)  # Her zaman üstte ve araç penceresi olarak

        # Widget'ları oluştur
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout()

        # Fırça boyutu seçimi
        size_label = QLabel("Fırça Boyutu:")
        layout.addWidget(size_label)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 50)
        self.size_slider.setValue(self.paint_window.brush_size)
        self.size_slider.valueChanged.connect(self.update_brush_size)
        layout.addWidget(self.size_slider)

        # Boyut değeri göstergesi
        self.size_value = QLabel(f"Değer: {self.size_slider.value()}px")
        layout.addWidget(self.size_value)

        # Renk seçimi
        color_label = QLabel("Renk Seçimi:")
        layout.addWidget(color_label)

        color_layout = QHBoxLayout()
        colors = [
            ("Siyah", Qt.black),
            ("Kırmızı", Qt.red),
            ("Mavi", Qt.blue),
            ("Yeşil", Qt.green),
            ("Sarı", Qt.yellow)
        ]

        for text, color in colors:
            btn = QPushButton()
            btn.setFixedSize(30, 30)
            btn.setStyleSheet(f"background-color: {color.name()}; border-radius: 15px;")
            btn.clicked.connect(lambda _, c=color: self.set_color(c))
            color_layout.addWidget(btn)

        layout.addLayout(color_layout)

        # Özel renk seçimi
        custom_color_btn = QPushButton("Özel Renk Seç")
        custom_color_btn.clicked.connect(self.choose_custom_color)
        layout.addWidget(custom_color_btn)

        # Kapat butonu
        close_btn = QPushButton("Kapat (Esc)")
        close_btn.clicked.connect(self.paint_window.close)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def update_brush_size(self, size):
        self.paint_window.set_brush_size(size)
        self.size_value.setText(f"Değer: {size}px")

    def set_color(self, color):
        self.paint_window.set_brush_color(color)

    def choose_custom_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.paint_window.set_brush_color(color)


# Ana uygulama ve pencere testi
if __name__ == "__main__":
    app = QApplication(sys.argv)


    # Örnek ana pencere
    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Ana Pencere")
            self.setGeometry(100, 100, 400, 300)

            btn = QPushButton("Paint Aç", self)
            btn.clicked.connect(self.open_paint)
            self.setCentralWidget(btn)

        def open_paint(self):
            self.paint_window = PaintWindow(main_window=self)
            self.paint_window.show()
            self.hide()


    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
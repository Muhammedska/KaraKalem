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
import traceback


class Ui(QMainWindow):
    def __init__(self):
        super().__init__()

        # .ui dosyasının varlığını kontrol et
        ui_path = 'datam/undockapp.ui'
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        # UI yükleniyor
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
        self.setWindowFlags( Qt.WindowStaysOnTopHint)

        # Buton bağlantıları
        self.quit.clicked.connect(self.close)
        self.pen.clicked.connect(self.start_paint)
        self.ss.clicked.connect(self.start_fullscreen_paint)
        self.eraser.clicked.connect(self.close)

        # Renk butonları
        self.red.clicked.connect(lambda: self.set_color(QColor(Qt.red)))
        self.blue.clicked.connect(lambda: self.set_color(QColor(Qt.blue)))
        self.green.clicked.connect(lambda: self.set_color(QColor(Qt.green)))
        self.black.clicked.connect(lambda: self.set_color(QColor(Qt.black)))

        # Varsayılan renk ve kalem boyutu
        self.active_color = QColor(Qt.red)
        self.active_size = 5
        self.hwnd = None

        self.color_indicator = self.findChild(QLabel, "colorIndicator")
        self.size_combo = self.findChild(QComboBox, "sizeCombo")

        # Renk göstergesini ayarla
        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {self.active_color.name()}; border-radius: 5px;")

        # Kalem boyutu seçim kutusunu doldur
        if self.size_combo:
            self.size_combo.addItems(["1px", "3px", "5px", "7px", "10px", "15px", "20px"])
            self.size_combo.setCurrentIndex(2)
            self.size_combo.currentIndexChanged.connect(self.set_size)

    def showEvent(self, event):
        super().showEvent(event)
        self.hwnd = int(self.winId())
        self.setup_window_transparency()

    def setup_window_transparency(self):
        # Pencereyi şeffaf yapmak için gerekli ayarlar
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
            traceback.print_exc()

    def set_color(self, color):
        # Aktif rengi güncelle
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
        try:
            self.paint_window = PaintWindow(self.active_color, self.active_size, self)
            self.paint_window.show()
        except Exception as e:
            print(f"Paint penceresi oluşturulamadı: {e}")
            traceback.print_exc()
            self.show()

    def start_fullscreen_paint(self):
        self.hide()
        self.capture_screenshot()
        try:
            self.paint_window = PaintWindow(self.active_color, self.active_size, self)
            self.paint_window.showFullScreen()
        except Exception as e:
            print(f"Tam ekran paint penceresi oluşturulamadı: {e}")
            traceback.print_exc()
            self.show()

    def capture_screenshot(self):
        try:
            if os.path.exists('./curr_screen_cozeltisoftware.png'):
                os.remove('./curr_screen_cozeltisoftware.png')

            screenshot = ImageGrab.grab()
            screen = QApplication.primaryScreen()
            screen_rect = screen.geometry()
            max_width = min(screen_rect.width(), 1920)
            max_height = min(screen_rect.height(), 1080)
            screenshot = screenshot.resize((max_width, max_height))
            screenshot.save('./curr_screen_cozeltisoftware.png', 'PNG')
        except Exception as e:
            print(f"Screenshot alınamadı: {e}")
            traceback.print_exc()


class PaintWindow(QMainWindow):
    def __init__(self, brush_color, brush_size, main_window):
        super().__init__()

        # Temel ayarlar
        self.brush_color = brush_color

        self.brush_size  = brush_size
        self.main_window = main_window
        self.active_tool = "pen"
        self.drawing     = False
        self.lastPoint   = QPoint()
        self.temp_start_point = QPoint()
        self.temp_end_point   = QPoint()

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        screen = QApplication.primaryScreen()
        w, h = screen.geometry().width(), screen.geometry().height()
        self.setGeometry(0, 0, min(w,1920), min(h,1080))

        # 1) Arka planı yükle
        self.backgroundImage = self._load_background()
        # 2) Üzerine çizeceğimiz boş, şeffaf katmanı oluştur
        self.overlayImage = QImage(self.backgroundImage.size(), QImage.Format_ARGB32)
        self.overlayImage.fill(Qt.transparent)

        self.tool_window = ToolWindow(self)
        self.tool_window.show()

    def _load_background(self):
        path = './curr_screen_cozeltisoftware.png'
        img = QImage(path) if os.path.exists(path) else QImage()
        if img.isNull():
            img = QImage(self.width(), self.height(), QImage.Format_RGB32)
            img.fill(Qt.white)
        else:
            img = img.scaled(self.width(), self.height(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            img = img.convertToFormat(QImage.Format_RGB32)
        return img

    def set_tool(self, tool):
        self.active_tool = tool

    def set_brush_color(self, color):
        self.brush_color = color

    def set_brush_size(self, size):

        self.brush_size = size


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.lastPoint = event.pos()
            self.temp_start_point = event.pos()

    def mouseMoveEvent(self, event):
        if not self.drawing or not (event.buttons() & Qt.LeftButton):
            return

        if self.active_tool in ["pen", "eraser"]:
            # pen veya silgi için anlık çizim
            painter = QPainter(self.overlayImage)
            if self.active_tool == "eraser":
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                pen = QPen(Qt.transparent, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.lastPoint, event.pos())
            painter.end()
            self.lastPoint = event.pos()
            self.update()
        else:
            # line, rect, ellipse için sadece temp_end_point'i güncelle
            self.temp_end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            # nihai şekli overlayImage üzerine çiz
            painter = QPainter(self.overlayImage)
            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)

            if self.active_tool == "line":
                painter.drawLine(self.temp_start_point, event.pos())
            elif self.active_tool == "rect":
                painter.drawRect(QRect(self.temp_start_point, event.pos()).normalized())
            elif self.active_tool == "ellipse":
                painter.drawEllipse(QRect(self.temp_start_point, event.pos()).normalized())
            # pen ve eraser zaten mouseMoveEvent ile işlendi

            painter.end()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 1) arka plan
        painter.drawImage(0, 0, self.backgroundImage)
        # 2) çizim katmanı
        painter.drawImage(0, 0, self.overlayImage)

        # şekil önizlemesi (çizgi/dikdörtgen/daire)
        if self.drawing and self.active_tool in ["line", "rect", "ellipse"]:
            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            rect = QRect(self.temp_start_point, self.temp_end_point).normalized()
            if self.active_tool == "line":
                painter.drawLine(self.temp_start_point, self.temp_end_point)
            elif self.active_tool == "rect":
                painter.drawRect(rect)
            elif self.active_tool == "ellipse":
                painter.drawEllipse(rect)

        painter.end()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_tool_window()
            self.close()
            if self.main_window:
                self.main_window.show()

    def close_tool_window(self):
        if hasattr(self, 'tool_window') and self.tool_window:
            self.tool_window.close()
            self.tool_window = None

    def closeEvent(self, event):
        self.close_tool_window()
        win = Ui()
        win.show()

class ToolWindowold(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paint_window = parent
        self.setWindowTitle("Kalem Araçları")
        self.setFixedSize(120, 440)  # Yükseklik biraz artırdık spinbox için
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        ui_path = 'datam/pen_tool.ui'
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        uic.loadUi(ui_path, self)  # UI yüklendi

        # Buton bağlantıları
        self.pen_btn.clicked.connect(self.select_pen)
        self.eraser_btn.clicked.connect(self.select_eraser)

        self.color_red.clicked.connect(lambda: self.set_color(Qt.red))
        self.color_blue.clicked.connect(lambda: self.set_color(Qt.blue))
        self.color_black.clicked.connect(lambda: self.set_color(Qt.black))
        self.color_green.clicked.connect(lambda: self.set_color(Qt.green))

        # SpinBox bağlantısı
        self.brushSizeSpinBox.setMinimum(1)
        self.brushSizeSpinBox.setMaximum(50)
        self.brushSizeSpinBox.setValue(self.paint_window.brush_size)
        self.brushSizeSpinBox.valueChanged.connect(self.change_brush_size)

        self.exit_btn.clicked.connect(self.close)

    def select_pen(self):
        if self.paint_window:
            self.paint_window.set_tool("pen")

    def select_eraser(self):
        if self.paint_window:
            self.paint_window.set_tool("eraser")

    def set_color(self, color):
        if self.paint_window:
            self.paint_window.set_brush_color(QColor(color))

    def change_brush_size(self, value):
        if self.paint_window:
            self.paint_window.set_brush_size(value)

    def closeEvent(self, event):
        # ToolWindow kapatıldığında paint penceresini de kapat
        if self.paint_window:
            self.paint_window.close()
        event.accept()

class ToolWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.paint_window = parent
        self.setWindowTitle("Kalem Araçları")
        self.setFixedSize(120, 440)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        ui_path = 'datam/pen_tool.ui'
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        uic.loadUi(ui_path, self)

        # Buton bağlantıları
        self.pen_btn.clicked.connect(self.select_pen)
        self.eraser_btn.clicked.connect(self.select_eraser)

        self.color_red.clicked.connect(lambda: self.set_color(Qt.red))
        self.color_blue.clicked.connect(lambda: self.set_color(Qt.blue))
        self.color_black.clicked.connect(lambda: self.set_color(Qt.black))
        self.color_green.clicked.connect(lambda: self.set_color(Qt.green))

        # QSlider bağlantısı (SpinBox yerine kullanılıyor)
        self.horizontalSlider.setMinimum(1)
        self.horizontalSlider.setMaximum(50)
        self.horizontalSlider.setValue(self.paint_window.brush_size)
        self.horizontalSlider.valueChanged.connect(self.change_brush_size)
        # Şekiller
        self.line_btn.clicked.connect(lambda: self.set_tool("line"))
        self.rect_btn.clicked.connect(lambda: self.set_tool("rect"))
        self.ellipse_btn.clicked.connect(lambda: self.set_tool("ellipse"))

        # Fosforlu kalem
        self.highlight_btn.clicked.connect(self.select_highlighter)

        # Çıkış
        self.exit_btn.clicked.connect(self.close)

    def set_tool(self, tool):
        if self.paint_window:
            self.paint_window.set_tool(tool)


    def select_highlighter(self):
        """Yarı saydam fosforlu kalem gibi bir çizim rengi ayarla"""
        if self.paint_window:
            color = QColor(self.paint_window.brush_color)
            color.setAlpha(128)  # %50 şeffaflık
            self.paint_window.set_brush_color(color)
            self.paint_window.set_tool("pen")

    def select_pen(self):
        if self.paint_window:
            self.paint_window.set_tool("pen")

    def select_eraser(self):
        if self.paint_window:
            self.paint_window.set_tool("eraser")

    def set_color(self, color):
        if self.paint_window:
            self.paint_window.set_brush_color(QColor(color))

    def change_brush_size(self, value):
        if self.paint_window:
            self.paint_window.set_brush_size(value)

    def closeEvent(self, event):
        if self.paint_window:
            self.paint_window.close()
        event.accept()

if __name__ == '__main__':
    sys.setrecursionlimit(10000)
    app = QApplication(sys.argv)
    try:
        win = Ui()
        win.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Kritik hata: {e}")
        traceback.print_exc()
        sys.exit(1)

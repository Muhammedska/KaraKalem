import sys
import datetime
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QToolBar, QAction, QColorDialog,
                             QInputDialog, QMessageBox, QShortcut)
from PyQt5.QtGui import (QPainter, QPainterPath, QPen, QColor, QFont,
                         QKeySequence, QPixmap, QPolygonF)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QPointF


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

        # Çizim özellikleri
        self.drawing = False
        self.last_point = QPoint()
        self.pen_color = QColor(255, 0, 0)  # Kırmızı
        self.pen_width = 4
        self.mode = "draw"  # draw, rectangle, circle, arrow, text
        self.current_shape = None

        # Çizim verileri
        self.paths = []  # Tüm çizim yolları
        self.shapes = []  # Dikdörtgen, daire ve oklar
        self.texts = []  # Metin öğeleri
        self.background_image = None

        # Geri alma için yığın
        self.undo_stack = []

        # Klavye kısayolları
        self.shortcut_undo = QShortcut(QKeySequence.Undo, self)
        self.shortcut_undo.activated.connect(self.undo)
        self.shortcut_clear = QShortcut(QKeySequence('Ctrl+C'), self)
        self.shortcut_clear.activated.connect(self.clear_canvas)
        self.shortcut_quit = QShortcut(QKeySequence('Esc'), self)
        self.shortcut_quit.activated.connect(self.close)
        self.shortcut_save = QShortcut(QKeySequence.Save, self)
        self.shortcut_save.activated.connect(self.capture_screen)

    def capture_background(self):
        """Ekran görüntüsü alarak arka plana yerleştirir"""
        screen = QApplication.primaryScreen()
        screenshot = screen.grabWindow(0)
        self.background_image = screenshot
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

            if self.mode == "draw":
                path = QPainterPath()
                path.moveTo(self.last_point)
                self.paths.append((path, self.pen_color, self.pen_width))
            elif self.mode == "text":
                text, ok = QInputDialog.getText(self, "Metin Ekle", "Metin:")
                if ok and text:
                    self.texts.append((text, event.pos(), self.pen_color, QFont("Arial", 16)))
                    self.update()
            else:
                # Şekil çizimi başlangıcı
                self.current_shape = {
                    "type": self.mode,
                    "start": event.pos(),
                    "end": event.pos(),
                    "color": self.pen_color,
                    "width": self.pen_width
                }

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drawing:
            if self.mode == "draw":
                path = self.paths[-1][0]
                path.lineTo(event.pos())
                self.paths[-1] = (path, self.paths[-1][1], self.paths[-1][2])
                self.last_point = event.pos()
                self.update()
            elif self.mode in ["rectangle", "circle", "arrow"]:
                self.current_shape["end"] = event.pos()
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            if self.mode in ["rectangle", "circle", "arrow"] and self.current_shape:
                self.shapes.append(self.current_shape.copy())
                self.current_shape = None
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Arka plan görüntüsünü çiz
        if self.background_image:
            painter.drawPixmap(0, 0, self.background_image)

        # Tüm çizim yollarını çiz
        for path, color, width in self.paths:
            pen = QPen(color, width)
            painter.setPen(pen)
            painter.drawPath(path)

        # Şekilleri çiz
        for shape in self.shapes:
            self.draw_shape(painter, shape)

        # Metinleri çiz
        for text, position, color, font in self.texts:
            painter.setPen(color)
            painter.setFont(font)
            painter.drawText(position, text)

        # Şu an çizilmekte olan şekli çiz
        if self.drawing and self.current_shape:
            self.draw_shape(painter, self.current_shape)

    def draw_shape(self, painter, shape):
        pen = QPen(shape["color"], shape["width"])
        painter.setPen(pen)
        start = shape["start"]
        end = shape["end"]
        rect = QRect(start, end).normalized()

        if shape["type"] == "rectangle":
            painter.drawRect(rect)
        elif shape["type"] == "circle":
            painter.drawEllipse(rect)
        elif shape["type"] == "arrow":
            painter.drawLine(start, end)

            # Ok başı çizimi
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            arrow_size = 15

            p1 = end - QPointF(
                arrow_size * math.cos(angle - math.pi / 6),
                arrow_size * math.sin(angle - math.pi / 6)
            )
            p2 = end - QPointF(
                arrow_size * math.cos(angle + math.pi / 6),
                arrow_size * math.sin(angle + math.pi / 6)
            )

            arrow_head = QPolygonF()
            arrow_head.append(end)
            arrow_head.append(p1)
            arrow_head.append(p2)

            painter.drawPolygon(arrow_head)

    def undo(self):
        """Son işlemi geri alır"""
        if self.paths:
            self.undo_stack.append(self.paths.pop())
            self.update()
        elif self.shapes:
            self.undo_stack.append(self.shapes.pop())
            self.update()
        elif self.texts:
            self.undo_stack.append(self.texts.pop())
            self.update()

    def clear_canvas(self):
        """Tüm çizimleri temizler"""
        self.paths = []
        self.shapes = []
        self.texts = []
        self.undo_stack = []
        self.update()

    def capture_screen(self):
        """Ekran görüntüsünü kaydeder"""
        if not self.background_image:
            self.capture_background()

        # Çizimleri ekran görüntüsüne ekle
        screenshot = self.background_image.copy()
        painter = QPainter(screenshot)
        painter.setRenderHint(QPainter.Antialiasing)

        # Tüm çizim yollarını çiz
        for path, color, width in self.paths:
            pen = QPen(color, width)
            painter.setPen(pen)
            painter.drawPath(path)

        # Şekilleri çiz
        for shape in self.shapes:
            self.draw_shape(painter, shape)

        # Metinleri çiz
        for text, position, color, font in self.texts:
            painter.setPen(color)
            painter.setFont(font)
            painter.drawText(position, text)

        painter.end()

        # Dosya adı oluştur
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ekran_notu_{timestamp}.png"

        # Dosyayı kaydet
        screenshot.save(filename, "PNG")
        QMessageBox.information(self, "Kaydedildi", f"Ekran görüntüsü '{filename}' olarak kaydedildi.")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic Pen Klonu")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # Ana widget ve düzen
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)

        # Araç çubuğu oluştur
        self.toolbar = QToolBar("Araçlar")
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: rgba(50, 50, 50, 200);
                border: 1px solid #333;
                border-radius: 5px;
                padding: 5px;
            }
            QToolButton {
                background-color: rgba(70, 70, 70, 200);
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
            }
            QToolButton:hover {
                background-color: rgba(90, 90, 90, 200);
            }
            QToolButton:pressed {
                background-color: rgba(110, 110, 110, 200);
            }
        """)

        # Araçlar
        self.create_actions()
        self.add_toolbar_actions()

        # Ekran görüntüsünü al
        self.canvas.capture_background()

    def create_actions(self):
        # Çizim modları
        self.draw_action = QAction("✏️", self)
        self.draw_action.setToolTip("Serbest Çizim (D)")
        self.draw_action.triggered.connect(lambda: self.set_mode("draw"))
        self.draw_action.setCheckable(True)
        self.draw_action.setChecked(True)

        self.rect_action = QAction("⬜", self)
        self.rect_action.setToolTip("Dikdörtgen (R)")
        self.rect_action.triggered.connect(lambda: self.set_mode("rectangle"))
        self.rect_action.setCheckable(True)

        self.circle_action = QAction("⭕", self)
        self.circle_action.setToolTip("Daire (C)")
        self.circle_action.triggered.connect(lambda: self.set_mode("circle"))
        self.circle_action.setCheckable(True)

        self.arrow_action = QAction("➡️", self)
        self.arrow_action.setToolTip("Ok (A)")
        self.arrow_action.triggered.connect(lambda: self.set_mode("arrow"))
        self.arrow_action.setCheckable(True)

        self.text_action = QAction("T", self)
        self.text_action.setToolTip("Metin Ekle (T)")
        self.text_action.triggered.connect(lambda: self.set_mode("text"))
        self.text_action.setCheckable(True)

        # Renk seçici
        self.color_action = QAction("🎨", self)
        self.color_action.setToolTip("Renk Seç")
        self.color_action.triggered.connect(self.choose_color)

        # Kalınlık ayarları
        self.thin_action = QAction("─", self)
        self.thin_action.setToolTip("İnce Kalem (1)")
        self.thin_action.triggered.connect(lambda: self.set_width(2))

        self.medium_action = QAction("──", self)
        self.medium_action.setToolTip("Orta Kalem (2)")
        self.medium_action.triggered.connect(lambda: self.set_width(4))

        self.thick_action = QAction("━━", self)
        self.thick_action.setToolTip("Kalın Kalem (3)")
        self.thick_action.triggered.connect(lambda: self.set_width(8))

        # İşlemler
        self.undo_action = QAction("↩️", self)
        self.undo_action.setToolTip("Geri Al (Ctrl+Z)")
        self.undo_action.triggered.connect(self.canvas.undo)

        self.clear_action = QAction("❌", self)
        self.clear_action.setToolTip("Temizle (Ctrl+C)")
        self.clear_action.triggered.connect(self.canvas.clear_canvas)

        self.save_action = QAction("💾", self)
        self.save_action.setToolTip("Kaydet (Ctrl+S)")
        self.save_action.triggered.connect(self.canvas.capture_screen)

        self.exit_action = QAction("🚪", self)
        self.exit_action.setToolTip("Çıkış (Esc)")
        self.exit_action.triggered.connect(self.close)

    def add_toolbar_actions(self):
        self.toolbar.addAction(self.draw_action)
        self.toolbar.addAction(self.rect_action)
        self.toolbar.addAction(self.circle_action)
        self.toolbar.addAction(self.arrow_action)
        self.toolbar.addAction(self.text_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.color_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.thin_action)
        self.toolbar.addAction(self.medium_action)
        self.toolbar.addAction(self.thick_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.clear_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addAction(self.exit_action)

    def set_mode(self, mode):
        self.canvas.mode = mode
        # Aktif modu vurgula
        self.draw_action.setChecked(mode == "draw")
        self.rect_action.setChecked(mode == "rectangle")
        self.circle_action.setChecked(mode == "circle")
        self.arrow_action.setChecked(mode == "arrow")
        self.text_action.setChecked(mode == "text")

    def choose_color(self):
        color = QColorDialog.getColor(self.canvas.pen_color, self, "Kalem Rengi Seç")
        if color.isValid():
            self.canvas.pen_color = color

    def set_width(self, width):
        self.canvas.pen_width = width

    def keyPressEvent(self, event):
        # Klavye kısayolları
        if event.key() == Qt.Key_D:
            self.set_mode("draw")
        elif event.key() == Qt.Key_R:
            self.set_mode("rectangle")
        elif event.key() == Qt.Key_C:
            self.set_mode("circle")
        elif event.key() == Qt.Key_A:
            self.set_mode("arrow")
        elif event.key() == Qt.Key_T:
            self.set_mode("text")
        elif event.key() == Qt.Key_1:
            self.set_width(2)
        elif event.key() == Qt.Key_2:
            self.set_width(4)
        elif event.key() == Qt.Key_3:
            self.set_width(8)
        else:
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Koyu tema
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.Window, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.WindowText, Qt.white)
    dark_palette.setColor(dark_palette.Base, QColor(35, 35, 35))
    dark_palette.setColor(dark_palette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ToolTipBase, Qt.white)
    dark_palette.setColor(dark_palette.ToolTipText, Qt.white)
    dark_palette.setColor(dark_palette.Text, Qt.white)
    dark_palette.setColor(dark_palette.Button, QColor(53, 53, 53))
    dark_palette.setColor(dark_palette.ButtonText, Qt.white)
    dark_palette.setColor(dark_palette.BrightText, Qt.red)
    dark_palette.setColor(dark_palette.Highlight, QColor(142, 45, 197).lighter())
    dark_palette.setColor(dark_palette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)

    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec_())
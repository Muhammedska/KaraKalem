import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QColorDialog, QSlider, QVBoxLayout,
    QHBoxLayout, QMessageBox
)
from PyQt5.QtGui import QPainter, QPen, QColor, QScreen, QPixmap
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, pyqtSignal

# Kontrol Paneli Penceresi
class ControlPanelWindow(QWidget):
    # Ana AnnotationWindow'a gönderilecek sinyaller
    color_changed = pyqtSignal(QColor)
    size_changed = pyqtSignal(int)
    clear_drawing_signal = pyqtSignal()
    hide_annotation_signal = pyqtSignal()
    close_app_signal = pyqtSignal()
    take_screenshot_signal = pyqtSignal()
    toggle_drawing_mode_signal = pyqtSignal(bool) # True: drawing, False: mouse pass-through

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kontrol Paneli")
        # Pencere bayrakları: Her zaman üstte, çerçevesiz, yönetici bypass
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Yarı şeffaf arka plan için

        self.offset = QPoint() # Pencere taşıma için başlangıç noktası

        self.init_ui()

    def init_ui(self):
        # Ana yatay düzen (layout)
        control_layout = QHBoxLayout(self)
        control_layout.setContentsMargins(10, 5, 10, 5) # İç boşluklar

        # Stil şablonu (tüm butonlar için ortak)
        slider_style = "QSlider::groove:horizontal { border: 1px solid #999999; height: 8px; background: #888888; margin: 2px 0; border-radius: 4px; }" \
                       "QSlider::handle:horizontal { background: #33aaff; border: 1px solid #33aaff; width: 18px; margin: -5px 0; border-radius: 9px; }"

        # Renk Seçici Butonu
        self.color_button = QPushButton("Renk Seç", self)
        self.color_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.color_button.clicked.connect(self.choose_color)
        control_layout.addWidget(self.color_button)

        # Kalem Boyutu Kaydırıcısı
        self.size_slider = QSlider(Qt.Horizontal, self)
        self.size_slider.setRange(1, 20)
        self.size_slider.setValue(5) # Varsayılan kalem boyutu
        self.size_slider.setToolTip("Kalem Boyutu")
        self.size_slider.setStyleSheet(slider_style)
        self.size_slider.valueChanged.connect(lambda value: self.size_changed.emit(value))
        control_layout.addWidget(self.size_slider)

        # Temizle Butonu
        self.clear_button = QPushButton("Temizle", self)
        self.clear_button.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        self.clear_button.clicked.connect(lambda: self.clear_drawing_signal.emit())
        control_layout.addWidget(self.clear_button)

        # Gizleme Butonu
        self.hide_button = QPushButton("Gizle", self)
        self.hide_button.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0b7dda; }"
        )
        self.hide_button.clicked.connect(lambda: self.hide_annotation_signal.emit())
        control_layout.addWidget(self.hide_button)

        # Çizim Modu / Fare Modu Butonu
        self.drawing_mode_button = QPushButton("Çizim Modu: Açık", self)
        self.drawing_mode_button.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #7B1FA2; }"
        )
        self.is_drawing_active = True # Başlangıçta çizim modu aktif
        self.drawing_mode_button.clicked.connect(self.toggle_drawing_mode)
        control_layout.addWidget(self.drawing_mode_button)

        # Ekran görüntüsü alma butonu
        self.screenshot_button = QPushButton("Ekran Görüntüsü Al", self)
        self.screenshot_button.setStyleSheet(
            "QPushButton { background-color: #FFC107; color: black; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ffb300; }"
        )
        self.screenshot_button.clicked.connect(lambda: self.take_screenshot_signal.emit())
        control_layout.addWidget(self.screenshot_button)

        # Kapatma Butonu
        self.close_button = QPushButton("Kapat", self)
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #FF5722; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
            "QPushButton:hover { background-color: #e64a19; }"
        )
        self.close_button.clicked.connect(lambda: self.close_app_signal.emit())
        control_layout.addWidget(self.close_button)

        self.setLayout(control_layout)
        self.adjustSize() # İçeriğe göre boyutu ayarla

    def choose_color(self):
        color = QColorDialog.getColor(QColor(Qt.red), self, "Renk Seç")
        if color.isValid():
            self.color_changed.emit(color)
            # Renk butonunun rengini güncelle
            self.color_button.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; color: {'black' if color.lightnessF() > 0.5 else 'white'}; border-radius: 8px; padding: 8px 15px; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: {color.darker(120).name()}; }}"
            )

    def toggle_drawing_mode(self):
        self.is_drawing_active = not self.is_drawing_active
        if self.is_drawing_active:
            self.drawing_mode_button.setText("Çizim Modu: Açık")
            self.drawing_mode_button.setStyleSheet(
                "QPushButton { background-color: #9C27B0; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
                "QPushButton:hover { background-color: #7B1FA2; }"
            )
        else:
            self.drawing_mode_button.setText("Çizim Modu: Kapalı")
            self.drawing_mode_button.setStyleSheet(
                "QPushButton { background-color: #607D8B; color: white; border-radius: 8px; padding: 8px 15px; font-weight: bold; }"
                "QPushButton:hover { background-color: #455A64; }"
            )
        self.toggle_drawing_mode_signal.emit(self.is_drawing_active)

    # Pencereyi sürükleme işlevleri (Kontrol paneli için)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(self.mapToGlobal(event.pos() - self.offset))

    def mouseReleaseEvent(self, event):
        self.offset = QPoint()

# Ana Ekran Açıklama Penceresi (Çizim Tuvali)
class AnnotationWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic Pen Benzeri")
        # Pencereyi tüm ekranı kaplayacak şekilde ayarla
        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

        # Çerçevesiz, her zaman üstte (WindowManagerHint kaldırıldı)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint # Qt.BypassWindowManagerHint kaldırıldı
        )
        self.setAttribute(Qt.WA_TranslucentBackground) # Arka planı şeffaf yapar
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Başlangıçta fare olaylarını yakala (çizim modu aktif)

        self.drawing = False
        self.drawing_enabled = True # Başlangıçta çizim modu aktif
        self.last_point = QPoint()

        self.pen_color = QColor(Qt.red) # Varsayılan kalem rengi
        self.pen_size = 5 # Varsayılan kalem boyutu
        self.paths = [] # Çizilen tüm yolları saklamak için

        self.screenshot_selector = None
        self.image_editor = None

        self.init_control_panel()

    def init_control_panel(self):
        self.control_panel = ControlPanelWindow()
        # Sinyalleri bağla
        self.control_panel.color_changed.connect(self.set_pen_color)
        self.control_panel.size_changed.connect(self.set_pen_size)
        self.control_panel.clear_drawing_signal.connect(self.clear_drawing)
        self.control_panel.hide_annotation_signal.connect(self.toggle_visibility)
        self.control_panel.close_app_signal.connect(self.close_application)
        self.control_panel.take_screenshot_signal.connect(self.take_screenshot)
        self.control_panel.toggle_drawing_mode_signal.connect(self.toggle_drawing_mode)

        # Kontrol panelini ekranın sağ üst köşesine yerleştir
        screen_geo = QApplication.primaryScreen().geometry()
        panel_width = self.control_panel.width()
        panel_height = self.control_panel.height()
        self.control_panel.move(screen_geo.width() - panel_width - 20, 20) # Sağ üstten 20px boşluk

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for path_data in self.paths:
            pen = QPen(path_data['color'], path_data['size'], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(1, len(path_data['points'])):
                painter.drawLine(path_data['points'][i-1], path_data['points'][i])

    def mousePressEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.pos()
            self.paths.append({'color': self.pen_color, 'size': self.pen_size, 'points': [self.last_point]})

    def mouseMoveEvent(self, event):
        if self.drawing_enabled and self.drawing and event.buttons() & Qt.LeftButton:
            current_path = self.paths[-1]['points']
            current_path.append(event.pos())
            self.last_point = event.pos()
            self.update() # Ekranı yeniden çiz

    def mouseReleaseEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.LeftButton:
            self.drawing = False

    def set_pen_color(self, color):
        self.pen_color = color

    def set_pen_size(self, size):
        self.pen_size = size

    def clear_drawing(self):
        self.paths = []
        self.update()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
            self.control_panel.hide()
            show_message("Bilgi", "Uygulama gizlendi. Tekrar göstermek için 'S' tuşuna basabilirsiniz.")
        else:
            self.show()
            self.control_panel.show()

    def toggle_drawing_mode(self, enabled):
        self.drawing_enabled = enabled
        if self.drawing_enabled:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Fare olaylarını yakala
            self.setCursor(Qt.CrossCursor) # İmleci kalem gibi yap
            self.activateWindow() # Pencereyi aktif hale getir
            self.raise_() # Pencereyi üste getir
        else:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True) # Fare olaylarını altındaki pencerelere ilet
            self.unsetCursor() # Varsayılan imleci kullan
        self.update() # Pencere özelliklerinin güncellendiğinden emin ol

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_application()
        elif event.key() == Qt.Key_S and not self.isVisible():
            self.toggle_visibility()

    def take_screenshot(self):
        self.hide() # Ana pencereyi gizle
        self.control_panel.hide() # Kontrol panelini gizle
        QApplication.processEvents() # Olay döngüsünün pencereleri gizlemesini bekle

        # Ekran seçim penceresini başlat
        self.screenshot_selector = ScreenshotSelector()
        self.screenshot_selector.screenshot_taken.connect(self.open_image_editor)
        self.screenshot_selector.screenshot_cancelled.connect(self.show_windows_after_screenshot)
        self.screenshot_selector.show()

    def show_windows_after_screenshot(self):
        # Ekran görüntüsü seçimi iptal edildiğinde veya tamamlandığında pencereleri tekrar göster
        self.show()
        self.control_panel.show()

    def open_image_editor(self, pixmap):
        self.show_windows_after_screenshot() # Pencereleri tekrar göster
        self.image_editor = ImageEditorWindow(pixmap)
        self.image_editor.show()

    def close_application(self):
        # Tüm pencereleri kapat
        if self.screenshot_selector:
            self.screenshot_selector.close()
        if self.image_editor:
            self.image_editor.close()
        self.control_panel.close()
        self.close()
        QApplication.instance().quit()


# Ekran seçim penceresi (Değişiklik yok)
class ScreenshotSelector(QWidget):
    screenshot_taken = pyqtSignal(QPixmap)
    screenshot_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Arka planı şeffaf yapar
        self.setCursor(Qt.CrossCursor) # İmleci artı işareti yapar

        self.screen = QApplication.primaryScreen().grabWindow(0) # Tüm ekranı yakala
        self.setGeometry(self.screen.rect()) # Pencereyi ekran boyutuna ayarla

        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.screen) # Ekran görüntüsünü çiz

        # Seçim alanını vurgula
        if self.selecting:
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.drawRect(rect)
            painter.fillRect(rect, QColor(0, 0, 0, 100)) # Seçilen alanı koyu ve yarı şeffaf yapar

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selecting = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selecting = False
            rect = QRect(self.start_point, self.end_point).normalized()
            if not rect.isEmpty():
                screenshot = self.screen.copy(rect)
                self.screenshot_taken.emit(screenshot)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.screenshot_cancelled.emit() # İptal sinyali gönder
            self.close()

# Görüntü düzenleme penceresi (Değişiklik yok)
class ImageEditorWindow(QWidget):
    def __init__(self, pixmap):
        super().__init__()
        self.setWindowTitle("Ekran Görüntüsü Düzenleyici")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: white;") # Beyaz arka plan

        self.original_pixmap = pixmap
        self.current_pixmap = QPixmap(pixmap.size()) # Çizim için ayrı bir pixmap
        self.current_pixmap.fill(Qt.transparent) # Şeffaf arka plan

        self.drawing = False
        self.last_point = QPoint()
        self.pen_color = QColor(Qt.black)
        self.pen_size = 3
        self.paths = []

        self.image_offset = QPoint(0, 0) # Görüntünün konumu
        self.moving_image = False
        self.last_mouse_pos = QPoint()

        self.init_ui()
        self.center_image()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Kontrol paneli
        control_panel = QWidget(self)
        control_panel.setStyleSheet("background-color: #f0f0f0; border-radius: 10px; padding: 5px;")
        control_layout = QHBoxLayout(control_panel)

        self.color_button = QPushButton("Renk", self)
        self.color_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.color_button.clicked.connect(self.choose_color)
        control_layout.addWidget(self.color_button)

        self.size_slider = QSlider(Qt.Horizontal, self)
        self.size_slider.setRange(1, 15)
        self.size_slider.setValue(self.pen_size)
        self.size_slider.setToolTip("Kalem Boyutu")
        self.size_slider.valueChanged.connect(self.change_pen_size)
        control_layout.addWidget(self.size_slider)

        self.clear_button = QPushButton("Temizle", self)
        self.clear_button.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; border-radius: 5px; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #da190b; }"
        )
        self.clear_button.clicked.connect(self.clear_drawing)
        control_layout.addWidget(self.clear_button)

        self.close_button = QPushButton("Kapat", self)
        self.close_button.setStyleSheet(
            "QPushButton { background-color: #FF5722; color: white; border-radius: 5px; padding: 5px 10px; }"
            "QPushButton:hover { background-color: #e64a19; }"
        )
        self.close_button.clicked.connect(self.close)
        control_layout.addWidget(self.close_button)

        main_layout.addWidget(control_panel, alignment=Qt.AlignTop | Qt.AlignCenter)
        main_layout.addStretch()

    def center_image(self):
        # Görüntüyü pencerenin ortasına yerleştir
        self.image_offset.setX((self.width() - self.original_pixmap.width()) // 2)
        self.image_offset.setY((self.height() - self.original_pixmap.height()) // 2)
        self.update()


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Beyaz arka planı çiz
        painter.fillRect(self.rect(), QColor(Qt.white))

        # Orijinal görüntüyü çiz
        painter.drawPixmap(self.image_offset, self.original_pixmap)

        # Çizimleri current_pixmap üzerine çiz
        drawing_painter = QPainter(self.current_pixmap)
        drawing_painter.setRenderHint(QPainter.Antialiasing)

        for path_data in self.paths:
            pen = QPen(path_data['color'], path_data['size'], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            drawing_painter.setPen(pen)
            for i in range(1, len(path_data['points'])):
                drawing_painter.drawLine(path_data['points'][i-1] - self.image_offset,
                                        path_data['points'][i] - self.image_offset)

        drawing_painter.end() # QPainter'ı sonlandır

        # current_pixmap'ı ana pencereye çiz
        painter.drawPixmap(self.image_offset, self.current_pixmap)


    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Görüntü üzerinde mi çizim yapılıyor yoksa görüntü mü taşınıyor?
            image_rect = QRect(self.image_offset, self.original_pixmap.size())
            if image_rect.contains(event.pos()):
                self.drawing = True
                self.last_point = event.pos()
                self.paths.append({'color': self.pen_color, 'size': self.pen_size, 'points': [self.last_point]})
            else:
                self.moving_image = True
                self.last_mouse_pos = event.pos()


    def mouseMoveEvent(self, event):
        if self.drawing and event.buttons() & Qt.LeftButton:
            current_path = self.paths[-1]['points']
            current_path.append(event.pos())
            self.last_point = event.pos()
            self.update()

        elif self.moving_image and event.buttons() & Qt.LeftButton:
            delta = event.pos() - self.last_mouse_pos
            self.image_offset += delta
            self.last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.moving_image = False

    def choose_color(self):
        color = QColorDialog.getColor(self.pen_color, self, "Renk Seç")
        if color.isValid():
            self.pen_color = color
            self.color_button.setStyleSheet(
                f"QPushButton {{ background-color: {color.name()}; color: {'black' if color.lightnessF() > 0.5 else 'white'}; border-radius: 5px; padding: 5px 10px; }}"
                f"QPushButton:hover {{ background-color: {color.darker(120).name()}; }}"
            )

    def change_pen_size(self):
        self.pen_size = self.size_slider.value()

    def clear_drawing(self):
        self.paths = []
        self.current_pixmap.fill(Qt.transparent) # Çizim pixmap'ini temizle
        self.update()

    def resizeEvent(self, event):
        # Pencere boyutu değiştiğinde görüntüyü ortala
        self.center_image()
        super().resizeEvent(event)


def show_message(title, message):
    msg_box = QMessageBox()
    msg_box.setWindowTitle(title)
    msg_box.setText(message)
    msg_box.setIcon(QMessageBox.Information)
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Epic Pen Benzeri")
    # QApplication.setQuitOnLastWindowClosed(True) # Uygulamanın ControlPanelWindow'un kapanmasıyla da kapanması için yönetimi AnnotationWindow'a bırakalım

    main_window = AnnotationWindow()
    main_window.show()
    main_window.control_panel.show() # Kontrol panelini de göster

    sys.exit(app.exec_())

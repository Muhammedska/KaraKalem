import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QSlider, QLabel, QColorDialog, QFrame, QMessageBox # QMessageBox eklendi
)
from PyQt5.QtGui import QPainter, QPen, QColor, QScreen, QPixmap, QBrush # QBrush eklendi
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal, QTimer, QSize
from typing import Union

# --- Yardımcı Sınıf: Seçim Alanı Widget'ı ---
class SelectionAreaWidget(QWidget):
    """
    Ekran üzerinde dikdörtgen bir seçim alanı oluşturmak için kullanılan şeffaf widget.
    Kullanıcı fare ile sürükleyerek bir alan seçer.
    """
    # Seçim tamamlandığında veya iptal edildiğinde yayılacak sinyal
    # is_cancelled: Kullanıcı sağ tıklama veya ESC tuşu ile iptal ettiyse True olur.
    selectionFinished = pyqtSignal(QRect, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Alan Seç")
        # Pencereyi çerçevesiz, her zaman üstte ve şeffaf yap
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor) # Fare imlecini artı işaretine çevir

        self.start_point = QPoint() # Seçimin başlangıç noktası
        self.end_point = QPoint()   # Seçimin bitiş noktası
        self.selecting = False      # Seçim yapılıyor mu?

        # Ekranın tüm boyutunu kapla
        self.setFixedSize(QApplication.primaryScreen().size())

    def paintEvent(self, event):
        """
        Widget içeriğini çizer. Seçim alanını ve arkaplanı karartır.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Tüm ekranı karart (hafif şeffaf siyah)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100)) # %40 şeffaflık

        if self.selecting:
            # Seçim alanını çiz
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine)) # Kırmızı kesik çizgi
            painter.setBrush(QColor(0, 0, 0, 1)) # Seçim alanını tamamen şeffaf yap (içi şeffaf dışı kesikli çizgi)
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        """
        Fare tuşuna basıldığında seçim işlemini başlatır.
        """
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.selecting = True
            self.update() # Ekranı yeniden çiz
        elif event.button() == Qt.RightButton:
            # Sağ tıklama ile seçimi iptal et
            self.selectionFinished.emit(QRect(), True) # Boş QRect ve iptal bayrağı
            self.hide() # Kendini gizle
            self.close() # Widget'ı kapat

    def mouseMoveEvent(self, event):
        """
        Fare hareket ettiğinde seçim alanını günceller.
        """
        if self.selecting:
            self.end_point = event.pos()
            self.update() # Ekranı yeniden çiz

    def mouseReleaseEvent(self, event):
        """
        Fare tuşu bırakıldığında seçimi tamamlar ve sinyal yayar.
        """
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            selection_rect = QRect(self.start_point, event.pos()).normalized()
            self.hide() # Seçim tamamlandıktan sonra kendini gizle
            self.selectionFinished.emit(selection_rect, False) # Seçilen alanı ve iptal edilmediğini yay
            self.close() # Widget'ı kapat

    def keyPressEvent(self, event):
        """
        ESC tuşuna basıldığında seçimi iptal eder.
        """
        if event.key() == Qt.Key_Escape:
            self.selectionFinished.emit(QRect(), True) # Boş QRect ve iptal bayrağı
            self.hide() # Kendini gizle
            self.close() # Widget'ı kapat


# --- Yardımcı Sınıf: Taşınabilir Araç Çubuğu ---
class MovableToolbar(QFrame):
    """
    Çizim araçlarını içeren, sürüklenip taşınabilen bir araç çubuğu (dock widget simülasyonu).
    """
    penColorSelected = pyqtSignal(QColor)
    penThicknessChanged = pyqtSignal(int)
    eraserModeToggled = pyqtSignal(bool)
    returnToMainPage = pyqtSignal() # Ana sayfaya dönme sinyali

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("background-color: #f0f0f0; border-radius: 8px;") # Hafif yuvarlak köşeler ve arka plan
        # Ebeveyni varsa widget, yoksa top-level pencere olarak üstte kalır
        self.setWindowFlags(Qt.WindowStaysOnTopHint if parent is None else Qt.Widget)
        self.init_ui()

        self._old_pos = None # Sürükleme için eski pozisyon

    def init_ui(self):
        """
        Araç çubuğunun kullanıcı arayüzünü başlatır.
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Sürükleme başlığı (handle)
        self.handle_label = QLabel("::: Çizim Araçları :::") # Referansı depola
        self.handle_label.setAlignment(Qt.AlignCenter)
        self.handle_label.setStyleSheet("font-weight: bold; padding-bottom: 5px; border-bottom: 1px solid #ccc;")
        main_layout.addWidget(self.handle_label)

        # Kalem Kalınlığı Seçimi
        thickness_label = QLabel("Kalem Kalınlığı:")
        main_layout.addWidget(thickness_label)
        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setMinimum(1)
        self.thickness_slider.setMaximum(50)
        self.thickness_slider.setValue(5)
        self.thickness_slider.setTickPosition(QSlider.TicksBelow)
        self.thickness_slider.setTickInterval(5)
        self.thickness_slider.valueChanged.connect(self.thickness_changed)
        main_layout.addWidget(self.thickness_slider)

        # Renk Seçimi
        color_label = QLabel("Renk Seçimi:")
        main_layout.addWidget(color_label)
        color_layout = QHBoxLayout()
        colors = {
            "Kırmızı": Qt.red, "Mavi": Qt.blue, "Yeşil": Qt.green,
            "Siyah": Qt.black, "Beyaz": Qt.white
        }
        for name, qcolor_enum in colors.items():
            btn = QPushButton(name)
            qcolor_obj = QColor(qcolor_enum)
            text_color = 'black' if qcolor_enum == Qt.white else 'white'
            btn.setStyleSheet(f"background-color: {qcolor_obj.name()}; color: {text_color}; border-radius: 5px; padding: 5px;")
            # Lambda fonksiyonunu sabitlemek için `c=qcolor_obj` kullanıldı
            btn.clicked.connect(lambda _, c=qcolor_obj: self.select_color(c))
            color_layout.addWidget(btn)
        self.custom_color_btn = QPushButton("Özel Renk")
        self.custom_color_btn.clicked.connect(self.choose_custom_color)
        color_layout.addWidget(self.custom_color_btn)
        main_layout.addLayout(color_layout)

        # Silgi Modu
        self.eraser_button = QPushButton("Silgi")
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(self.toggle_eraser)
        main_layout.addWidget(self.eraser_button)

        # Ana Sayfaya Dön Butonu
        self.return_button = QPushButton("Ana Sayfaya Dön")
        self.return_button.clicked.connect(self.returnToMainPage.emit)
        main_layout.addWidget(self.return_button)

        self.setLayout(main_layout)

    def thickness_changed(self, value):
        """Kalem kalınlığı değiştiğinde sinyal yayar ve silgi modunu kapatır."""
        self.penThicknessChanged.emit(value)
        self.eraser_button.setChecked(False) # Kalınlık değişince silgi modunu kapat

    def select_color(self, qcolor):
        """Renk seçildiğinde sinyal yayar ve silgi modunu kapatır."""
        self.penColorSelected.emit(qcolor)
        self.eraser_button.setChecked(False) # Renk değişince silgi modunu kapat

    def choose_custom_color(self):
        """Özel renk seçimi için renk diyalogu açar."""
        color = QColorDialog.getColor(self.penColorSelected.currentData(), self) # Mevcut rengi başlangıç rengi yap
        if color.isValid():
            self.select_color(color)

    def toggle_eraser(self, checked):
        """Silgi modunu açar veya kapatır."""
        self.eraserModeToggled.emit(checked)
        if checked:
            self.thickness_slider.setValue(20) # Silgi için varsayılan kalınlık
            # Silgi rengi tamamen şeffaf olmalı, çizim katmanı bunu halleder
        else:
            self.thickness_slider.setValue(5) # Varsayılan kalem kalınlığı

    def mousePressEvent(self, event):
        """ Fare basıldığında sürükleme işlemini başlatır. """
        if event.button() == Qt.LeftButton:
            # Sadece başlık etiketine basıldığında sürükle
            # self.childAt(event.pos()) yerine handle_label referansı kullanıldı
            if self.childAt(event.pos()) is self.handle_label:
                self._old_pos = event.globalPos()
                event.accept()
            else:
                event.ignore() # Başlık dışında basıldığında olayı yoksay
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """ Fare hareket ettiğinde pencereyi taşır. """
        if event.buttons() == Qt.LeftButton and self._old_pos:
            # Eğer araç çubuğu ana pencereye bağlı değilse global pozisyon kullanarak taşırız
            if self.parent() is None:
                delta = event.globalPos() - self._old_pos
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self._old_pos = event.globalPos()
            # Eğer araç çubuğu bir ebeveyne bağlıysa (DrawingOverlay gibi)
            # o zaman kendi koordinat sisteminde taşınır
            else:
                delta = event.pos() - self._old_pos
                self.move(self.pos() + delta)
                self._old_pos = event.pos()
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """ Fare bırakıldığında sürükleme işlemini bitirir. """
        self._old_pos = None
        event.accept()
        super().mouseReleaseEvent(event)


# --- Çizim Katmanı ---
class DrawingOverlay(QWidget):
    """
    Ekranın üzerinde yüzen çizim tuvali.
    Hem tam ekran ekran görüntüsü üzerine çizim hem de kısmi ekran görüntüsü üzerine çizim modunu destekler.
    """
    FULL_SCREEN_MODE = 0
    PARTIAL_SCREEN_MODE = 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Çizim Katmanı")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Varsayılan olarak şeffaf

        self.drawing_enabled = False # Çizim modu aktif mi?
        self.strokes = [] # Tamamlanmış çizim vuruşlarını depolar
        self.current_stroke_points = [] # Mevcut çizilen vuruşun noktaları

        self.current_pen_color = QColor(255, 0, 0) # Varsayılan kalem rengi (kırmızı)
        self.current_pen_thickness = 5 # Varsayılan kalem kalınlığı
        self.is_eraser_mode = False # Silgi modu aktif mi?

        # Tam ekranı kapla
        self.setFixedSize(QApplication.primaryScreen().size())

        self.border_color = QColor(255, 0, 0, 150) # Kırmızı yarı şeffaf çerçeve rengi
        self.border_thickness = 5 # Çerçeve kalınlığı

        self.current_mode = self.FULL_SCREEN_MODE # Mevcut çizim modu
        self.full_screen_background_pixmap = None # Tam ekran görüntüsü için arka plan pixmap'i
        self.partial_screenshot_pixmap = None     # Kısmi ekran görüntüsü için pixmap
        self.partial_screenshot_rect = QRect()    # Kısmi ekran görüntüsünün tuvaldeki konumu ve boyutu

        # Kısmi ekran görüntüsü için taşıma/boyutlandırma değişkenleri
        self.resize_handle_size = 10 # Boyutlandırma tutamacının boyutu
        self.current_handle = None # Hangi boyutlandırma tutamacının seçili olduğunu tutar (ör: 'TL', 'BR')
        self._old_pos = QPoint()   # Boyutlandırma/Taşıma için fare pozisyonu
        self.moving_image_mode = False # Görseli taşıma modunda mı?

        # Çizim araç çubuğunu oluştur ve bu katmanın çocuğu yap
        self.toolbar = MovableToolbar(self)
        self.toolbar.hide() # Başlangıçta gizli
        # Araç çubuğunu sağ üst köşeye yerleştir
        self.toolbar.move(self.width() - self.toolbar.width() - 20, 20)

        self._connect_toolbar_signals()

    def _connect_toolbar_signals(self):
        """
        Araç çubuğundan gelen sinyalleri işler ve uygun slotlara bağlar.
        """
        self.toolbar.penColorSelected.connect(self.set_pen_color)
        self.toolbar.penThicknessChanged.connect(self.set_pen_thickness)
        self.toolbar.eraserModeToggled.connect(self.set_eraser_mode)
        # Ana pencereye dönme sinyali, MainWindow tarafından yakalanacak
        # (Bu sinyali doğrudan MainWindow'a iletmek için, MainWindow'daki slotu çağırır.)
        # Aslında bu sinyal DrawingOverlay'den MainWindow'a geçmeli, burada toolbar'dan direkt çağrılıyor.
        # Bu sinyal MainWindow'da yakalanıp işlenmeli.

    def set_drawing_mode(self, enabled: bool):
        """
        Çizim modunu etkinleştirir veya devre dışı bırakır.
        Mod kapatıldığında mevcut tüm çizimleri ve arka planları temizler.
        """
        self.drawing_enabled = enabled
        if not enabled:
            self.current_stroke_points = []
            self.strokes = [] # Çizimleri de temizle
            # Mod kapatıldığında tüm arka planları temizle
            self.full_screen_background_pixmap = None
            self.partial_screenshot_pixmap = None
            self.partial_screenshot_rect = QRect()
            self.setAttribute(Qt.WA_TranslucentBackground, True) # Arka planı tekrar şeffaf yap
        self.update()

    def set_full_screen_mode(self, pixmap: QPixmap):
        """
        Tam ekran annotasyon modunu ayarlar ve ekran görüntüsünü arka plan yapar.
        """
        self.current_mode = self.FULL_SCREEN_MODE
        self.full_screen_background_pixmap = pixmap
        # Tam ekran modunda arka plan tamamen ekran görüntüsü olduğu için şeffaflık gerekli
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.update()

    def set_partial_screen_mode(self, pixmap: QPixmap, initial_rect: QRect):
        """
        Kısmi ekran annotasyon modunu ayarlar ve seçilen görseli tuvale yerleştirir.
        """
        self.current_mode = self.PARTIAL_SCREEN_MODE
        self.partial_screenshot_pixmap = pixmap
        # Kısmi görüntüyü pencerenin ortasına yerleştir
        screen_center = self.rect().center()
        image_size = initial_rect.size()
        # Görselin pencere içindeki başlangıç konumu
        self.partial_screenshot_rect = QRect(screen_center - QPoint(image_size.width() // 2, image_size.height() // 2), image_size)

        # Kısmi ekran modunda arka plan beyaz olmalı ki görsel öne çıksın
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.update()

    def set_pen_color(self, color: QColor):
        """Kalem rengini ayarlar ve silgi modunu kapatır."""
        self.current_pen_color = color
        self.is_eraser_mode = False
        self.toolbar.eraser_button.setChecked(False) # Silgi butonunun işaretini kaldır

    def set_pen_thickness(self, thickness: int):
        """Kalem kalınlığını ayarlar."""
        self.current_pen_thickness = thickness

    def set_eraser_mode(self, enabled: bool):
        """Silgi modunu açar veya kapatır. Silgi modu, transparan bir kalem gibi davranır."""
        self.is_eraser_mode = enabled
        if enabled:
            # Silgi rengi aslında arka planın rengi olmalı, tam şeffaf yapmak yerine
            # Arka plan beyazsa beyaz, tam ekran modunda ekran görüntüsünün rengi olmalı.
            # Ancak transparan bir kalem gibi kullanmak daha esnektir.
            # Burada tamamen şeffaf bir renk kullanmak, paintEvent'teki çizim mantığı ile çalışır.
            self.current_pen_color = QColor(0, 0, 0, 0) # Tamamen şeffaf
            self.current_pen_thickness = 20
        else:
            self.current_pen_color = QColor(255, 0, 0) # Varsayılan kırmızıya dön
            self.current_pen_thickness = self.toolbar.thickness_slider.value() # Kaydırıcı değerine dön

    def clear_drawing(self):
        """Tüm çizimleri temizler."""
        self.strokes = []
        self.current_stroke_points = []
        self.update()

    def paintEvent(self, event):
        """Widget içeriğini çizer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.current_mode == self.FULL_SCREEN_MODE:
            # Tam ekran modunda ekran görüntüsünü arka plan olarak çiz
            if self.full_screen_background_pixmap:
                painter.drawPixmap(self.rect(), self.full_screen_background_pixmap)
            # Tam ekran modunda kırmızı çerçeveyi çiz (sadece çizim modu aktifken)
            if self.drawing_enabled:
                pen = QPen(self.border_color, self.border_thickness)
                painter.setPen(pen)
                # Pencerenin iç kenarından çerçeve çizimi için ayarlandı
                painter.drawRect(self.rect().adjusted(self.border_thickness // 2, self.border_thickness // 2,
                                                      -self.border_thickness // 2, -self.border_thickness // 2))
        elif self.current_mode == self.PARTIAL_SCREEN_MODE:
            # Kısmi ekran modunda tüm arka planı beyaz yap
            painter.fillRect(self.rect(), Qt.white)
            if self.partial_screenshot_pixmap:
                # Kısmi ekran görüntüsünü kendi dikdörtgeninde çiz
                painter.drawPixmap(self.partial_screenshot_rect, self.partial_screenshot_pixmap)

                # Kısmi ekran görüntüsünün etrafına kırmızı çerçeve çiz
                pen = QPen(self.border_color, self.border_thickness)
                painter.setPen(pen)
                painter.drawRect(self.partial_screenshot_rect)

                # Boyutlandırma tutamaçlarını çiz (sadece çizim modu aktifken)
                if self.drawing_enabled:
                    handle_pen = QPen(Qt.blue, 2)
                    handle_brush = QBrush(QColor(0, 0, 255, 150)) # Yarı şeffaf mavi
                    painter.setPen(handle_pen)
                    painter.setBrush(handle_brush)
                    # Köşe tutamaçları
                    for point in [self.partial_screenshot_rect.topLeft(), self.partial_screenshot_rect.topRight(),
                                  self.partial_screenshot_rect.bottomLeft(), self.partial_screenshot_rect.bottomRight()]:
                        painter.drawRect(self._get_handle_rect(point))

        # Saklanan tüm çizim vuruşlarını çiz
        # Silgi modu için çizilen vuruşlar aslında transparan olduğu için arka planı siliyormuş gibi görünür.
        for stroke in self.strokes:
            pen = QPen(stroke['color'], stroke['thickness'], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(len(stroke['points']) - 1):
                painter.drawLine(stroke['points'][i], stroke['points'][i+1])

        # Mevcut çizilen vuruşu çiz (mouse sürüklenirken)
        if self.current_stroke_points:
            pen = QPen(self.current_pen_color, self.current_pen_thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(len(self.current_stroke_points) - 1):
                painter.drawLine(self.current_stroke_points[i], self.current_stroke_points[i+1])

    def _get_handle_rect(self, point: QPoint) -> QRect:
        """ Belirli bir köşe noktası için boyutlandırma tutamacının dikdörtgenini döndürür. """
        # Tutamaçları karenin ortası verilen noktada olacak şekilde çizer
        return QRect(point.x() - self.resize_handle_size // 2,
                     point.y() - self.resize_handle_size // 2,
                     self.resize_handle_size, self.resize_handle_size)

    def _get_handle_at(self, pos: QPoint) -> Union[str, None]:
        """ Fare pozisyonuna göre hangi boyutlandırma tutamacının üzerinde olunduğunu döndürür. """
        if not self.drawing_enabled or self.current_mode != self.PARTIAL_SCREEN_MODE or not self.partial_screenshot_pixmap:
            return None

        rect = self.partial_screenshot_rect
        # Her bir köşe tutamacının dikdörtgenini kontrol et
        if self._get_handle_rect(rect.topLeft()).contains(pos): return 'TL'
        if self._get_handle_rect(rect.topRight()).contains(pos): return 'TR'
        if self._get_handle_rect(rect.bottomLeft()).contains(pos): return 'BL'
        if self._get_handle_rect(rect.bottomRight()).contains(pos): return 'BR'
        return None

    def mousePressEvent(self, event):
        """ Mouse basıldığında olayı işler. Çizim, taşıma veya boyutlandırma modlarını başlatır. """
        if event.button() == Qt.LeftButton:
            self._old_pos = event.pos() # Taşıma/Boyutlandırma/Çizim için başlangıç pozisyonunu kaydet

            if self.drawing_enabled and self.current_mode == self.PARTIAL_SCREEN_MODE:
                # Önce boyutlandırma tutamaçlarını kontrol et
                handle = self._get_handle_at(event.pos())
                if handle:
                    self.current_handle = handle
                    event.accept()
                    return

                # Sonra görselin kendisini taşıma bölgesini kontrol et
                if self.partial_screenshot_rect.contains(event.pos()):
                    self.moving_image_mode = True
                    event.accept()
                    return

            # Hiçbiri değilse ve çizim modu aktifse, çizim başlat
            if self.drawing_enabled:
                self.current_stroke_points = [event.pos()]
                self.update()
                event.accept()
            else:
                event.ignore() # Çizim modu kapalıysa olayı yoksay
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """ Mouse hareket ettiğinde olayı işler. Çizim, taşıma veya boyutlandırma işlemlerini günceller. """
        if event.buttons() == Qt.LeftButton: # Sol fare tuşu basılıysa
            delta = event.pos() - self._old_pos # Geçen süre boyunca faredeki değişim

            if self.drawing_enabled and self.current_mode == self.PARTIAL_SCREEN_MODE:
                # Görseli boyutlandırma
                if self.current_handle:
                    new_rect = QRect(self.partial_screenshot_rect) # Mevcut dikdörtgeni kopyala
                    # Hangi tutamaç seçiliyse o yönde boyutlandırma yap
                    if 'T' in self.current_handle: new_rect.setTop(new_rect.top() + delta.y())
                    if 'B' in self.current_handle: new_rect.setBottom(new_rect.bottom() + delta.y())
                    if 'L' in self.current_handle: new_rect.setLeft(new_rect.left() + delta.x())
                    if 'R' in self.current_handle: new_rect.setRight(new_rect.right() + delta.x())

                    # Minimum boyut kontrolü
                    min_size = QSize(50, 50)
                    if new_rect.width() < min_size.width():
                        # Minimum genişliğin altına düşerse, ilgili kenarı ayarla
                        if 'L' in self.current_handle: new_rect.setLeft(new_rect.right() - min_size.width())
                        else: new_rect.setRight(new_rect.left() + min_size.width())
                    if new_rect.height() < min_size.height():
                        # Minimum yüksekliğin altına düşerse, ilgili kenarı ayarla
                        if 'T' in self.current_handle: new_rect.setTop(new_rect.bottom() - min_size.height())
                        else: new_rect.setBottom(new_rect.top() + min_size.height())

                    self.partial_screenshot_rect = new_rect.normalized() # Dikdörtgeni normalleştir (negatif boyutları engelle)
                    self._old_pos = event.pos() # Konumu güncelle
                    self.update()
                    event.accept()
                    return

                # Görseli taşıma
                if self.moving_image_mode:
                    self.partial_screenshot_rect.translate(delta) # Dikdörtgeni fare hareketine göre taşı
                    self._old_pos = event.pos() # Konumu güncelle
                    self.update()
                    event.accept()
                    return

            # Hiçbiri değilse ve çizim modu aktifse, çizim devam et
            if self.drawing_enabled:
                self.current_stroke_points.append(event.pos())
                self.update()
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """ Mouse bırakıldığında olayı işler. """
        if event.button() == Qt.LeftButton:
            self.current_handle = None # Boyutlandırma tutamacını sıfırla
            self.moving_image_mode = False # Taşıma modunu sıfırla
            self._old_pos = None # Eski pozisyonu sıfırla

            if self.drawing_enabled:
                if self.current_stroke_points: # Eğer çizim yapıldıysa
                    # Mevcut çizim vuruşunu tamamlanmış vuruşlar listesine ekle
                    self.strokes.append({
                        'points': list(self.current_stroke_points), # Noktaları kopyala
                        'color': self.current_pen_color,
                        'thickness': self.current_pen_thickness,
                        'is_eraser': self.is_eraser_mode
                    })
                    self.current_stroke_points = [] # Mevcut vuruşu temizle
                self.update()
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def enterEvent(self, event):
        """ Fare pencereye girdiğinde mouse izleme modunu etkinleştir. """
        self.setMouseTracking(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """ Fare pencereden çıktığında mouse izleme modunu devre dışı bırak. """
        self.setMouseTracking(False)
        super().leaveEvent(event)


# --- Ana Kontrol Penceresi ---
class MainWindow(QWidget):
    """
    Uygulamanın ana kontrol penceresi.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Çizim Uygulaması Kontrolü")
        self.setGeometry(100, 100, 300, 250) # Pencere boyutu ve konumu

        self.drawing_overlay = DrawingOverlay() # Çizim katmanı örneği
        self.selection_widget = None # Seçim widget'ı için referans

        self.init_ui()
        self._connect_signals()

    def init_ui(self):
        """
        Kullanıcı arayüzünü başlatır.
        """
        layout = QVBoxLayout()

        self.full_screen_button = QPushButton("Tam Ekran Çizim Modu")
        self.full_screen_button.setCheckable(True)
        self.full_screen_button.clicked.connect(self._toggle_full_screen_mode)
        layout.addWidget(self.full_screen_button)

        self.partial_screen_button = QPushButton("Kısmi Ekran Görüntüsü Al")
        self.partial_screen_button.clicked.connect(self._initiate_partial_screenshot)
        layout.addWidget(self.partial_screen_button)

        self.clear_button = QPushButton("Çizimi Temizle")
        self.clear_button.clicked.connect(self.drawing_overlay.clear_drawing)
        layout.addWidget(self.clear_button)

        self.close_button = QPushButton("Uygulamayı Kapat")
        self.close_button.clicked.connect(self.close_application)
        layout.addWidget(self.close_button)

        self.setLayout(layout)

    def _connect_signals(self):
        """
        Gerekli sinyalleri bağlar.
        """
        # DrawingOverlay'in araç çubuğundan gelen "Ana Sayfaya Dön" sinyalini yakala
        self.drawing_overlay.toolbar.returnToMainPage.connect(self._handle_return_to_main_page)

    def _toggle_full_screen_mode(self):
        """
        Tam ekran çizim modunu açar veya kapatır.
        """
        if self.full_screen_button.isChecked():
            self._hide_all_windows_temporarily() # Tüm pencereleri geçici olarak gizle
            # Kısa bir gecikme ile ekran görüntüsünü al ve katmanı göster
            QTimer.singleShot(100, self._capture_full_screen_and_show_overlay)
            self.full_screen_button.setText("Tam Ekran Çizim Modunu Kapat")
        else:
            self._handle_return_to_main_page() # Modu kapatırken ana sayfaya dönme işlevini çağır

    def _capture_full_screen_and_show_overlay(self):
        """
        Ekran görüntüsünü alır ve çizim katmanını tam ekran modunda gösterir.
        """
        screen = QApplication.primaryScreen()
        screenshot = screen.grabWindow(0) # Tüm ekranın görüntüsünü al
        self.drawing_overlay.set_full_screen_mode(screenshot) # Katmanı ayarla
        self.drawing_overlay.showFullScreen() # Katmanı tam ekran göster
        self.drawing_overlay.set_drawing_mode(True) # Çizim modunu etkinleştir
        self.drawing_overlay.toolbar.show() # Araç çubuğunu göster
        self.show() # Ana pencereyi tekrar göster (çizim katmanı üzerinde)

    def _initiate_partial_screenshot(self):
        """
        Kısmi ekran görüntüsü alma modunu başlatır.
        """
        self._hide_all_windows_temporarily() # Tüm pencereleri geçici olarak gizle
        # SelectionAreaWidget'ı oluştur ve sinyalini bağla
        self.selection_widget = SelectionAreaWidget()
        self.selection_widget.selectionFinished.connect(self._handle_partial_screenshot_selection)
        self.selection_widget.showFullScreen() # Seçim widget'ını tam ekran göster

    def _handle_partial_screenshot_selection(self, rect: QRect, is_cancelled: bool):
        """
        Kısmi ekran görüntüsü seçimi tamamlandığında veya iptal edildiğinde çalışır.
        """
        if self.selection_widget:
            self.selection_widget.close() # Seçim widget'ını kapat
            self.selection_widget = None # Referansı sıfırla

        if is_cancelled or rect.isEmpty() or not rect.isValid():
            # Seçim iptal edildi veya geçersiz bir alan seçildi
            QMessageBox.information(self, "Bilgi", "Kısmi ekran görüntüsü seçimi iptal edildi.")
            self.show() # Ana pencereyi tekrar göster
            self.full_screen_button.setChecked(False) # Tam ekran butonu durumunu sıfırla
            return

        screen = QApplication.primaryScreen()
        # Seçilen bölgenin ekran görüntüsünü al
        partial_screenshot = screen.grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height())

        self.drawing_overlay.set_partial_screen_mode(partial_screenshot, rect) # Kısmi modu ayarla
        self.drawing_overlay.showFullScreen() # Çizim katmanını tam ekran göster
        self.drawing_overlay.set_drawing_mode(True) # Çizim modunu etkinleştir
        self.drawing_overlay.toolbar.show() # Araç çubuğunu göster
        self.show() # Ana pencereyi tekrar göster (çizim katmanı üzerinde)
        self.full_screen_button.setChecked(False) # Tam ekran butonu durumunu sıfırla

    def _handle_return_to_main_page(self):
        """
        Çizim katmanından ana sayfaya dönme isteği geldiğinde çalışır.
        Tüm çizim ve araç çubuğu görünümlerini gizler ve ana pencereyi gösterir.
        """
        self.drawing_overlay.hide()
        self.drawing_overlay.toolbar.hide()
        self.drawing_overlay.set_drawing_mode(False) # Çizim modunu devre dışı bırak ve çizimleri temizle
        self.full_screen_button.setChecked(False) # Tam ekran butonunun işaretini kaldır
        self.show() # Ana pencereyi göster

    def _hide_all_windows_temporarily(self):
        """
        Tüm uygulama pencerelerini ekran görüntüsü alma veya seçim sırasında geçici olarak gizler.
        """
        self.hide()
        self.drawing_overlay.hide()
        self.drawing_overlay.toolbar.hide()
        QApplication.processEvents() # Olay kuyruğunu işle, gizlemenin hemen gerçekleşmesini sağlar

    def close_application(self):
        """
        Uygulamayı tamamen kapatır.
        """
        self.drawing_overlay.close()
        self.drawing_overlay.toolbar.close()
        # Eğer selection_widget açıksa onu da kapat
        if self.selection_widget and self.selection_widget.isVisible():
            self.selection_widget.close()
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())

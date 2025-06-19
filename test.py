import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QColorDialog, QSlider, QFrame, QLabel, QToolButton, QSizePolicy
)
from PyQt5.QtGui import QPainter, QPen, QColor, QScreen, QPixmap, QIcon
from PyQt5.QtCore import Qt, QPoint, QSize, QByteArray, QRectF  # QByteArray ve QRectF eklendi

# QtSvg modülünü içe aktarın
try:
    from PyQt5.QtSvg import QSvgRenderer
except ImportError:
    # Eğer QtSvg kurulu değilse, bir uyarı gösterin ve ikonlar yerine metin kullanın.
    print("Uyarı: PyQt5.QtSvg modülü bulunamadı. Lütfen 'pip install PyQt5.QtSvg' komutuyla yükleyin.")
    print("İkonlar yerine buton metinleri kullanılacaktır.")
    QSvgRenderer = None  # QSvgRenderer'ı None olarak ayarla


# Gelişmiş Ekran Açıklama Uygulaması
class ScreenAnnotator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ekran Açıklama Uygulaması")  # Pencere başlığı
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # Arka planı tamamen şeffaf yap
        self.setWindowFlag(Qt.WindowTransparentForInput, True)  # Başlangıçta giriş olaylarını almaz

        self.drawing_mode = False  # Çizim modunun durumu
        self.drawing_history = []  # Yapılan tüm çizimlerin geçmişi (undo/redo için)
        self.redo_stack = []  # Geri alınan çizimlerin yığını

        self.current_line = []  # Mevcut çizilen çizgi
        self.current_tool = 'pen'  # Mevcut çizim aracı: 'pen', 'highlighter', 'eraser'
        self.current_color = QColor(255, 0, 0)  # Mevcut çizim rengi (kırmızı)
        self.current_thickness = 3  # Mevcut çizim kalınlığı

        self.init_ui()

    def init_ui(self):
        # Pencereyi tüm ekranı kaplayacak şekilde ayarla
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        self.setGeometry(screen_geometry)

        # Araç çubuğunu başlat ve ana pencerenin referansını ver
        self.toolbar = AnnotationToolbar(self)
        self.toolbar.show()

    def toggle_drawing_mode(self):
        self.drawing_mode = not self.drawing_mode
        if self.drawing_mode:
            # Çizim moduna girince, pencereye input olaylarının gelmesini sağla
            self.setWindowFlag(Qt.WindowTransparentForInput, False)
            self.show()  # Pencerenin en üstte kalmasını sağlamak için tekrar göster
            self.toolbar.hide()  # Araç çubuğunu gizle
            print("Çizim modu etkin.")
        else:
            # Çizim modundan çıkınca, pencereyi input olaylarına karşı tekrar şeffaf yap
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
            self.show()  # Değişiklikleri uygulamak için tekrar göster
            self.toolbar.show()  # Araç çubuğunu göster
            print("Çizim modu devre dışı.")

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        print(f"Araç değişti: {tool_name}")

    def set_color(self, color):
        self.current_color = color
        print(f"Renk değişti: {color.name()}")

    def set_thickness(self, thickness):
        self.current_thickness = thickness
        print(f"Kalınlık değişti: {thickness}")

    def clear_drawings(self):
        self.drawing_history.clear()
        self.redo_stack.clear()
        self.update()  # Ekranı yeniden çiz
        print("Çizimler temizlendi.")

    def undo_last_drawing(self):
        if self.drawing_history:
            last_drawing = self.drawing_history.pop()
            self.redo_stack.append(last_drawing)
            self.update()
            print("Son çizim geri alındı.")
        else:
            print("Geri alınacak çizim yok.")

    def redo_last_drawing(self):
        if self.redo_stack:
            last_undone = self.redo_stack.pop()
            self.drawing_history.append(last_undone)
            self.update()
            print("Son geri alınan çizim yinelendi.")
        else:
            print("Yinelenecek çizim yok.")

    def take_screenshot(self):
        screen = QApplication.primaryScreen()
        # Tüm ekranın görüntüsünü al
        pixmap = screen.grabWindow(QApplication.desktop().winId())

        # Kaydetme iletişim kutusu göster
        # QMessageBox.question yerine doğrudan QFileDialog kullanmak daha uygun olacaktır
        # Kullanıcı 'Save' seçeneğini seçtiğinde otomatik olarak dosya kaydetme penceresi açılmalı
        from PyQt5.QtWidgets import QFileDialog
        save_path, _ = QFileDialog.getSaveFileName(self, "Ekran Görüntüsünü Kaydet",
                                                   "screenshot.png", "PNG Dosyaları (*.png);;Tüm Dosyalar (*)")
        if save_path:
            pixmap.save(save_path)
            print(f"Ekran görüntüsü kaydedildi: {save_path}")
        else:
            print("Ekran görüntüsü kaydedilmedi.")

    def confirm_quit(self):
        # Uygulamadan çıkmadan önce onay kutusu göster
        reply = QMessageBox.question(self, 'Uygulamadan Çık',
                                     "Uygulamadan çıkmak istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.toolbar.close()  # Araç çubuğunu kapat
            QApplication.quit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)  # Kenarları yumuşat

        # Tüm geçmiş çizimleri çiz
        for drawing_info in self.drawing_history:
            points = drawing_info['points']
            color = drawing_info['color']
            thickness = drawing_info['thickness']
            tool = drawing_info['tool']

            if tool == 'eraser':
                # Silgi için CompositeMode_Clear kullan
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                pen = QPen(Qt.transparent, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                if tool == 'highlighter':
                    # Vurgulayıcı için yarı saydam renk
                    color.setAlpha(120)  # Yarı saydamlık ayarı
                    pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                else:  # 'pen' veya diğer araçlar
                    pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

            painter.setPen(pen)

            if len(points) > 1:
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

        # Mevcut çizilen çizgiyi çiz (fare hala basılıyken)
        if self.current_line:
            points = self.current_line
            color = self.current_color
            thickness = self.current_thickness
            tool = self.current_tool

            if tool == 'eraser':
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                pen = QPen(Qt.transparent, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                if tool == 'highlighter':
                    color_copy = QColor(color)  # Orijinal rengi koru
                    color_copy.setAlpha(120)
                    pen = QPen(color_copy, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                else:
                    pen = QPen(color, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)

            painter.setPen(pen)

            if len(points) > 1:
                for i in range(len(points) - 1):
                    painter.drawLine(points[i], points[i + 1])

        # Reset composition mode for future drawings
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def mousePressEvent(self, event):
        if self.drawing_mode and event.button() == Qt.LeftButton:
            self.current_line = [event.pos()]
            self.redo_stack.clear()  # Yeni bir çizime başlandığında redo stack'i temizle
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing_mode and event.buttons() & Qt.LeftButton:
            self.current_line.append(event.pos())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drawing_mode and event.button() == Qt.LeftButton:
            if self.current_line:
                # Çizimi geçmişe kaydet
                self.drawing_history.append({
                    'points': list(self.current_line),
                    'color': QColor(self.current_color),  # Renk kopyasını sakla
                    'thickness': self.current_thickness,
                    'tool': self.current_tool
                })
                self.current_line = []  # Mevcut çizgiyi sıfırla
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self.drawing_mode:
                self.toggle_drawing_mode()
            else:
                self.confirm_quit()


# Araç Çubuğu Sınıfı
class AnnotationToolbar(QWidget):
    def __init__(self, annotator_app):
        super().__init__()
        self.annotator_app = annotator_app  # Ana uygulamanın referansı
        self.setWindowTitle("Araç Çubuğu")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool  # Uygulama çubuğunda görünmesini engeller
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # Şeffaf arka plan
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(50, 50, 50, 200); /* Yarı şeffaf gri arka plan */
                border-radius: 10px;
            }
            QPushButton, QToolButton {
                background-color: #4CAF50; /* Yeşil */
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover, QToolButton:hover {
                background-color: #45a049;
            }
            QToolButton {
                min-width: 30px;
                min-height: 30px;
                font-size: 18px; /* İkonlar için daha büyük font */
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #888;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #fff;
                border: 1px solid #5C5C5C;
                width: 18px;
                margin: -2px 0;
                border-radius: 9px;
            }
        """)

        self.old_pos = None  # Sürükle-bırak için eski konum

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # İç kenar boşlukları
        main_layout.setSpacing(10)  # Öğeler arası boşluk

        # Üst kısım: Çizim Modu ve Çıkış
        top_row_layout = QHBoxLayout()
        self.toggle_button = QPushButton("Çizim Modunu Aç")
        self.toggle_button.clicked.connect(self.toggle_drawing_mode_and_hide_toolbar)
        top_row_layout.addWidget(self.toggle_button)

        self.quit_button = QPushButton("Çıkış")
        self.quit_button.clicked.connect(self.annotator_app.confirm_quit)
        top_row_layout.addWidget(self.quit_button)
        main_layout.addLayout(top_row_layout)

        # Araç Seçimi
        tool_layout = QHBoxLayout()
        tool_label = QLabel("Araçlar:")
        tool_label.setStyleSheet("color: white; font-weight: bold;")
        tool_layout.addWidget(tool_label)

        # Kalem (Pen) ikonu için SVG
        pen_icon = self.create_svg_icon("""<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12.9842 2.76672C13.5684 2.18241 14.5028 2.18241 15.087 2.76672L18.8988 6.5785C19.4831 7.16281 19.4831 8.09712 18.8988 8.68143L8.29342 19.2868C8.01639 19.5639 7.64731 19.7423 7.2474 19.8093L3.19532 20.4704C2.86877 20.5255 2.57018 20.2269 2.6253 19.9004L3.2864 15.8483C3.35341 15.4484 3.53183 15.0793 3.80887 14.8023L12.9842 2.76672Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16.9208 4.7928L19.2071 7.07908" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""")
        self.pen_button = QToolButton()
        self.pen_button.setIcon(pen_icon)
        self.pen_button.setIconSize(QSize(24, 24))
        self.pen_button.clicked.connect(lambda: self.annotator_app.set_tool('pen'))
        tool_layout.addWidget(self.pen_button)

        # Vurgulayıcı (Highlighter) ikonu için SVG
        highlighter_icon = self.create_svg_icon("""<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2Z" fill="rgba(255, 255, 0, 0.7)" stroke="white" stroke-width="2"/>
            <path d="M15 9L9 15" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>""")
        self.highlighter_button = QToolButton()
        self.highlighter_button.setIcon(highlighter_icon)
        self.highlighter_button.setIconSize(QSize(24, 24))
        self.highlighter_button.clicked.connect(lambda: self.annotator_app.set_tool('highlighter'))
        tool_layout.addWidget(self.highlighter_button)

        # Silgi (Eraser) ikonu için SVG
        eraser_icon = self.create_svg_icon("""<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M14 3L21 10L10 21L3 14L14 3Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 21L14 17" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 14L7 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>""")
        self.eraser_button = QToolButton()
        self.eraser_button.setIcon(eraser_icon)
        self.eraser_button.setIconSize(QSize(24, 24))
        self.eraser_button.clicked.connect(lambda: self.annotator_app.set_tool('eraser'))
        tool_layout.addWidget(self.eraser_button)

        main_layout.addLayout(tool_layout)

        # Renk Seçimi
        color_layout = QHBoxLayout()
        color_label = QLabel("Renk:")
        color_label.setStyleSheet("color: white; font-weight: bold;")
        color_layout.addWidget(color_label)

        self.color_button = QPushButton()
        self.color_button.setFixedSize(30, 30)
        self.color_button.setStyleSheet(
            f"background-color: {self.annotator_app.current_color.name()}; border: 2px solid white; border-radius: 5px;")
        self.color_button.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_button)
        main_layout.addLayout(color_layout)

        # Kalınlık Ayarı
        thickness_layout = QHBoxLayout()
        thickness_label = QLabel("Kalınlık:")
        thickness_label.setStyleSheet("color: white; font-weight: bold;")
        thickness_layout.addWidget(thickness_label)

        self.thickness_slider = QSlider(Qt.Horizontal)
        self.thickness_slider.setMinimum(1)
        self.thickness_slider.setMaximum(20)
        self.thickness_slider.setValue(self.annotator_app.current_thickness)
        self.thickness_slider.setTickPosition(QSlider.TicksBelow)
        self.thickness_slider.setTickInterval(1)
        self.thickness_slider.valueChanged.connect(self.annotator_app.set_thickness)
        thickness_layout.addWidget(self.thickness_slider)
        main_layout.addLayout(thickness_layout)

        # Aksiyon Butonları
        action_layout = QHBoxLayout()

        self.undo_button = QPushButton("Geri Al")
        self.undo_button.clicked.connect(self.annotator_app.undo_last_drawing)
        action_layout.addWidget(self.undo_button)

        self.redo_button = QPushButton("Yinele")
        self.redo_button.clicked.connect(self.annotator_app.redo_last_drawing)
        action_layout.addWidget(self.redo_button)

        self.clear_button = QPushButton("Temizle")
        self.clear_button.clicked.connect(self.annotator_app.clear_drawings)
        action_layout.addWidget(self.clear_button)

        self.screenshot_button = QPushButton("Ekran Görüntüsü Al")
        self.screenshot_button.clicked.connect(self.annotator_app.take_screenshot)
        action_layout.addWidget(self.screenshot_button)
        main_layout.addLayout(action_layout)

        # Düzenin boyutlandırma politikasını ayarla
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.adjustSize()  # İçeriğe göre boyutu ayarla

        # Pencereyi ekranın ortasına konumlandır
        screen_geometry = QApplication.primaryScreen().geometry()
        self.move(screen_geometry.width() // 2 - self.width() // 2, 50)  # Ekranın üst ortası

    def create_svg_icon(self, svg_data):
        if QSvgRenderer is None:
            # QSvgRenderer mevcut değilse boş bir ikon döndür
            # Veya butonların metnini doğrudan ayarlayabilirsiniz
            # self.pen_button.setText("Kalem") vb.
            return QIcon()  # Boş bir ikon döndür

        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)  # Şeffaf arka plan
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # QSvgRenderer'ı kullanarak SVG'yi QPixmap üzerine çizin
        renderer = QSvgRenderer(QByteArray(svg_data.encode('utf-8')))
        renderer.render(painter, QRectF(0, 0, 24, 24))
        painter.end()
        return QIcon(pixmap)

    def toggle_drawing_mode_and_hide_toolbar(self):
        self.annotator_app.toggle_drawing_mode()
        if self.annotator_app.drawing_mode:
            self.toggle_button.setText("Çizim Modunu Kapat")
            self.hide()  # Çizim moduna geçildiğinde araç çubuğunu gizle
        else:
            self.toggle_button.setText("Çizim Modunu Aç")
            self.show()  # Çizim modundan çıkıldığında araç çubuğunu göster

    def choose_color(self):
        color = QColorDialog.getColor(self.annotator_app.current_color, self, "Renk Seç")
        if color.isValid():
            self.annotator_app.set_color(color)
            self.color_button.setStyleSheet(
                f"background-color: {color.name()}; border: 2px solid white; border-radius: 5px;")

    # Araç çubuğunu sürüklemek için fare olayları
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    annotator = ScreenAnnotator()
    sys.exit(app.exec_())

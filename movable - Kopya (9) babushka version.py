import sys
import os
import traceback
import json
import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QComboBox, QMessageBox, QFrame, QPushButton, \
    QSlider, QFileDialog
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QTimer, QBuffer, QByteArray
from PyQt5.QtGui import QColor, QPen, QPainter, QImage, QPixmap, QCursor, QIcon

# Conditional import for Windows-specific modules
try:
    import win32api
    import win32con
    import win32gui
    from PIL import ImageGrab

    WIN_SPECIFIC_IMPORTS_AVAILABLE = True
except ImportError:
    WIN_SPECIFIC_IMPORTS_AVAILABLE = False
    print(
        "Warning: win32api, win32con, win32gui, or PIL not found. Windows-specific features (transparency, ImageGrab) will be disabled.")


def log_error(error_message, exception_info=None):
    """
    Kritik uygulama hatalarını bir günlük dosyasına kaydeder.
    """
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)  # logs klasörünü oluştur (varsaysa atla)

    log_file_path = os.path.join(log_dir, 'error_log.txt')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Hata: {error_message}\n")
        if exception_info:
            # traceback.format_exc() ile hatanın detaylı izini al
            f.write("Hata Detayı:\n")
            f.write(traceback.format_exc())
        f.write("-" * 50 + "\n\n")
    print(f"Hata günlüğe kaydedildi: {error_message}")


class CursorManager:
    """
    JSON dosyasından özel imleç görsellerini yükler ve QCursor nesneleri sağlar.
    """
    _cursors = {}  # Yüklenen QCursor nesnelerini saklamak için sınıf seviyesi sözlük
    _base_path = ""  # İmleç görsellerinin kök dizini

    @classmethod
    def set_base_path(cls, path):
        """İmleç görsellerinin bulunduğu temel yolu ayarlar."""
        cls._base_path = path

    @classmethod
    def load_cursors(cls, json_path):
        """
        Belirtilen JSON dosyasından imleç tanımlarını yükler ve QCursor nesneleri oluşturur.
        """
        if not cls._base_path:
            error_msg = "Hata: İmleç görselleri için temel yol ayarlanmadı. Lütfen CursorManager.set_base_path() çağırın."
            print(error_msg)
            log_error(error_msg)
            return

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                cursor_data = json.load(f)
                for key, cursor_info in cursor_data.items():
                    if isinstance(cursor_info, dict) and "image_path" in cursor_info:
                        image_file = os.path.join(cls._base_path, cursor_info["image_path"])
                        hotspot_x = cursor_info.get("hotspot_x", 0)
                        hotspot_y = cursor_info.get("hotspot_y", 0)
                        size = cursor_info.get("size", 24)  # Yeni: Boyut bilgisini al, varsayılan 24px

                        pixmap = QPixmap(image_file)
                        if not pixmap.isNull():
                            # Pixmap'ı belirtilen boyuta ölçeklendir
                            scaled_pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            cls._cursors[key] = QCursor(scaled_pixmap, hotspot_x, hotspot_y)
                            # print(f"İmleç yüklendi: {key} -> {image_file}, Boyut: {size}x{size}")
                        else:
                            error_msg = f"Uyarı: İmleç görseli yüklenemedi: {image_file} (Anahtar: {key}). Varsayılan ok kullanılacak."
                            print(error_msg)
                            log_error(error_msg)
                            cls._cursors[key] = QCursor(Qt.ArrowCursor)  # Yüklenemezse varsayılan
                    elif isinstance(cursor_info, str) and hasattr(Qt, cursor_info):
                        # Geriye dönük uyumluluk veya varsayılan Qt imleçleri için
                        cls._cursors[key] = QCursor(getattr(Qt, cursor_info))
                    else:
                        error_msg = f"Uyarı: Geçersiz imleç tanımı '{key}' JSON'da bulundu. Varsayılan ok kullanılacak."
                        print(error_msg)
                        log_error(error_msg)
                        cls._cursors[key] = QCursor(Qt.ArrowCursor)

                print(f"İmleçler '{json_path}' dosyasından başarıyla yüklendi.")
        except FileNotFoundError:
            error_msg = f"Hata: İmleç dosyası bulunamadı: {json_path}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
        except json.JSONDecodeError:
            error_msg = f"Hata: İmleç dosyası geçersiz JSON formatında: {json_path}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
        except Exception as e:
            error_msg = f"İmleçler yüklenirken bir hata oluştu: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    @classmethod
    def get_cursor(cls, cursor_name):
        """
        İsimle bir Qt QCursor nesnesi döndürür.
        Tanımsız ise varsayılan oku döndürür.
        """
        return cls._cursors.get(cursor_name, QCursor(Qt.ArrowCursor))  # Yüklenmemişse standart Qt oku


_SCRIPT_DIR = os.path.dirname(__file__)
_AUTO_SAVE_DRAWING_FILE = os.path.join(_SCRIPT_DIR, 'data', 'auto_saved_drawing.txt')


class Ui(QMainWindow):
    """
    Main application window that provides options to start painting,
    take full-screen screenshots, or select a region for drawing.
    """

    def __init__(self):
        super().__init__()

        # Construct paths
        script_dir = os.path.dirname(__file__)
        cursors_json_path = os.path.join(script_dir, 'data', 'cursors.json')
        cursors_images_path = os.path.join(script_dir, 'data')  # İmleç görsellerinin kök dizini (data klasörü)
        app_config_path = os.path.join(script_dir, 'data', 'app_config.json')

        # Load application configuration first
        self.app_config = self.load_app_config(app_config_path)
        if not self.app_config:
            error_msg = "Uygulama yapılandırma dosyası yüklenemedi veya eksik."
            QMessageBox.critical(self, "Hata", error_msg)
            log_error(error_msg)
            sys.exit(1)

        # CursorManager'a temel yolu ayarla
        CursorManager.set_base_path(cursors_images_path)
        # İmleçleri yükle
        CursorManager.load_cursors(cursors_json_path)

        # Uygulama simgesini ayarla
        self.set_application_icon(script_dir)  # app_config self.app_config'ten alınacak

        # Get UI file path from config
        ui_file_name = self.app_config.get("main_ui_file", "undockapp.ui")  # Varsayılan: undockapp.ui
        ui_path = os.path.join(script_dir, 'data', ui_file_name)

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            error_msg = f"UI dosyası bulunamadı: {ui_path}"
            QMessageBox.critical(self, "Hata", error_msg)
            log_error(error_msg)
            sys.exit(1)

        # Load the UI from the .ui file
        try:
            uic.loadUi(ui_path, self)
        except Exception as e:
            error_msg = f"UI dosyası '{ui_path}' yüklenirken hata oluştu: {e}"
            QMessageBox.critical(self, "UI Yükleme Hatası", error_msg)
            log_error(error_msg, sys.exc_info())
            sys.exit(1)

        # Apply custom styles for a translucent background and magenta border
        self.setStyleSheet("""
            QMainWindow {
                background-color: rgba(255, 255, 255, 200); /* Yarı saydam beyaz */
                border: 2px solid magenta;
                border-radius: 10px;
            }
        """)
        self.setAttribute(Qt.WA_TranslucentBackground)  # Enable translucent background
        self.setWindowFlags(Qt.WindowStaysOnTopHint)  # Keep window on top

        # Set initial window position from app_config.json
        main_pos = self.app_config.get("main_window_position")
        if main_pos:
            self.move(main_pos.get("x", 100), main_pos.get("y", 100))
        else:
            print("Warning: 'main_window_position' not found in app_config.json. Using default position.")
            log_error("'main_window_position' app_config.json'da bulunamadı.")

        # Connect buttons to their respective methods using object names from .ui file
        self.findChild(QPushButton, "quit").clicked.connect(self.close)
        self.findChild(QPushButton, "pen").clicked.connect(self.start_full_screen_paint)
        self.findChild(QPushButton, "ss").clicked.connect(self.open_region_selector)
        self.findChild(QPushButton, "eraser").clicked.connect(self.close)

        # --- KALEM RENKLERİNİ app_config.json'dan DİNAMİK YÜKLEME ---
        self.load_pen_colors_from_config()
        # --- KALEM RENKLERİNİ DİNAMİK YÜKLEME SONU ---

        # Default drawing properties
        self.active_color = QColor(Qt.red)  # Başlangıç rengi ilk renk olabilir veya varsayılan
        if self.app_config and "pen_colors" in self.app_config and self.app_config["pen_colors"]:
            self.active_color = QColor(self.app_config["pen_colors"][0])  # İlk rengi başlangıç rengi yap
        else:
            self.active_color = QColor(Qt.red)  # Eğer renkler yapılandırmada yoksa varsayılan kırmızı

        self.active_size = 5
        self.hwnd = None  # Window handle for win32 transparency

        # Get references to UI elements for color indicator and size combo box
        self.color_indicator = self.findChild(QLabel, "colorIndicator")
        self.size_combo = self.findChild(QComboBox, "sizeCombo")

        # Initialize color indicator and size combo box
        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {self.active_color.name()}; border-radius: 5px;")

        if self.size_combo:
            self.size_combo.addItems(["1px", "3px", "5px", "7px", "10px", "15px", "20px"])
            self.size_combo.setCurrentIndex(2)  # Default to 5px
            self.size_combo.currentIndexChanged.connect(self.set_size)

    def load_pen_colors_from_config(self):
        """
        Loads pen colors from app_config.json and connects them to buttons.
        """
        if self.app_config and "pen_colors" in self.app_config:
            colors = self.app_config["pen_colors"]
            # Clear existing color buttons if any (though for .ui, they are usually fixed)
            # Find the layout containing your color buttons
            # Assuming your color buttons are directly under Ui or a specific layout
            # For this example, we'll iterate through predefined names like "color_red", "color_blue" etc.
            # If you want truly dynamic buttons, you'd need a QGridLayout and add buttons programmatically.

            # Iterate through the first few color buttons defined in your .ui file
            # and assign them colors from the config.
            # This is a fixed mapping. For more dynamic, you'd generate buttons.
            color_button_names = ["color_red", "color_blue", "color_black", "color_green",
                                  "color_custom1", "color_custom2"]  # Add more as needed based on your .ui

            for i, color_str in enumerate(colors):
                if i < len(color_button_names):
                    btn = self.findChild(QPushButton, color_button_names[i])
                    if btn:
                        try:
                            q_color = QColor(color_str)
                            if q_color.isValid():
                                btn.setStyleSheet(
                                    f"background-color: {color_str}; border-radius: 5px; border: 1px solid gray;")
                                btn.clicked.disconnect()  # Disconnect previous connection if any
                                btn.clicked.connect(lambda checked, c=q_color: self.set_color(c))
                                btn.show()  # Make sure the button is visible
                            else:
                                print(f"Uyarı: Geçersiz renk değeri '{color_str}' app_config.json'da bulundu.")
                                log_error(f"Geçersiz renk değeri app_config.json'da: {color_str}")
                                if btn: btn.hide()  # Hide button if color is invalid
                        except Exception as e:
                            print(f"Renk butonu ayarlanırken hata oluştu: {color_str} - {e}")
                            log_error(f"Renk butonu ayarlanırken hata: {color_str} - {e}", sys.exc_info())
                            if btn: btn.hide()  # Hide button on error
                    else:
                        print(f"Uyarı: {color_button_names[i]} isimli buton UI dosyasında bulunamadı.")
                else:
                    print(f"Bilgi: app_config.json'da tanımlanan tüm renkler için yeterli buton mevcut değil.")
        else:
            print("Uyarı: 'pen_colors' anahtarı app_config.json'da bulunamadı. Varsayılan renkler kullanılacak.")
            log_error("app_config.json'da 'pen_colors' anahtarı bulunamadı.")

    def load_app_config(self, config_path):
        """
        Loads application configuration from the specified JSON file.
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return config_data
        except FileNotFoundError:
            error_msg = f"Hata: Uygulama yapılandırma dosyası bulunamadı: {config_path}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            return None
        except json.JSONDecodeError:
            error_msg = f"Hata: Uygulama yapılandırma dosyası geçersiz JSON formatında: {config_path}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            return None
        except Exception as e:
            error_msg = f"Uygulama yapılandırması yüklenirken bir hata oluştu: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            return None

    def set_application_icon(self, base_dir):
        """
        Loads the application icon based on the app_config data.
        """
        try:
            icon_path_relative = self.app_config.get("app_icon_path")
            if icon_path_relative:
                full_icon_path = os.path.join(base_dir, icon_path_relative)
                if os.path.exists(full_icon_path):
                    self.setWindowIcon(QIcon(full_icon_path))
                    print(f"Uygulama simgesi yüklendi: {full_icon_path}")
                else:
                    error_msg = f"Uyarı: Uygulama simgesi bulunamadı: {full_icon_path}"
                    print(error_msg)
                    log_error(error_msg)
            else:
                print("Uyarı: 'app_icon_path' yapılandırma dosyasında bulunamadı.")
        except Exception as e:
            error_msg = f"Uygulama simgesi ayarlanırken hata oluştu: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def open_region_selector(self):
        """Hides the main window and opens the region selection tool."""
        try:
            self.hide()  # Hide the main window, do not close it
            self.selector = RegionSelector(self.active_color, self.active_size, self)  # Pass main window reference
            self.selector.showFullScreen()
        except Exception as e:
            error_msg = f"Bölge seçici açılırken hata oluştu: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            self.show()  # Hata olursa ana pencereyi tekrar göster

    def showEvent(self, event):
        """Event handler for when the window is shown. Sets up transparency."""
        super().showEvent(event)
        # Get the native window handle (HWND) for Windows-specific operations
        self.hwnd = int(self.winId())
        self.setup_window_transparency()

    def setup_window_transparency(self):
        """Applies Windows-specific transparency settings if available."""
        if not WIN_SPECIFIC_IMPORTS_AVAILABLE or not self.hwnd:
            return

        try:
            # Get current extended window style
            ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            # Add WS_EX_LAYERED style for transparency
            ex_style |= win32con.WS_EX_LAYERED
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex_style)
            # Set Fuchsia color (RGB(255, 0, 128)) as transparent key
            win32gui.SetLayeredWindowAttributes(
                self.hwnd,
                win32api.RGB(255, 0, 128),
                0,  # Alpha value (not used with LWA_COLORKEY)
                win32con.LWA_COLORKEY  # Use color key transparency
            )
        except Exception as e:
            error_msg = f"Şeffaflık ayarlanamadı: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def set_color(self, color):
        """Sets the active drawing color and updates the color indicator."""
        try:
            self.active_color = color
            if self.color_indicator:
                self.color_indicator.setStyleSheet(f"background-color: {color.name()}; border-radius: 5px;")
        except Exception as e:
            error_msg = f"Renk ayarlama hatası: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def set_size(self, index):
        """Sets the active brush size based on the combo box selection."""
        try:
            sizes = [1, 3, 5, 7, 10, 15, 20]
            if 0 <= index < len(sizes):
                self.active_size = sizes[index]
            else:
                error_msg = f"Geçersiz fırça boyutu indeksi: {index}"
                print(error_msg)
                log_error(error_msg)
        except Exception as e:
            error_msg = f"Fırça boyutu ayarlama hatası: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def start_full_screen_paint(self):
        """Hides the main window and starts a full-screen paint session."""
        try:
            self.hide()
            screenshot = self._capture_screenshot_pixmap()
            if screenshot:
                try:
                    self.paint_window = PaintCanvasWindow(
                        screenshot,
                        self.active_color,
                        self.active_size,
                        self  # Pass main window reference
                    )
                    self.paint_window.showFullScreen()
                except Exception as e:
                    error_msg = f"Tam ekran çizim penceresi oluşturulurken hata oluştu: {e}"
                    print(error_msg)
                    log_error(error_msg, sys.exc_info())
                    self.show()  # Show main window if paint window fails
            else:
                self.show()  # Show main window if screenshot fails
        except Exception as e:
            error_msg = f"Tam ekran boyama başlatılırken genel hata: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            self.show()

    def _capture_screenshot_pixmap(self):
        """
        Captures a full-screen screenshot as a QPixmap.
        Handles platform-specific screenshotting.
        """
        try:
            screen = QApplication.primaryScreen()
            # Use grabWindow for entire screen (root window ID 0)
            pixmap = screen.grabWindow(0)

            # Resize to a max resolution for performance if it's too large
            screen_rect = screen.geometry()
            max_width = 1920
            max_height = 1080

            # Only scale down if current pixmap is larger than the max resolution
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(QSize(max_width, max_height),
                                       Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
            return pixmap
        except Exception as e:
            error_msg = f"Ekran görüntüsü alınamadı: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            QMessageBox.critical(self, "Ekran Görüntüsü Hatası", "Ekran görüntüsü alınamadı.")
            return None


class RegionSelector(QWidget):
    """
    Allows the user to select a rectangular region on the screen for screenshotting.
    """

    def __init__(self, brush_color, brush_size, main_window_ref):  # Get main window reference
        super().__init__()
        self.brush_color = brush_color
        self.brush_size = brush_size
        self.main_window_ref = main_window_ref  # Store the reference

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.3)  # Translucent overlay
        self.setStyleSheet("background-color: gray;")
        self.begin = QPoint()
        self.end = QPoint()
        # İmleci CursorManager'dan çekiyoruz
        self.setCursor(CursorManager.get_cursor("region_select"))

        # Set geometry to cover the primary screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def mousePressEvent(self, event):
        """Records the starting point of the selection."""
        try:
            if event.button() == Qt.LeftButton:
                self.begin = event.pos()
                self.end = event.pos()
                self.update()  # Trigger repaint to show initial selection rectangle
        except Exception as e:
            log_error(f"RegionSelector mousePressEvent hatası: {e}", sys.exc_info())

    def mouseMoveEvent(self, event):
        """Updates the end point of the selection as the mouse moves."""
        try:
            if event.buttons() & Qt.LeftButton:  # Only if left button is held down
                self.end = event.pos()
                self.update()  # Trigger repaint to update the rectangle
        except Exception as e:
            log_error(f"RegionSelector mouseMoveEvent hatası: {e}", sys.exc_info())

    def mouseReleaseEvent(self, event):
        """
        Finalizes the selection, closes the selector, and opens the paint window
        with the cropped screenshot.
        """
        try:
            if event.button() == Qt.LeftButton:
                self.close()  # Close the selector window

                x1 = min(self.begin.x(), self.end.x())
                y1 = min(self.begin.y(), self.end.y())
                x2 = max(self.begin.x(), self.end.x())
                y2 = max(self.begin.y(), self.end.y())
                self.selected_rect = QRect(x1, y1, x2 - x1, y2 - y1)

                if self.selected_rect.width() > 0 and self.selected_rect.height() > 0:
                    self.capture_and_open_paint()
                else:
                    # If no valid region selected (e.g., zero width/height), just go back to main window
                    if self.main_window_ref:
                        self.main_window_ref.show()  # Show the original main window
                    self.close()  # Close RegionSelector
        except Exception as e:
            log_error(f"RegionSelector mouseReleaseEvent hatası: {e}", sys.exc_info())

    def paintEvent(self, event):
        """Draws the transparent gray overlay and the red selection rectangle."""
        try:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.drawRect(QRect(self.begin, self.end))
        except Exception as e:
            log_error(f"RegionSelector paintEvent hatası: {e}", sys.exc_info())

    def capture_and_open_paint(self):
        """Captures the selected region and opens the paint window."""
        try:
            screen = QApplication.primaryScreen()
            # Grab only the selected portion of the screen
            pixmap = screen.grabWindow(0, self.selected_rect.x(), self.selected_rect.y(),
                                       self.selected_rect.width(), self.selected_rect.height())

            # Open PaintCanvasWindow with the selected region screenshot
            paint_window = PaintCanvasWindow(pixmap, self.brush_color, self.brush_size,
                                             self.main_window_ref)  # Pass main window reference
            paint_window.show()
        except Exception as e:
            error_msg = f"Bölge yakalama veya çizim penceresi açılamadı: {e}"
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            QMessageBox.critical(self, "Hata", "Bölge yakalama veya çizim penceresi açılamadı.")
            # Reopen main UI if something goes wrong
            if self.main_window_ref:
                self.main_window_ref.show()  # Show the original main window


class PaintCanvasWindow(QMainWindow):
    """
    A window that displays a screenshot and allows the user to draw on it
    with various tools (pen, eraser, shapes, highlighter).
    It also hosts the ToolWindow.
    """

    def __init__(self, background_pixmap, initial_brush_color, initial_brush_size,
                 main_window_ref):  # Get main window reference
        super().__init__()
        self.setWindowTitle("Taşınabilir Görsel ve Çizim Alanı")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.main_window_ref = main_window_ref  # Store the reference

        # Store a copy of the background pixmap
        self.background_pixmap = background_pixmap.copy()

        # Get screen dimensions for fullscreen behavior
        screen_rect = QApplication.primaryScreen().geometry()
        # Set the window to full screen.
        self.setGeometry(screen_rect)  # This makes the canvas cover the whole screen.

        # Calculate initial position to center the background pixmap on the full screen canvas
        # This is the actual position of the image within this window.
        self.image_pos = QPoint(
            int((screen_rect.width() - self.background_pixmap.width()) / 2),
            int((screen_rect.height() - self.background_pixmap.height()) / 2)
        )

        # Create an empty overlay image to draw on. Its size matches the window size.
        # Her zaman boş bir tuvalle başla
        self.overlay_image = QImage(self.size(), QImage.Format_ARGB32)
        self.overlay_image.fill(Qt.transparent)

        # --- Undo/Redo için eklenenler ---
        self.undo_stack = []
        self.undo_index = -1

        # Başlangıçtaki boş tuval durumunu kaydet (sadece bir kez, pencere ilk açıldığında)
        # Bu, undo yığınının ilk boş haliyle başlamasını sağlar
        self.save_drawing_state()
        print("DEBUG: PaintCanvasWindow başlatıldı, boş tuvalle başlandı.")

        # --- Undo/Redo için eklenenler SONU ---

        # Drawing properties
        self.brush_color = initial_brush_color
        self.brush_size = initial_brush_size
        self.active_tool = "pen"  # Default tool
        self.eraser_size = 20  # Silgi için başlangıç boyutu, kalemden ayrı tutulacak

        self.drawing = False  # Flag to indicate if drawing is active
        self.moving_image = False  # Flag to indicate if image is being moved
        self.space_pressed = False  # Flag for spacebar (hand tool)

        # Resizing specific attributes
        self.resizing = False
        self.resize_anchor = None  # e.g., 'bottom_right'
        self.resize_handle_size = 10  # pixels for the resize handle
        self.original_pixmap_size = QSize()  # Stores initial size when resizing starts
        self.current_preview_rect = QRect()  # Stores the rectangle for resize preview

        self.last_point = QPoint()  # Last point for continuous drawing (pen/eraser)
        self.temp_start_point = QPoint()  # Start point for shape tools (line, rect, ellipse)
        self.temp_end_point = QPoint()  # End point for shape tools

        self.drag_offset = QPoint()  # Offset for dragging the image

        self.painter = None  # Initialize painter for continuous drawing

        # Create move image button
        self.move_image_btn = QPushButton("Görseli Taşı", self)
        self.move_image_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(100, 100, 100, 150); /* Semi-transparent dark gray */
                color: white;
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(120, 120, 120, 180);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 200);
            }
        """)
        # Connect to a new method that handles the button text change
        self.move_image_btn.clicked.connect(self._toggle_move_tool)
        self.move_image_btn.setFixedSize(120, 30)

        # Determine button visibility: If it's a full-screen screenshot, the move button is less useful.
        # It's primarily for cropped images within a larger drawing area.
        if self.background_pixmap.isNull() or (self.background_pixmap.size() == screen_rect.size()):
            self.move_image_btn.hide()
        else:
            self.move_image_btn.show()
            # Calculate the position above the center of the image's top edge
            button_width = self.move_image_btn.width()
            image_width = self.background_pixmap.width()
            image_x = self.image_pos.x()
            image_y = self.image_pos.y()

            button_x = image_x + (image_width - button_width) // 2
            button_y = image_y - self.move_image_btn.height() - 10  # 10px above the top top edge

            self.move_image_btn.move(button_x, button_y)

        # Initialize and show the tool window
        self.tool_window = ToolWindow(self, self.main_window_ref.app_config)  # app_config'i ToolWindow'a ilet
        self.tool_window.show()

        # Position tool window using offsets from app_config.json
        tool_pos_config = self.main_window_ref.app_config.get("tool_window_position")
        if tool_pos_config:
            x_offset = tool_pos_config.get("x_offset_from_paint_window", 0)
            y_offset = tool_pos_config.get("y_offset_from_paint_window", 0)

            # Position tool window relative to the paint window
            # Default: top-right corner of paint window, then apply offset
            self.tool_window.move(
                self.x() + self.width() - self.tool_window.width() + x_offset,
                self.y() + y_offset
            )
        else:
            print("Warning: 'tool_window_position' not found in app_config.json. Using default positioning.")
            log_error("'tool_window_position' app_config.json'da bulunamadı.")
            # Fallback to default positioning if config is missing
            self.tool_window.move(self.x() + self.width() - self.tool_window.width() - 20, self.y() + 20)

        # Ensure the tool window's selected color indicator is updated on init
        self.tool_window.set_selected_color_indicator(self.brush_color)

    def _toggle_move_tool(self):
        """Toggles the move tool on/off and updates the button text."""
        try:
            if self.active_tool == "move":
                self.set_tool("pen")  # Switch back to pen
            else:
                self.set_tool("move")  # Activate move tool
        except Exception as e:
            log_error(f"Görsel taşıma aracı değiştirilirken hata: {e}", sys.exc_info())

    def set_tool(self, tool):
        """Sets the active drawing tool and updates the move button text."""
        try:
            self.active_tool = tool
            # Update cursor based on tool
            if tool == "move":
                self.setCursor(CursorManager.get_cursor("move_active"))  # JSON'dan imleç çek
                self.move_image_btn.setText("Görsel Taşınıyor")  # Update button text
            elif tool in ["pen", "eraser", "highlight", "line", "rect", "ellipse"]:
                self.setCursor(CursorManager.get_cursor(tool))  # JSON'dan imleç çek (tool ismiyle aynı anahtar)
                self.move_image_btn.setText("Görseli Taşı")  # Reset button text
            else:
                self.setCursor(CursorManager.get_cursor("default"))  # Varsayılan imleç
                self.move_image_btn.setText("Görseli Taşı")  # Reset button text
        except Exception as e:
            log_error(f"Araç ayarlanırken hata: {e}", sys.exc_info())

    def set_brush_color(self, color):
        """Sets the current brush color and updates the tool window's indicator."""
        try:
            self.brush_color = color
            # Update the selected color indicator in the tool window
            if self.tool_window:
                self.tool_window.set_selected_color_indicator(color)
        except Exception as e:
            log_error(f"Fırça rengi ayarlanırken hata: {e}", sys.exc_info())

    def set_brush_size(self, size):
        """Sets the current brush size (for pen and shapes)."""
        try:
            self.brush_size = size
        except Exception as e:
            log_error(f"Fırça boyutu ayarlanırken hata: {e}", sys.exc_info())

    def set_eraser_size(self, size):
        """Sets the current eraser size."""
        try:
            self.eraser_size = size
        except Exception as e:
            log_error(f"Silgi boyutu ayarlanırken hata: {e}", sys.exc_info())

    def clear_all_drawings(self):
        """Çizim katmanındaki tüm çizimleri temizler ve geri alma/yineleme yığınını sıfırlar."""
        try:
            self.overlay_image.fill(Qt.transparent)  # Çizim katmanını şeffaf renkle doldur
            self.save_drawing_state()  # Yeni boş durumu kaydet (bu otomatik kaydetmeyi de tetikler)
            self.update()  # Tuvalin temizlendiğini göstermek için yeniden boyama iste
        except Exception as e:
            log_error(f"Çizimleri temizlerken hata: {e}", sys.exc_info())

    def save_drawing_state(self):
        """Çizim katmanının mevcut durumunu geri alma yığınına kaydeder ve otomatik olarak dosyaya kaydeder."""
        try:
            # Mevcut indeksin ötesindeki tüm durumları sil
            while len(self.undo_stack) > self.undo_index + 1:
                self.undo_stack.pop()

            # overlay_image'ın derin kopyasını al
            copied_image = QImage(self.overlay_image.size(), self.overlay_image.format())
            painter = QPainter(copied_image)
            painter.drawImage(0, 0, self.overlay_image)
            painter.end()

            self.undo_stack.append(copied_image)
            self.undo_index = len(self.undo_stack) - 1
            # print(f"Durum kaydedildi. Stack boyutu: {len(self.undo_stack)}, Index: {self.undo_index}")

            # Otomatik kaydetme işlemini de burada yap
            self._save_current_drawing_auto()

        except Exception as e:
            log_error(f"Çizim durumu kaydedilirken hata: {e}", sys.exc_info())

    def undo_drawing(self):
        """Son çizim eylemini geri alır."""
        try:
            if self.undo_index > 0:
                self.undo_index -= 1
                self.overlay_image = self.undo_stack[self.undo_index]
                self.update()
                self._save_current_drawing_auto()  # Undo sonrası otomatik kaydet
            else:
                print("Geri alınacak başka çizim yok.")
        except Exception as e:
            log_error(f"Geri alma işlemi sırasında hata: {e}", sys.exc_info())

    def redo_drawing(self):
        """Geri alınan son çizim eylemini tekrar yapar."""
        try:
            if self.undo_index < len(self.undo_stack) - 1:
                self.undo_index += 1
                self.overlay_image = self.undo_stack[self.undo_index]
                self.update()
                self._save_current_drawing_auto()  # Redo sonrası otomatik kaydet
            else:
                print("İleri alınacak başka çizim yok.")
        except Exception as e:
            log_error(f"İleri alma işlemi sırasında hata: {e}", sys.exc_info())

    def set_overlay_image(self, image: QImage):
        """Harici olarak yüklenen bir QImage'ı çizim katmanı olarak ayarlar."""
        try:
            # Explicitly make a deep copy to ensure independent memory management
            # and to prevent issues if the 'image' argument is temporary.
            self.overlay_image = QImage(image)
            # Yüklendikten sonra undo stack'i sıfırla ve yeni görüntüyü ilk durum olarak ekle
            self.undo_stack = [QImage(self.overlay_image)]  # Use the newly copied overlay_image for the stack
            self.undo_index = 0

            self.update()  # Yeni görüntüyü ekranda göstermek için güncelleme iste
            self._save_current_drawing_auto()  # Yeni çizim yüklendikten sonra otomatik kaydet
        except Exception as e:
            log_error(f"Çizim katmanı görüntüsü ayarlanırken hata: {e}", sys.exc_info())

    def _save_current_drawing_auto(self):
        """
        Mevcut çizimi (overlay_image) Base64 kodlu PNG string olarak
        önceden tanımlanmış otomatik kayıt dosyasına kaydeder.
        """
        try:
            # Dosya dizininin var olduğundan emin olun
            os.makedirs(os.path.dirname(_AUTO_SAVE_DRAWING_FILE), exist_ok=True)

            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            self.overlay_image.save(buffer, "PNG")
            png_data = buffer.data()
            buffer.close()

            base64_data = png_data.toBase64().data().decode('utf-8')

            # Efficiently check if the image contains any visible (non-transparent) pixels
            has_visible_content = False
            # Check if the image format allows direct byte access for alpha channel check
            if not self.overlay_image.isNull() and self.overlay_image.format() == QImage.Format_ARGB32:
                # Access raw bytes for faster check (assuming ARGB32 format, a,r,g,b)
                # Note: constBits() returns a sip.voidptr, which needs to be converted to bytes
                # using asarray() to be iterable and check byte values.
                # The total size in bytes is width * height * bytes_per_pixel (4 for ARGB32).
                byte_array = self.overlay_image.constBits().asarray(
                    self.overlay_image.width() * self.overlay_image.height() * 4)
                # Check the alpha byte (index 3 for each pixel in ARGB32)
                for i in range(0, len(byte_array), 4):
                    if byte_array[i + 3] != 0:  # If alpha is not 0 (fully transparent)
                        has_visible_content = True
                        break
            elif not self.overlay_image.isNull() and not self.overlay_image.hasAlphaChannel():
                # If no alpha channel, it's implicitly opaque (e.g., RGB888), so assume it has visible content.
                # A more thorough check would be to examine pixel values for non-zero colors, but for a quick check,
                # if it's not null and no alpha channel, it likely has visible content.
                has_visible_content = True
            elif not self.overlay_image.isNull():  # General fallback for other formats
                # If the image is not null and we couldn't check its alpha channel specifically,
                # we can make a heuristic guess: if the PNG data is significantly larger than a minimal empty PNG,
                # it probably contains something. A minimal transparent PNG is usually very small (around 60-70 bytes).
                if len(png_data) > 100:  # This threshold can be adjusted based on minimal empty PNG size
                    has_visible_content = True

            print(f"DEBUG: Saved overlay_image contains visible content: {has_visible_content}")
            print(
                f"DEBUG: Otomatik kaydedildi. Resim Boyutu: {self.overlay_image.size().width()}x{self.overlay_image.size().height()}, Base64 Uzunluğu: {len(base64_data)}")

            with open(_AUTO_SAVE_DRAWING_FILE, 'w', encoding='utf-8') as f:
                f.write(base64_data)
        except Exception as e:
            log_error(f"Otomatik çizim kaydedilirken hata: {e}", sys.exc_info())

    def mousePressEvent(self, event):
        """Handles mouse press events for drawing, moving, and resizing the image."""
        try:
            # Check for resize handle interaction first
            image_rect = QRect(self.image_pos, self.background_pixmap.size())
            br_handle = QRect(
                image_rect.bottomRight() - QPoint(self.resize_handle_size, self.resize_handle_size),
                QSize(self.resize_handle_size, self.resize_handle_size)
            )

            if br_handle.contains(event.pos()) and not self.background_pixmap.isNull():
                self.resizing = True
                self.resize_anchor = 'bottom_right'
                self.original_pixmap_size = self.background_pixmap.size()
                self.setCursor(CursorManager.get_cursor("resize_br"))  # JSON'dan imleç çek
                return

            # Check for image move interaction
            # Only consider image handle area if not already resizing
            image_handle_area = QRect(self.image_pos, QSize(self.background_pixmap.width(), 30))  # 30px handle at top
            if image_handle_area.contains(event.pos()) and not self.background_pixmap.isNull():
                self.moving_image = True
                self.drag_offset = event.pos() - self.image_pos
                self.setCursor(CursorManager.get_cursor("move_active"))  # JSON'dan imleç çek
                return  # Stop here if image is being moved

            # If not resizing or moving, proceed with drawing logic
            if event.button() == Qt.LeftButton:
                if self.space_pressed or self.active_tool == "move":
                    # Check if the click is within the current image bounds for dragging
                    # Important: check against the current image_pos, not always (0,0)
                    image_rect = QRect(self.image_pos, self.background_pixmap.size())
                    if image_rect.contains(event.pos()):
                        self.moving_image = True
                        self.drag_offset = event.pos() - self.image_pos
                        self.setCursor(CursorManager.get_cursor("move_active"))  # JSON'dan imleç çek
                else:  # Drawing initiated
                    self.drawing = True
                    self.last_point = event.pos()  # These are now always window-relative
                    self.temp_start_point = event.pos()  # These are now always window-relative

                    # Start QPainter for continuous drawing (pen, eraser, highlight)
                    if self.active_tool in ["pen", "eraser", "highlight"]:
                        self.painter = QPainter(self.overlay_image)
                        self.painter.begin(self.overlay_image)  # Explicitly begin painting
                        if self.active_tool == "eraser":
                            self.painter.setCompositionMode(QPainter.CompositionMode_Clear)
                            # Silgi kalınlığı için self.eraser_size kullan
                            pen = QPen(Qt.transparent, self.eraser_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        elif self.active_tool == "highlight":
                            self.painter.setCompositionMode(QPainter.CompositionMode_Screen)
                            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        else:  # Pen
                            self.painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        self.painter.setPen(pen)

        except Exception as e:
            log_error(f"PaintCanvasWindow mousePressEvent hatası: {e}", sys.exc_info())

    def mouseMoveEvent(self, event):
        """Handles mouse move events for drawing, moving, and resizing the image."""
        try:
            if self.resizing and self.resize_anchor == 'bottom_right':
                # Calculate new size based on mouse position relative to image_pos
                new_width = event.pos().x() - self.image_pos.x()
                new_height = event.pos().y() - self.image_pos.y()

                # Ensure minimum size
                new_width = max(10, new_width)
                new_height = max(10, new_height)

                # Maintain aspect ratio
                if self.original_pixmap_size.width() > 0 and self.original_pixmap_size.height() > 0:
                    original_aspect_ratio = float(
                        self.original_pixmap_size.width()) / self.original_pixmap_size.height()

                    # Determine which dimension is the limiting factor and scale proportionally
                    current_aspect_ratio = float(new_width) / new_height if new_height > 0 else 0

                    if current_aspect_ratio > original_aspect_ratio:
                        # Width is proportionally larger, adjust width based on new_height
                        new_width = int(new_height * original_aspect_ratio)
                    else:
                        # Height is proportionally larger or equal, adjust height based on new_width
                        new_height = int(new_width / original_aspect_ratio)

                # Update the preview rectangle, don't scale the actual pixmap yet
                self.current_preview_rect = QRect(self.image_pos.x(), self.image_pos.y(), new_width, new_height)
                self.update()  # Request repaint to draw the preview rectangle
            elif (self.space_pressed or self.active_tool == "move") and self.moving_image:
                self.image_pos = event.pos() - self.drag_offset
                # Recalculate and reposition the move button based on the new image_pos
                button_x = self.image_pos.x() + (self.background_pixmap.width() - self.move_image_btn.width()) // 2
                button_y = self.image_pos.y() - self.move_image_btn.height() - 10
                self.move_image_btn.move(button_x, button_y)
                self.update()
            elif self.drawing and (event.buttons() & Qt.LeftButton):
                if self.active_tool in ["pen", "eraser", "highlight"] and self.painter:
                    self.painter.drawLine(self.last_point, event.pos())  # Drawing with window-relative coords
                    self.last_point = event.pos()
                self.temp_end_point = event.pos()  # Always window-relative
                self.update()  # Request repaint for the whole window
        except Exception as e:
            log_error(f"PaintCanvasWindow mouseMoveEvent hatası: {e}", sys.exc_info())

    def mouseReleaseEvent(self, event):
        """Finalizes drawing, image movement, or resizing on mouse release."""
        try:
            if event.button() == Qt.LeftButton:
                if self.resizing:
                    if not self.current_preview_rect.isNull():
                        # Apply the actual scaling only once, on mouse release
                        self.background_pixmap = self.background_pixmap.scaled(
                            self.current_preview_rect.size(),
                            Qt.KeepAspectRatio,  # Keep aspect ratio for final scale
                            Qt.SmoothTransformation
                        )
                        # Recalculate and reposition the move button based on the new image_pos and size
                        button_x = self.image_pos.x() + (
                                self.background_pixmap.width() - self.move_image_btn.width()) // 2
                        button_y = self.image_pos.y() - self.move_image_btn.height() - 10
                        self.move_image_btn.move(button_x, button_y)

                    self.resizing = False
                    self.resize_anchor = None
                    self.current_preview_rect = QRect()  # Clear preview rectangle
                    self.setCursor(CursorManager.get_cursor("default"))  # JSON'dan imleç çek
                    self.update()  # Request repaint after final scaling
                elif self.moving_image:
                    self.moving_image = False
                    self.setCursor(
                        CursorManager.get_cursor("move_inactive") if self.space_pressed else CursorManager.get_cursor(
                            "default"))  # JSON'dan imleç çek
                elif self.drawing:
                    # End continuous drawing painter if active
                    if self.painter and self.painter.isActive():
                        self.painter.end()
                        self.painter = None

                    # For shapes (line, rect, ellipse), draw them once on release
                    if self.active_tool in ["line", "rect", "ellipse"]:
                        painter = QPainter(self.overlay_image)
                        if self.active_tool == "highlight":  # Highlighter modu için özel harmanlama modu
                            painter.setCompositionMode(QPainter.CompositionMode_Screen)
                        else:  # Diğer tüm araçlar (kalem, şekiller vb.) için normal harmanlama
                            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

                        painter.setPen(QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

                        if self.active_tool == "line":
                            painter.drawLine(self.temp_start_point, event.pos())  # Drawing with window-relative coords
                        elif self.active_tool == "rect":
                            painter.drawRect(
                                QRect(self.temp_start_point,
                                      event.pos()).normalized())  # Drawing with window-relative coords
                        elif self.active_tool == "ellipse":
                            painter.drawEllipse(
                                QRect(self.temp_start_point,
                                      event.pos()).normalized())  # Drawing with window-relative coords
                        painter.end()  # End painter for overlay_image to apply changes

                    self.drawing = False  # Reset drawing flag after all operations
                    self.update()  # Request repaint for the whole window
                    self.save_drawing_state()  # Çizim bittikten sonra durumu kaydet
        except Exception as e:
            log_error(f"PaintCanvasWindow mouseReleaseEvent hatası: {e}", sys.exc_info())

    def keyPressEvent(self, event):
        """Handles keyboard shortcuts (Space for hand tool, Esc to close)."""
        try:
            if event.key() == Qt.Key_Space:
                self.space_pressed = True
                # When space is pressed, explicitly set the tool to "move"
                # This will also update the button text
                self.set_tool("move")
            elif event.key() == Qt.Key_Escape:
                self.close_tool_window()
                self.close()
                # Reopen the main UI window if it was passed as a reference
                if self.main_window_ref:
                    self.main_window_ref.show()
            elif event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:  # Ctrl+Z için undo
                self.undo_drawing()
            elif event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier:  # Ctrl+Y için redo
                self.redo_drawing()
            else:
                super().keyPressEvent(event)
        except Exception as e:
            log_error(f"PaintCanvasWindow keyPressEvent hatası: {e}", sys.exc_info())

    def keyReleaseEvent(self, event):
        """Resets cursor and tool after Space key is released."""
        try:
            if event.key() == Qt.Key_Space:
                self.space_pressed = False
                if not self.moving_image:  # Only reset if not actively dragging
                    # Revert to previous tool (likely "pen" if it was moved to "move" by spacebar)
                    self.set_tool("pen")  # Always switch back to pen
            else:
                super().keyReleaseEvent(event)
        except Exception as e:
            log_error(f"PaintCanvasWindow keyReleaseEvent hatası: {e}", sys.exc_info())

    def paintEvent(self, event):
        """
        Draws the background screenshot and the overlay with user drawings.
        Also draws previews for shape tools and resize indicators.
        """
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)  # For smoother lines/shapes

            # 1) Fill the entire canvas background with light gray
            painter.fillRect(self.rect(), QColor(245, 245, 245))

            # 2) Draw the background pixmap (if any) at its current position
            if not self.background_pixmap.isNull():
                painter.drawPixmap(self.image_pos, self.background_pixmap)

                # Draw a dashed frame around the image if not resizing
                if not self.resizing:
                    image_rect = QRect(self.image_pos, self.background_pixmap.size())
                    frame_pen = QPen(QColor(0, 0, 0, 100), 2, Qt.DashLine)  # Slightly transparent black frame
                    painter.setPen(frame_pen)
                    painter.drawRect(image_rect)

            # 3) Draw the overlay image (where persistent drawings are stored) at (0,0)
            # This covers the entire window and allows drawing anywhere, even outside the initial screenshot area
            painter.drawImage(0, 0, self.overlay_image)
            print(
                f"DEBUG: paintEvent: overlay_image isNull: {self.overlay_image.isNull()}, Size: {self.overlay_image.size().width()}x{self.overlay_image.size().height()}, Format: {self.overlay_image.format()}")

            # 4) Draw preview for shape tools (line, rect, ellipse) using window-relative coordinates
            # This preview must be drawn on the window's painter, not the overlay_image's painter
            if self.drawing and self.active_tool in ["line", "rect", "ellipse"]:
                pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                pen.setStyle(Qt.DashLine)  # Use dashed line for preview
                painter.setPen(pen)
                if self.active_tool == "line":
                    painter.drawLine(self.temp_start_point, self.temp_end_point)
                elif self.active_tool == "rect":
                    painter.drawRect(QRect(self.temp_start_point, self.temp_end_point).normalized())
                elif self.active_tool == "ellipse":
                    painter.drawEllipse(QRect(self.temp_start_point, self.temp_end_point).normalized())

            # 5) Draw the resize handle and preview rectangle if resizing is active
            if not self.background_pixmap.isNull():
                # Always draw the resize handle if the image is present
                image_rect = QRect(self.image_pos, self.background_pixmap.size())
                handle_rect = QRect(
                    image_rect.bottomRight() - QPoint(self.resize_handle_size, self.resize_handle_size),
                    QSize(self.resize_handle_size, self.resize_handle_size)
                )
                painter.fillRect(handle_rect, QColor(0, 0, 255, 160))  # Blue semi-transparent box for handle

                # Draw the preview rectangle during resizing
                if self.resizing and not self.current_preview_rect.isNull():
                    preview_pen = QPen(QColor(255, 165, 0, 200), 2, Qt.DashLine)  # Orange dashed line for preview
                    painter.setPen(preview_pen)
                    painter.drawRect(self.current_preview_rect)

            painter.end()  # End painter for the window
        except Exception as e:
            log_error(f"PaintCanvasWindow paintEvent hatası: {e}", sys.exc_info())

    def resizeEvent(self, event):
        """
        Resizes the overlay_image when the window resizes to maintain drawing consistency.
        """
        try:
            # Only create a new overlay image if the size has actually changed
            if self.size() != self.overlay_image.size():
                # Create a new, empty overlay image with the new window size
                new_overlay_image = QImage(self.size(), QImage.Format_ARGB32)
                new_overlay_image.fill(Qt.transparent)

                # Create a painter for the new overlay image
                painter = QPainter(new_overlay_image)
                # Draw the content from the old overlay image onto the new one
                # This copies existing drawings to the resized canvas.
                painter.drawImage(0, 0, self.overlay_image)
                painter.end()
                self.overlay_image = new_overlay_image
                # Resize olayında undo stack'i güncelleme (genellikle gerekmez, çünkü çizimler aynı kalır)
                # Ancak uygulamanızda yeniden boyutlandırma çizimi etkiliyorsa burada kaydetme yapılabilir.
            super().resizeEvent(event)
        except Exception as e:
            log_error(f"PaintCanvasWindow resizeEvent hatası: {e}", sys.exc_info())

    def close_tool_window(self):
        """Safely closes the associated tool window."""
        try:
            if hasattr(self, 'tool_window') and self.tool_window:
                self.tool_window.close()
                self.tool_window = None
        except Exception as e:
            log_error(f"Araç penceresi kapatılırken hata: {e}", sys.exc_info())

    def closeEvent(self, event):
        """
        Handles the window close event. Ensures tool window is closed,
        saves the current drawing state, and reopens the main UI window.
        """
        try:
            # Mevcut çizim durumunu kaydet
            self._save_current_drawing_auto()
            print("DEBUG: Çizim penceresi kapatılırken otomatik kaydetme tetiklendi.")

            self.close_tool_window()
            # Ensure the main window is reopened after this window closes
            if self.main_window_ref:
                self.main_window_ref.show()
            super().closeEvent(event)  # Call parent's closeEvent
        except Exception as e:
            log_error(f"PaintCanvasWindow closeEvent hatası: {e}", sys.exc_info())


class ToolWindow(QWidget):
    """
    A floating tool window for selecting drawing tools, colors, and brush size.
    """

    def __init__(self, parent_paint_window, app_config):  # app_config'i parametre olarak al
        super().__init__(parent_paint_window)  # Parent is PaintCanvasWindow
        self.paint_window = parent_paint_window
        self.app_config = app_config  # app_config'i sakla
        self.setWindowTitle("Çizim Araçları")
        self.setFixedSize(120, 482)  # Set fixed size for UI elements
        # Keep window on top and make it a tool window (not visible in taskbar)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        # Construct path to .ui file from config
        script_dir = os.path.dirname(__file__)
        ui_file_name = self.app_config.get("tool_ui_file", "pen_tool.ui")  # Varsayılan: pen_tool.ui
        ui_path = os.path.join(script_dir, 'data', ui_file_name)

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            error_msg = f"Araçlar için UI dosyası bulunamadı: {ui_path}"
            QMessageBox.critical(self, "Hata", error_msg)
            log_error(error_msg)
            sys.exit(1)

        try:
            uic.loadUi(ui_path, self)  # Load the UI from the .ui file
        except Exception as e:
            error_msg = f"Araç UI dosyası '{ui_path}' yüklenirken hata oluştu: {e}"
            QMessageBox.critical(self, "Araç UI Yükleme Hatası", error_msg)
            log_error(error_msg, sys.exc_info())
            sys.exit(1)

        # Get reference to the new color indicator QLabel
        self.selected_color_indicator = self.findChild(QLabel, "selected_color_indicator")
        if not self.selected_color_indicator:
            print("Warning: 'selected_color_indicator' QLabel not found in pen_tool.ui.")
            log_error("UI'da 'selected_color_indicator' QLabel bulunamadı.")

        # Connect tool buttons using their object names from .ui
        self.findChild(QPushButton, "pen_btn").clicked.connect(lambda: self.set_tool("pen"))
        self.findChild(QPushButton, "eraser_btn").clicked.connect(lambda: self.set_tool("eraser"))
        self.findChild(QPushButton, "line_btn").clicked.connect(lambda: self.set_tool("line"))
        self.findChild(QPushButton, "rect_btn").clicked.connect(lambda: self.set_tool("rect"))
        self.findChild(QPushButton, "ellipse_btn").clicked.connect(lambda: self.set_tool("ellipse"))

        # highlight_btn bağlantısı ve aracı "highlight" olarak ayarlama
        self.findChild(QPushButton, "highlight_btn").clicked.connect(self.select_highlighter)

        self.move_btn = self.findChild(QPushButton, "move_btn")
        if self.move_btn:
            self.move_btn.clicked.connect(lambda: self.paint_window._toggle_move_tool())
        else:
            print("Warning: 'move_btn' not found in pen_tool.ui. Move tool functionality will be unavailable.")
            log_error("UI'da 'move_btn' bulunamadı.")

        self.clear_all_btn = self.findChild(QPushButton, "clear_all_btn")
        if self.clear_all_btn:
            self.clear_all_btn.clicked.connect(self.clear_all_drawings_in_paint_window)
        else:
            print("Warning: 'clear_all_btn' not found in pen_tool.ui. Clear all functionality will be unavailable.")
            log_error("UI'da 'clear_all_btn' bulunamadı.")

        # --- Undo/Redo butonları bağlantısı ---
        self.undo_btn = self.findChild(QPushButton, "undo")
        if self.undo_btn:
            self.undo_btn.clicked.connect(self.paint_window.undo_drawing)
        else:
            print("Warning: 'undo' button not found in pen_tool.ui.")
            log_error("UI'da 'undo' butonu bulunamadı.")

        self.redo_btn = self.findChild(QPushButton, "redo")
        if self.redo_btn:
            self.redo_btn.clicked.connect(self.paint_window.redo_drawing)
        else:
            print("Warning: 'redo' button not found in pen_tool.ui.")
            log_error("UI'da 'redo' butonu bulunamadı.")
        # --- Undo/Redo butonları bağlantısı SONU ---

        # --- Otomatik Kayıt Yükle Butonu ---
        self.load_commands_btn = self.findChild(QPushButton, "load_commands_btn")
        if self.load_commands_btn:
            self.load_commands_btn.clicked.connect(
                self._load_auto_saved_drawing)  # Otomatik kaydı yükleyen metot bağlandı
        else:
            print(
                "Warning: 'load_commands_btn' button not found in pen_tool.ui. Load auto-saved drawing functionality will be unavailable.")
            log_error("UI'da 'load_commands_btn' butonu bulunamadı.")
        # --- Otomatik Kayıt Yükle Butonu SONU ---

        # --- KALEM RENKLERİNİ app_config.json'dan DİNAMİK YÜKLEME ---
        self.load_tool_window_colors_from_config()
        # --- KALEM RENKLERİNİ DİNAMİK YÜKLEME SONU ---

        # Connect brush size slider (for pen and shapes)
        self.brushSizeSlider = self.findChild(QSlider, "horizontalSlider")
        if self.brushSizeSlider:
            self.brushSizeSlider.setMinimum(1)
            self.brushSizeSlider.setMaximum(50)
            self.brushSizeSlider.setValue(self.paint_window.brush_size)  # Set initial value
            self.brushSizeSlider.setOrientation(Qt.Horizontal)
            self.brushSizeSlider.setTickPosition(QSlider.TicksBelow)
            self.brushSizeSlider.setTickInterval(2)
            self.brushSizeSlider.valueChanged.connect(self.change_brush_size)
        else:
            print("Warning: 'horizontalSlider' not found in pen_tool.ui. Brush size control will be unavailable.")
            log_error("UI'da 'horizontalSlider' bulunamadı.")

        # Connect eraser size slider (new)
        self.eraserSizeSlider = self.findChild(QSlider, "eraser_slider")  # Assume 'eraser_slider' exists in UI
        if self.eraserSizeSlider:
            self.eraserSizeSlider.setMinimum(1)
            self.eraserSizeSlider.setMaximum(50)  # Same range as brush
            self.eraserSizeSlider.setValue(self.paint_window.eraser_size)  # Set initial value for eraser
            self.eraserSizeSlider.setOrientation(Qt.Horizontal)
            self.eraserSizeSlider.setTickPosition(QSlider.TicksBelow)
            self.eraserSizeSlider.setTickInterval(5)
            self.eraserSizeSlider.valueChanged.connect(self.change_eraser_size)  # New connection
        else:
            print("Warning: 'eraser_slider' not found in pen_tool.ui. Eraser size control will be unavailable.")
            log_error("UI'da 'eraser_slider' bulunamadı.")

        self.findChild(QPushButton, "exit_btn").clicked.connect(self.close)

        # Set initial indicator color based on paint_window's current color
        self.set_selected_color_indicator(self.paint_window.brush_color)

    def load_tool_window_colors_from_config(self):
        """
        Loads pen colors from app_config.json for the ToolWindow and connects them to buttons.
        """
        if self.app_config and "pen_colors" in self.app_config:
            colors = self.app_config["pen_colors"]
            # These are the object names of your QPushButton widgets in pen_tool.ui
            color_button_names = ["color_red", "color_blue", "color_black", "color_green",
                                  "color_custom1", "color_custom2"]  # Add more as needed based on your .ui

            # Deactivate any buttons that won't be used (if fewer colors than buttons)
            for i in range(len(color_button_names)):
                btn = self.findChild(QPushButton, color_button_names[i])
                if btn:
                    if i < len(colors):
                        color_str = colors[i]
                        try:
                            q_color = QColor(color_str)
                            if q_color.isValid():
                                btn.setStyleSheet(
                                    f"background-color: {color_str}; border-radius: 5px; border: 1px solid gray;")
                                # Remove previous connections to avoid multiple calls
                                try:
                                    btn.clicked.disconnect()
                                except TypeError:  # Disconnects if already connected
                                    pass
                                btn.clicked.connect(lambda checked, c=q_color: self.set_color_and_update_main(c))
                                btn.show()  # Make sure the button is visible
                            else:
                                print(
                                    f"Uyarı (ToolWindow): Geçersiz renk değeri '{color_str}' app_config.json'da bulundu.")
                                log_error(f"ToolWindow: Geçersiz renk değeri app_config.json'da: {color_str}")
                                btn.hide()  # Hide button if color is invalid
                        except Exception as e:
                            print(f"ToolWindow renk butonu ayarlanırken hata oluştu: {color_str} - {e}")
                            log_error(f"ToolWindow renk butonu ayarlanırken hata: {color_str} - {e}", sys.exc_info())
                            btn.hide()  # Hide button on error
                    else:
                        btn.hide()  # Hide buttons if there are no corresponding colors in config
                else:
                    print(f"Uyarı (ToolWindow): {color_button_names[i]} isimli buton UI dosyasında bulunamadı.")
        else:
            print(
                "Uyarı (ToolWindow): 'pen_colors' anahtarı app_config.json'da bulunamadı. Varsayılan renkler kullanılacak.")
            log_error("ToolWindow: app_config.json'da 'pen_colors' anahtarı bulunamadı.")

    def set_selected_color_indicator(self, color):
        """
        Updates the selected color indicator QLabel's background color.
        """
        try:
            if self.selected_color_indicator:
                # Ensure a solid color is shown for the indicator, even if the brush has alpha for highlight
                display_color = QColor(color.red(), color.green(), color.blue(), 255)  # Force alpha to opaque
                self.selected_color_indicator.setStyleSheet(
                    f"background-color: {display_color.name()}; border-radius: 5px; border: 1px solid black;")
        except Exception as e:
            log_error(f"Seçili renk göstergesi güncellenirken hata: {e}", sys.exc_info())

    def set_tool(self, tool):
        """Delegates tool selection to the parent paint window."""
        try:
            if self.paint_window:
                self.paint_window.set_tool(tool)
        except Exception as e:
            log_error(f"ToolWindow araç ayarlanırken hata: {e}", sys.exc_info())

    def set_color_and_update_main(self, color):
        """
        Delegates color setting to the parent paint window and updates
        this tool window's color indicator. Ensures the brush color is
        fully opaque unless the highlighter tool is active.
        """
        try:
            q_color_obj = QColor(color)
            if self.paint_window and self.paint_window.active_tool != "highlight":
                # For non-highlighter tools, force the alpha to 255 (fully opaque)
                q_color_obj.setAlpha(255)
                # If it's highlight, it will already have its alpha set in select_highlighter,
            # or it will maintain its alpha if set externally.

            if self.paint_window:
                self.paint_window.set_brush_color(q_color_obj)
                self.set_selected_color_indicator(q_color_obj)  # Update this window's indicator
        except Exception as e:
            log_error(f"ToolWindow renk ayarlanırken hata: {e}", sys.exc_info())

    def change_brush_size(self, value):
        """Delegates brush size change to the parent paint window (for pen and shapes)."""
        try:
            if self.paint_window:
                self.paint_window.set_brush_size(value)
        except Exception as e:
            log_error(f"ToolWindow fırça boyutu değiştirilirken hata: {e}", sys.exc_info())

    def change_eraser_size(self, value):
        """Delegates eraser size change to the parent paint window."""
        try:
            if self.paint_window:
                self.paint_window.set_eraser_size(value)
        except Exception as e:
            log_error(f"ToolWindow silgi boyutu değiştirilirken hata: {e}", sys.exc_info())

    def select_highlighter(self):
        """
        Configures the brush for a semi-transparent highlighter effect.
        Uses the current active brush color from the PaintCanvasWindow
        and sets its alpha value for transparency.
        """
        try:
            if self.paint_window:
                current_base_color = QColor(self.paint_window.brush_color)
                current_base_color.setAlpha(128)  # 50% transparency for highlighter
                self.paint_window.set_brush_color(current_base_color)
                self.paint_window.set_tool("highlight")  # Aracı "highlight" olarak ayarla
                self.set_selected_color_indicator(current_base_color)  # Update indicator with highlight color
        except Exception as e:
            log_error(f"Highlighter seçilirken hata: {e}", sys.exc_info())

    def clear_all_drawings_in_paint_window(self):
        """Calls the clear_all_drawings method on the parent PaintCanvasWindow."""
        try:
            if self.paint_window:
                self.paint_window.clear_all_drawings()
        except Exception as e:
            log_error(f"Tüm çizimler temizlenirken hata: {e}", sys.exc_info())

    def _load_auto_saved_drawing(self):
        """
        Loads the drawing from the predefined auto-save file and applies it.
        This method is called when the 'Yükle' button is clicked.
        """
        print("DEBUG: ToolWindow._load_auto_saved_drawing called (Yükle butonu).")
        try:
            # Check if the auto-save file exists and has content
            if not os.path.exists(_AUTO_SAVE_DRAWING_FILE) or os.path.getsize(_AUTO_SAVE_DRAWING_FILE) == 0:
                QMessageBox.information(self, "Bilgi",
                                        "Otomatik kaydedilen çizim dosyası bulunamadı veya boş. Lütfen önce bir çizim yapın ve kaydedilmesini bekleyin.")
                print(f"DEBUG: 'Yükle' butonu: Otomatik kayıt dosyası bulunamadı veya boş: {_AUTO_SAVE_DRAWING_FILE}")
                return

            with open(_AUTO_SAVE_DRAWING_FILE, 'r', encoding='utf-8') as f:
                base64_data = f.read()
            print(f"DEBUG: 'Yükle' butonu ile okunan Base64 veri uzunluğu: {len(base64_data)}")

            if not base64_data.strip():
                QMessageBox.information(self, "Bilgi", "Otomatik kaydedilen çizim dosyası boş.")
                print("DEBUG: 'Yükle' butonu: Otomatik kaydedilen çizim dosyası boş.")
                return

            # Decode Base64 data to PNG byte array
            png_data = QByteArray().fromBase64(base64_data.encode('utf-8'))

            loaded_image = QImage()
            # Attempt to load the QImage from the PNG byte array
            load_success = loaded_image.loadFromData(png_data, "PNG")
            print(
                f"DEBUG: 'Yükle' butonu ile loaded_image.loadFromData başarı: {load_success}, isNull: {loaded_image.isNull()}")

            if load_success and not loaded_image.isNull():
                print(
                    f"DEBUG: 'Yükle' butonu ile yüklenen orijinal resim boyutu: {loaded_image.size().width()}x{loaded_image.size().height()}")

                # Scale the loaded image to the current paint window size if dimensions differ
                if loaded_image.size() != self.paint_window.size():
                    scaled_image = loaded_image.scaled(self.paint_window.size(),
                                                       Qt.IgnoreAspectRatio,  # En boy oranını korumadan doldur
                                                       Qt.SmoothTransformation)  # Smooth scaling for better quality
                    self.paint_window.set_overlay_image(scaled_image)
                    print(
                        f"DEBUG: 'Yükle' butonu ile yüklenen resim pencere boyutuna ölçeklendi: {scaled_image.size().width()}x{scaled_image.size().height()}")
                else:
                    # If sizes match, set the image directly
                    self.paint_window.set_overlay_image(loaded_image)
                    print(
                        f"DEBUG: 'Yükle' butonu ile yüklenen resim doğrudan ayarlandı. Boyut: {loaded_image.size().width()}x{loaded_image.size().height()}")

                QMessageBox.information(self, "Yükleme Tamamlandı", "Otomatik kaydedilen çizim başarıyla yüklendi.")
            else:
                QMessageBox.critical(self, "Yükleme Hatası",
                                     "Otomatik kaydedilen dosya geçerli bir çizim verisi içermiyor veya bozuk.")
                log_error(
                    f"Otomatik kaydedilen dosya geçerli bir çizim verisi içermiyor veya bozuk: {_AUTO_SAVE_DRAWING_FILE}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Otomatik çizim yüklenirken bir hata oluştu: {e}")
            log_error(f"Otomatik çizim yüklenirken hata: {e}", sys.exc_info())

    def closeEvent(self, event):
        """
        Handles the tool window close event. Ensures the parent paint window
        is also closed to prevent orphaned drawing sessions.
        """
        try:
            if self.paint_window:
                try:
                    self.paint_window.close()  # Close the associated drawing window
                except Exception as e:
                    log_error(f"Araç penceresinden ana çizim penceresi kapatılırken hata: {e}", sys.exc_info())
        except Exception as e:
            log_error(f"ToolWindow closeEvent hatası: {e}", sys.exc_info())
        event.accept()


if __name__ == '__main__':
    # Increase recursion limit if needed for deep call stacks (e.g., complex UI loading)
    sys.setrecursionlimit(10000)
    app = QApplication(sys.argv)
    try:
        main_app_window = Ui()
        main_app_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        error_msg = f"Kritik uygulama başlangıç hatası: {e}"
        print(error_msg)
        log_error(error_msg, sys.exc_info())
        sys.exit(1)

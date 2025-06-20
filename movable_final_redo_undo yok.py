import sys
import os
import traceback
import json
import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QComboBox, QMessageBox, QFrame, QPushButton, \
    QSlider
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QTimer
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
        self.overlay_image = QImage(self.size(), QImage.Format_ARGB32)
        self.overlay_image.fill(Qt.transparent)  # Fill with transparent color initially

        # Drawing properties
        self.brush_color = initial_brush_color
        self.brush_size = initial_brush_size
        self.active_tool = "pen"  # Default tool

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
            button_y = image_y - self.move_image_btn.height() - 10  # 10px above the top edge

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
        """Sets the current brush size."""
        try:
            self.brush_size = size
        except Exception as e:
            log_error(f"Fırça boyutu ayarlanırken hata: {e}", sys.exc_info())

    def clear_all_drawings(self):
        """Clears all drawings on the overlay image."""
        try:
            self.overlay_image.fill(Qt.transparent)  # Fill the overlay with transparent color
            self.update()  # Request a repaint to show the cleared canvas
        except Exception as e:
            log_error(f"Çizimleri temizlerken hata: {e}", sys.exc_info())

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
                else:
                    self.drawing = True
                    self.last_point = event.pos()  # These are now always window-relative
                    self.temp_start_point = event.pos()  # These are now always window-relative
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
                painter = QPainter(self.overlay_image)  # Paint directly on overlay_image
                if self.active_tool == "eraser":
                    painter.setCompositionMode(QPainter.CompositionMode_Clear)  # Transparent for erasing
                    pen = QPen(Qt.transparent, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                elif self.active_tool == "highlight":  # Highlighter modu için özel harmanlama modu
                    painter.setCompositionMode(QPainter.CompositionMode_Screen)  # Renkleri koyulaştırmadan harmanla
                    pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                else:  # Diğer tüm araçlar (kalem, şekiller vb.) için normal harmanlama
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)  # Normal blending
                    pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)

                if self.active_tool in ["pen", "eraser", "highlight"]:  # "highlight" da sürekli çizim yapar
                    painter.drawLine(self.last_point, event.pos())  # Drawing with window-relative coords
                    self.last_point = event.pos()
                self.temp_end_point = event.pos()  # Always window-relative
                painter.end()  # End painter for overlay_image to apply changes

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
                    self.drawing = False
                    painter = QPainter(self.overlay_image)  # Paint directly on overlay_image

                    # Mouse release for shapes also uses current tool's composition mode
                    if self.active_tool == "highlight":
                        painter.setCompositionMode(QPainter.CompositionMode_Screen)
                    else:
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
                    self.update()  # Request repaint for the whole window
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

            # 2) Draw the background screenshot (if any) at its current position
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

            # 4) Draw preview for shape tools (line, rect, ellipse) using window-relative coordinates
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
        Handles the window close event. Ensures tool window is closed
        and reopens the main UI window.
        """
        try:
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

        # --- KALEM RENKLERİNİ app_config.json'dan DİNAMİK YÜKLEME ---
        self.load_tool_window_colors_from_config()
        # --- KALEM RENKLERİNİ DİNAMİK YÜKLEME SONU ---

        # Connect brush size slider
        self.brushSizeSlider = self.findChild(QSlider, "horizontalSlider")
        if self.brushSizeSlider:
            self.brushSizeSlider.setMinimum(1)
            self.brushSizeSlider.setMaximum(50)
            self.brushSizeSlider.setValue(self.paint_window.brush_size)  # Set initial value
            self.brushSizeSlider.setOrientation(Qt.Horizontal)
            self.brushSizeSlider.setTickPosition(QSlider.TicksBelow)
            self.brushSizeSlider.setTickInterval(5)
            self.brushSizeSlider.valueChanged.connect(self.change_brush_size)
        else:
            print("Warning: 'horizontalSlider' not found in pen_tool.ui. Brush size control will be unavailable.")
            log_error("UI'da 'horizontalSlider' bulunamadı.")

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
        this tool window's color indicator.
        """
        try:
            if self.paint_window:
                self.paint_window.set_brush_color(QColor(color))
                self.set_selected_color_indicator(QColor(color))  # Update this window's indicator
        except Exception as e:
            log_error(f"ToolWindow renk ayarlanırken hata: {e}", sys.exc_info())

    def change_brush_size(self, value):
        """Delegates brush size change to the parent paint window."""
        try:
            if self.paint_window:
                self.paint_window.set_brush_size(value)
        except Exception as e:
            log_error(f"ToolWindow fırça boyutu değiştirilirken hata: {e}", sys.exc_info())

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
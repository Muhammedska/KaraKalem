import sys
import os
import traceback
import json
import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QComboBox, QMessageBox, QFrame, QPushButton, \
    QSlider, QFileDialog, QColorDialog, QSpinBox  # QSpinBox'u import et
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QTimer, QBuffer, QByteArray
from PyQt5.QtGui import QColor, QPen, QPainter, QImage, QPixmap, QCursor, QIcon, qAlpha, qRed, qGreen, qBlue

# Conditional import for Windows-specific modules
try:
    import win32api
    import win32con
    import win32gui
    from PIL import ImageGrab

    WIN_SPECIFIC_IMPORTS_AVAILABLE = True
except ImportError:
    WIN_SPECIFIC_IMPORTS_AVAILABLE = False
    # Warning for missing Windows-specific modules, always print
    print(
        "Warning: win32api, win32con, win32gui, or PIL not found. Windows-specific features (transparency, ImageGrab) will be disabled.")

# Global debug flag, controlled by app_config.json
_DEBUG_MODE_ENABLED = False


def _debug_print(*args, **kwargs):
    """
    Prints messages only if _DEBUG_MODE_ENABLED is True.
    """
    if _DEBUG_MODE_ENABLED:
        print("DEBUG:", *args, **kwargs)


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
    # Always print error messages
    print(f"Hata günlüğe kaydedildi: {error_message}")


def _check_qimage_for_visible_content(image: QImage) -> bool:
    """
    Checks if a QImage contains any non-transparent or non-zero color pixels.
    Returns True if visible content is found, False otherwise.
    """
    if image.isNull():
        _debug_print("Image is null, no visible content.")
        return False

    # For ARGB32, transparent is 0x00000000. Any other value indicates content.
    # We will directly check the raw pixel data for non-zero bytes.
    if image.format() == QImage.Format_ARGB32:
        try:
            # Access raw pixel data as a memoryview and check for any non-zero byte
            # This is a faster and more robust check for ARGB32 images.
            data = image.constBits().asarray(image.byteCount())
            if any(byte != 0 for byte in data):
                _debug_print("ARGB32 image has non-zero bytes, visible content found.")
                return True
            else:
                _debug_print("ARGB32 image contains only zero bytes (fully transparent).")
                return False
        except Exception as e:
            # Fallback to pixel-by-pixel if raw access fails for some reason
            _debug_print(f"Error accessing raw image bits ({e}), falling back to pixel-by-pixel check.")
            log_error(f"Error accessing raw image bits in _check_qimage_for_visible_content: {e}", sys.exc_info())

    # Fallback/general pixel-by-pixel check for other formats or if raw access failed
    if image.hasAlphaChannel():
        for y in range(image.height()):
            for x in range(image.width()):
                pixel_rgb = image.pixel(x, y)
                alpha = qAlpha(pixel_rgb)
                if alpha != 0:
                    # Also check if color components are not all zero, to exclude transparent black on transparent background.
                    # However, if alpha is non-zero, it usually means it's visible.
                    # We prioritize alpha being non-zero for 'visible content' as per Qt's transparency model.
                    if qRed(pixel_rgb) != 0 or qGreen(pixel_rgb) != 0 or qBlue(pixel_rgb) != 0:
                        _debug_print(f"Pixel-by-pixel: Visible alpha {alpha} and color at ({x},{y})")
                        return True
                    elif alpha == 255:  # Fully opaque black is also visible content
                        if qRed(pixel_rgb) == 0 and qGreen(pixel_rgb) == 0 and qBlue(pixel_rgb) == 0:
                            _debug_print(f"Pixel-by-pixel: Fully opaque black found at ({x},{y})")
                            return True
        _debug_print("Image with alpha channel: no visible alpha or non-black opaque content found.")
        return False
    else:
        # For images without alpha, check for any non-black pixel
        for y in range(image.height()):
            for x in range(image.width()):
                pixel_rgb = image.pixel(x, y)
                if qRed(pixel_rgb) != 0 or qGreen(pixel_rgb) != 0 or qBlue(pixel_rgb) != 0:
                    _debug_print(f"Pixel-by-pixel: Visible color at ({x},{y})")
                    return True
        _debug_print("Image without alpha channel: only black pixels found.")
        return False


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
            # Always print errors
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
                            # _debug_print(f"İmleç yüklendi: {key} -> {image_file}, Boyut: {size}x{size}")
                        else:
                            error_msg = f"Uyarı: İmleç görseli yüklenemedi: {image_file} (Anahtar: {key}). Varsayılan ok kullanılacak."
                            # Always print warnings
                            print(error_msg)
                            log_error(error_msg)
                            cls._cursors[key] = QCursor(Qt.ArrowCursor)  # Yüklenemezse varsayılan
                    elif isinstance(cursor_info, str) and hasattr(Qt, cursor_info):
                        # Geriye dönük uyumluluk veya varsayılan Qt imleçleri için
                        cls._cursors[key] = QCursor(getattr(Qt, cursor_info))
                    else:
                        error_msg = f"Uyarı: Geçersiz imleç tanımı '{key}' JSON'da bulundu. Varsayılan ok kullanılacak."
                        # Always print warnings
                        print(error_msg)
                        log_error(error_msg)
                        cls._cursors[key] = QCursor(Qt.ArrowCursor)

                _debug_print(f"İmleçler '{json_path}' dosyasından başarıyla yüklendi.")
        except FileNotFoundError:
            error_msg = f"Hata: İmleç dosyası bulunamadı: {json_path}"
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())
        except json.JSONDecodeError:
            error_msg = f"Hata: İmleç dosyası geçersiz JSON formatında: {json_path}"
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())
        except Exception as e:
            error_msg = f"İmleçler yüklenirken bir hata oluştu: {e}"
            # Always print errors
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
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)  # Keep window on top

        # Set initial window position from app_config.json
        main_pos = self.app_config.get("main_window_position")
        if main_pos:
            self.move(main_pos.get("x", 100), main_pos.get("y", 100))
        else:
            _debug_print("Warning: 'main_window_position' not found in app_config.json. Using default positioning.")
            log_error("'main_window_position' app_config.json'da bulunamadı.")

        # Connect buttons to their respective methods using object names from .ui file
        quit_btn = self.findChild(QPushButton, "quit")
        if quit_btn:
            quit_btn.clicked.connect(self.close)
        else:
            _debug_print("Warning: 'quit' button not found in undockapp.ui.")
            log_error("UI'da 'quit' butonu bulunamadı.")

        pen_btn = self.findChild(QPushButton, "pen")
        if pen_btn:
            pen_btn.clicked.connect(self.start_full_screen_paint)
        else:
            _debug_print("Warning: 'pen' button not found in undockapp.ui.")
            log_error("UI'da 'pen' butonu bulunamadı.")

        ss_btn = self.findChild(QPushButton, "ss")
        if ss_btn:
            ss_btn.clicked.connect(self.open_region_selector)
        else:
            _debug_print("Warning: 'ss' button not found in undockapp.ui.")
            log_error("UI'da 'ss' butonu bulunamadı.")

        # Connect the new "settings" button
        self.settings_btn = self.findChild(QPushButton, "settings_btn")  # Assuming objectName is 'settings_btn'
        if self.settings_btn:
            self.settings_btn.clicked.connect(self.open_settings_window)
        else:
            _debug_print("Warning: 'settings_btn' button not found in undockapp.ui.")
            log_error("UI'da 'settings_btn' butonu bulunamadı.")

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
        Loads pen colors from app_config.json and connects them to buttons in the main UI.
        This method is designed to work with fixed-named buttons in undockapp.ui if they exist.
        """
        if self.app_config and "pen_colors" in self.app_config:
            colors = self.app_config["pen_colors"]
            # These are the object names of your QPushButton widgets in undockapp.ui (if any)
            # This list should match the names in your undockapp.ui
            color_button_names = ["color_red", "color_blue", "color_black", "color_green",
                                  "color_custom1", "color_custom2"]  # Example names in main UI

            for i, color_str in enumerate(colors):
                if i < len(color_button_names):
                    btn = self.findChild(QPushButton, color_button_names[i])
                    if btn:
                        try:
                            q_color = QColor(color_str)
                            if q_color.isValid():
                                btn.setStyleSheet(
                                    f"background-color: {color_str}; border-radius: 5px; border: 1px solid gray;")
                                try:
                                    btn.clicked.disconnect()
                                except TypeError:  # Disconnects if already connected
                                    pass
                                btn.clicked.connect(lambda checked, c=q_color: self.set_color(c))
                                btn.show()  # Make sure the button is visible
                            else:
                                _debug_print(
                                    f"Uyarı (Main UI): Geçersiz renk değeri '{color_str}' app_config.json'da bulundu.")
                                log_error(f"Main UI: Geçersiz renk değeri app_config.json'da: {color_str}")
                                if btn: btn.hide()  # Hide button if color is invalid
                        except Exception as e:
                            _debug_print(f"Main UI renk butonu ayarlanırken hata oluştu: {color_str} - {e}")
                            log_error(f"Main UI renk butonu ayarlanırken hata: {color_str} - {e}", sys.exc_info())
                            if btn: btn.hide()  # Hide button on error
                    else:
                        _debug_print(
                            f"Uyarı (Main UI): {color_button_names[i]} isimli buton undockapp.ui dosyasında bulunamadı.")
                else:
                    _debug_print(
                        f"Bilgi (Main UI): app_config.json'da tanımlanan tüm renkler için yeterli buton mevcut değil.")
        else:
            _debug_print(
                "Uyarı (Main UI): 'pen_colors' anahtarı app_config.json'da bulunamadı. Varsayılan renkler kullanılacak.")
            log_error("Main UI: app_config.json'da 'pen_colors' anahtarı bulunamadı.")

    def load_app_config(self, config_path):
        """
        Loads application configuration from the specified JSON file.
        Sets the global _DEBUG_MODE_ENABLED flag based on 'debug_mode' in config.
        Ensures 'pen_colors' has at least 6 default entries if missing or too short.
        """
        global _DEBUG_MODE_ENABLED  # Declare global to modify it
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                # Set the global debug flag
                _DEBUG_MODE_ENABLED = config_data.get("debug_mode", False)
                _debug_print(f"Debug Mode Enabled: {_DEBUG_MODE_ENABLED}")

                # Ensure 'pen_colors' exists and has at least 6 entries
                if "pen_colors" not in config_data or not isinstance(config_data["pen_colors"], list):
                    config_data["pen_colors"] = []

                default_colors = ["#FF0000", "#0000FF", "#000000", "#008000", "#800080", "#FFA500"]
                while len(config_data["pen_colors"]) < len(default_colors):
                    config_data["pen_colors"].append(default_colors[len(config_data["pen_colors"])])

                # Trim if there are too many colors (optional, but good for fixed UI)
                config_data["pen_colors"] = config_data["pen_colors"][:len(default_colors)]

                # Ensure initial_smoothing_factor exists
                if "initial_smoothing_factor" not in config_data:
                    config_data["initial_smoothing_factor"] = 5  # Default smoothing factor

                return config_data
        except FileNotFoundError:
            error_msg = f"Hata: Uygulama yapılandırma dosyası bulunamadı: {config_path}"
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            # Create a default config if not found
            default_config = {
                "debug_mode": False,
                "main_window_position": {"x": 100, "y": 100},
                "app_icon_path": "icons/app_icon.ico",
                "main_ui_file": "undockapp.ui",
                "tool_ui_file": "pen_tool.ui",
                "tool_window_position": {"x_offset_from_paint_window": -20, "y_offset_from_paint_window": 20},
                "pen_colors": ["#FF0000", "#0000FF", "#000000", "#008000", "#800080", "#FFA500"],
                "initial_smoothing_factor": 5
            }
            try:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4, ensure_ascii=False)
                _debug_print(f"Varsayılan app_config.json oluşturuldu: {config_path}")
                _DEBUG_MODE_ENABLED = default_config.get("debug_mode", False)
                return default_config
            except Exception as write_e:
                error_msg_write = f"Hata: Varsayılan yapılandırma dosyası yazılamadı: {write_e}"
                print(error_msg_write)
                log_error(error_msg_write, sys.exc_info())
                return None

        except json.JSONDecodeError:
            error_msg = f"Hata: Uygulama yapılandırma dosyası geçersiz JSON formatında: {config_path}"
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            return None
        except Exception as e:
            error_msg = f"Uygulama yapılandırması yüklenirken bir hata oluştu: {e}"
            # Always print errors
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
                    _debug_print(f"Uygulama simgesi yüklendi: {full_icon_path}")
                else:
                    error_msg = f"Uyarı: Uygulama simgesi bulunamadı: {full_icon_path}"
                    # Always print warnings
                    print(error_msg)
                    log_error(error_msg)
            else:
                _debug_print("Uyarı: 'app_icon_path' yapılandırma dosyasında bulunamadı.")
        except Exception as e:
            error_msg = f"Uygulama simgesi ayarlanırken hata oluştu: {e}"
            # Always print errors
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
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())
            self.show()  # Hata olursa ana pencereyi tekrar göster

    def open_settings_window(self):
        """Hides the main window and opens the settings window."""
        try:
            self.hide()  # Main window'u gizle
            self.settings_window = SettingsWindow(self)  # SettingsWindow'ı oluştur ve main window referansını ilet
            self.settings_window.show()  # SettingsWindow'ı göster
        except Exception as e:
            error_msg = f"Ayarlar penceresi açılırken hata oluştu: {e}"
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
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def set_color(self, color):
        """Sets the active drawing color and updates the color indicator."""
        try:
            self.active_color = color
            if self.color_indicator:
                self.color_indicator.setStyleSheet(f"background-color: {self.active_color.name()}; border-radius: 5px;")
        except Exception as e:
            error_msg = f"Renk ayarlama hatası: {e}"
            # Always print errors
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
                # Always print errors
                print(error_msg)
                log_error(error_msg)
        except Exception as e:
            error_msg = f"Fırça boyutu ayarlama hatası: {e}"
            # Always print errors
            print(error_msg)
            log_error(error_msg, sys.exc_info())

    def start_full_screen_paint(self):
        """Hides the main window and starts a full-screen paint session."""
        try:
            self.hide()
            screenshot = self._capture_screenshot_pixmap()
            if screenshot:
                try:
                    # Ensure initial_brush_color passed to PaintCanvasWindow has full opacity for pen tool
                    initial_paint_color = QColor(self.active_color)
                    initial_paint_color.setAlpha(255)  # Force full opacity for the initial launch of the paint window

                    self.paint_window = PaintCanvasWindow(
                        screenshot,
                        initial_paint_color,  # Use the modified color with full alpha
                        self.active_size,
                        self  # Pass main window reference
                    )
                    self.paint_window.showFullScreen()
                except Exception as e:
                    error_msg = f"Tam ekran çizim penceresi oluşturulurken hata oluştu: {e}"
                    # Always print errors
                    print(error_msg)
                    log_error(error_msg, sys.exc_info())
                    self.show()  # Show main window if paint window fails
            else:
                self.show()  # Show main window if screenshot fails
        except Exception as e:
            error_msg = f"Tam ekran boyama başlatılırken genel hata: {e}"
            # Always print errors
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
            # Always print errors
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
            painter.setPen(QPen(QColor(255, 0, 0, 255), 2, Qt.DashLine))  # red frame added Qt.red > is old
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
            # Always print errors
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
        _debug_print("PaintCanvasWindow başlatıldı, boş tuvalle başlandı.")

        # --- Undo/Redo için eklenenler SONU ---

        # Drawing properties
        self.brush_color = initial_brush_color
        self.brush_size = initial_brush_size
        self.brush_alpha = initial_brush_color.alpha()  # Initialize brush_alpha from the color passed

        self.smoothing_factor = 0  # Default to no smoothing (0)
        self.is_smoothing_enabled = False  # New flag: Is smoothing actively enabled by the checkbox?
        # Initialize is_smoothing_enabled based on initial smoothing_factor from config
        initial_config_smoothing = self.main_window_ref.app_config.get("initial_smoothing_factor", 0)
        if initial_config_smoothing > 0:
            self.is_smoothing_enabled = True
            self.smoothing_factor = initial_config_smoothing  # Set initial factor
        else:
            self.smoothing_factor = 0
            self.is_smoothing_enabled = False  # Explicitly set to false if default is 0

        self.active_tool = "pen"  # Default tool
        self.eraser_size = 20  # Silgi için başlangıç boyutu, kalemden ayrı tutulacak
        self.line_style = Qt.SolidLine  # Varsayılan çizgi stili: Düz Çizgi
        self.whiteboard_mode = False  # Beyaz tahta modu varsayılan olarak kapalı

        self.drawing = False  # Flag to indicate if drawing is active
        self.moving_image = False  # Flag to indicate if image is being moved
        self.space_pressed = False  # Flag for spacebar (hand tool)

        # Resizing specific attributes
        self.resizing = False
        self.resize_anchor = None  # e.g., 'bottom_right'
        self.resize_handle_size = 10  # pixels for the resize handle
        self.original_pixmap_size = QSize()  # Stores initial size when resizing starts
        self.current_preview_rect = QRect()  # Stores the rectangle for resize preview

        self.last_point = QPoint()  # Last point for continuous drawing (pen/eraser) - actual mouse position
        self.last_drawn_point = QPoint()  # Last point that was actually drawn to (for smoothing)
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
            _debug_print("Warning: 'tool_window_position' not found in app_config.json. Using default positioning.")
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
            # When setting color, apply the current brush_alpha unless it's a highlight tool
            if self.active_tool != "highlight":
                color_with_alpha = QColor(color.red(), color.green(), color.blue(), self.brush_alpha)
            else:
                # Highlighter tool handles its own alpha (it's already set to 128 when selected)
                color_with_alpha = QColor(color.red(), color.green(), color.blue(), color.alpha())
            self.brush_color = color_with_alpha
            # Update the selected color indicator in the tool window
            if self.tool_window:
                self.tool_window.set_selected_color_indicator(color_with_alpha)
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

    def set_brush_alpha(self, alpha):
        """Sets the current brush alpha (opacity) and updates the brush color accordingly."""
        try:
            self.brush_alpha = alpha
            # Update the brush color to reflect the new alpha, keeping the RGB values
            current_rgb = self.brush_color.rgb()  # Get current RGB without alpha
            new_color = QColor(current_rgb)
            new_color.setAlpha(self.brush_alpha)
            self.brush_color = new_color
            # Update the selected color indicator in the tool window to reflect the alpha
            if self.tool_window:
                self.tool_window.set_selected_color_indicator(self.brush_color)
            _debug_print(f"Fırça alfa değeri ayarlandı: {self.brush_alpha}")
        except Exception as e:
            log_error(f"Fırça alfa değeri ayarlanırken hata: {e}", sys.exc_info())

    def set_smoothing_factor(self, factor):
        """Sets the current smoothing factor for drawing."""
        try:
            self.smoothing_factor = factor
            _debug_print(f"Düzleştirme faktörü ayarlandı: {self.smoothing_factor}")
        except Exception as e:
            log_error(f"Düzleştirme faktörü ayarlanırken hata: {e}", sys.exc_info())

    def set_line_style(self, style):
        """Sets the current line style (Solid, Dash, Dot)."""
        try:
            self.line_style = style
            _debug_print(f"Çizgi stili ayarlandı: {style}")
        except Exception as e:
            log_error(f"Çizgi stili ayarlanırken hata: {e}", sys.exc_info())

    def clear_all_drawings(self):
        """Çizim katmanındaki tüm çizimleri temizler ve geri alma/yineleme yığınını sıfırlar."""
        try:
            self.overlay_image.fill(Qt.transparent)  # Çizim katmanını şeffaf renkle doldur
            self.save_drawing_state()  # Yeni boş durumu kaydet (undo stack için)
            self.update()  # Tuvalin temizlendiğini göstermek için yeniden boyama iste
            self._save_current_drawing_auto()  # Otomatik kaydetme burada tetiklenir
        except Exception as e:
            log_error(f"Çizimleri temizlerken hata: {e}", sys.exc_info())

    def save_drawing_state(self):
        """Çizim katmanının mevcut durumunu geri alma yığınına kaydeder."""
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
            # _debug_print(f"Durum kaydedildi. Stack boyutu: {len(self.undo_stack)}, Index: {self.undo_index}")

            # Otomatik kaydetme artık burada çağrılmıyor

        except Exception as e:
            log_error(f"Çizim durumu kaydedilirken hata: {e}", sys.exc_info())

    def undo_drawing(self):
        """Son çizim eylemini geri alır."""
        try:
            if self.undo_index > 0:
                self.undo_index -= 1
                self.overlay_image = self.undo_stack[self.undo_index]
                self.update()
                # Otomatik kaydetme artık burada çağrılmıyor
            else:
                _debug_print("Geri alınacak başka çizim yok.")
        except Exception as e:
            log_error(f"Geri alma işlemi sırasında hata: {e}", sys.exc_info())

    def redo_drawing(self):
        """Geri alınan son çizim eylemini tekrar yapar."""
        try:
            if self.undo_index < len(self.undo_stack) - 1:
                self.undo_index += 1
                self.overlay_image = self.undo_stack[self.undo_index]
                self.update()
                # Otomatik kaydetme artık burada çağrılmıyor
            else:
                _debug_print("İleri alınacak başka çizim yok.")
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
            # Otomatik kaydetme artık burada çağrılmıyor
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

            # --- Hata Ayıklama İçin Geçici PNG Kaydı ---
            temp_debug_file = os.path.join(os.path.dirname(__file__), 'debug_overlay_temp.png')
            self.overlay_image.save(temp_debug_file, "PNG")
            _debug_print(f"Hata ayıklama için geçici çizim kaydedildi: {temp_debug_file}")
            # --- Hata Ayıklama İçin Geçici PNG Kaydı SONU ---

            buffer = QBuffer()
            buffer.open(QBuffer.WriteOnly)
            self.overlay_image.save(buffer, "PNG")
            png_data = buffer.data()
            buffer.close()

            base64_data = png_data.toBase64().data().decode('utf-8')

            has_visible_content = _check_qimage_for_visible_content(self.overlay_image)

            _debug_print(f"Saved overlay_image contains visible content: {has_visible_content}")
            _debug_print(
                f"Otomatik kaydedildi. Resim Boyutu: {self.overlay_image.size().width()}x{self.overlay_image.size().height()}, Base64 Uzunluğu: {len(base64_data)}")

            with open(_AUTO_SAVE_DRAWING_FILE, 'w', encoding='utf-8') as f:
                f.write(base64_data)
        except Exception as e:
            log_error(f"Otomatik çizim kaydedilirken hata: {e}", sys.exc_info())

    def toggle_whiteboard_mode(self):
        """Toggles between normal drawing mode and whiteboard mode."""
        try:
            self.whiteboard_mode = not self.whiteboard_mode
            if self.whiteboard_mode:
                # Clear existing drawings and background when entering whiteboard mode
                self.overlay_image.fill(Qt.transparent)
                self.background_pixmap = QPixmap()  # Clear background image
                QMessageBox.information(self, "Mod Değişikliği", "Beyaz Tahta Modu AÇIK. Arka plan temizlendi.")
            else:
                # When exiting whiteboard mode, clear overlay but don't restore old screenshot
                self.overlay_image.fill(Qt.transparent)
                QMessageBox.information(self, "Mod Değişikliği",
                                        "Beyaz Tahta Modu KAPALI. Tuval varsayılana döndürüldü.")

            self.save_drawing_state()  # Save new state to undo stack
            self._save_current_drawing_auto()  # Auto-save
            self.update()  # Repaint
        except Exception as e:
            log_error(f"toggle_whiteboard_mode hatası: {e}", sys.exc_info())

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
                    self.last_point = event.pos()  # Initialize last_point to the actual mouse position
                    self.last_drawn_point = event.pos()  # Initialize last_drawn_point for smoothing to current pos
                    self.temp_start_point = event.pos()  # These are now always window-relative

                    # Add debug print for brush color alpha
                    _debug_print(
                        f"Drawing initiated. Active tool: {self.active_tool}, Brush color alpha: {self.brush_color.alpha()}")

                    # Start QPainter for continuous drawing (pen, eraser, highlight)
                    if self.active_tool in ["pen", "eraser",
                                            "highlight"]:  # HIGHLIGHT added back here for continuous drawing
                        self.painter = QPainter(self.overlay_image)
                        # Enable antialiasing for continuous drawing
                        self.painter.setRenderHint(QPainter.Antialiasing, True)

                        if self.active_tool == "eraser":
                            self.painter.setCompositionMode(QPainter.CompositionMode_Clear)
                            # Silgi kalınlığı için self.eraser_size kullan
                            pen = QPen(Qt.transparent, self.eraser_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        elif self.active_tool == "highlight":
                            # Use Lighten for highlight to prevent infinite brightening/darkening when redrawing
                            self.painter.setCompositionMode(QPainter.CompositionMode_Lighten)
                            # Use brush_size for highlight thickness and current brush_color (with its alpha)
                            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                        else:  # Pen
                            self.painter.setCompositionMode(
                                QPainter.CompositionMode_SourceOver)  # Keep SourceOver for blending
                            # Use the selected line style for the pen tool
                            # Use self.brush_color which already has the correct alpha
                            pen = QPen(self.brush_color, self.brush_size, self.line_style, Qt.RoundCap, Qt.RoundJoin)
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
                current_mouse_pos = event.pos()

                if self.active_tool in ["pen", "highlight"] and self.painter:
                    # Only apply smoothing if the flag is enabled AND smoothing_factor is > 0
                    if self.is_smoothing_enabled and self.smoothing_factor > 0:
                        max_smoothing_value = 10  # Matches QSpinBox max
                        smoothing_normalized = self.smoothing_factor / max_smoothing_value

                        # Calculate the new smoothed point
                        blended_x = self.last_drawn_point.x() + (current_mouse_pos.x() - self.last_drawn_point.x()) * (
                                    1.0 - smoothing_normalized)
                        blended_y = self.last_drawn_point.y() + (current_mouse_pos.y() - self.last_drawn_point.y()) * (
                                    1.0 - smoothing_normalized)
                        new_point_smoothed = QPoint(int(blended_x), int(blended_y))

                        # Always draw from the last drawn smoothed point to the newly calculated smoothed point
                        self.painter.drawLine(self.last_drawn_point, new_point_smoothed)
                        self.last_drawn_point = new_point_smoothed  # Update to the new smoothed point

                    else:  # No smoothing, or smoothing explicitly disabled
                        # When no smoothing, simply draw from the last actual mouse point to the current mouse point
                        self.painter.drawLine(self.last_point, current_mouse_pos)
                        # For no smoothing, last_drawn_point should also follow the raw mouse movement
                        self.last_drawn_point = current_mouse_pos

                elif self.active_tool == "eraser" and self.painter:
                    # Eraser clears, so overlapping is not a concern, and precise clearing needs all movements
                    self.painter.drawLine(self.last_point, current_mouse_pos)

                # No longer need separate highlight logic here as it's part of continuous drawing
                # elif self.active_tool == "highlight": # This block is removed
                #     self.temp_end_point = current_mouse_pos

                # Always update last_point to the current mouse position for the next event,
                # as it represents the *actual* mouse position at this moment.
                self.last_point = current_mouse_pos
                self.temp_end_point = current_mouse_pos  # For shape previews
                self.update()
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
                    # HIGHLIGHT removed from this list as it's now continuous
                    if self.active_tool in ["line", "rect", "ellipse"]:
                        painter = QPainter(self.overlay_image)
                        painter.setRenderHint(QPainter.Antialiasing, True)

                        # Set normal blending for other shapes
                        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                        painter.setPen(
                            QPen(self.brush_color, self.brush_size, self.line_style, Qt.RoundCap, Qt.RoundJoin))

                        if self.active_tool == "line":
                            painter.drawLine(self.temp_start_point, event.pos())
                        elif self.active_tool == "rect":
                            painter.drawRect(QRect(self.temp_start_point, event.pos()).normalized())
                        elif self.active_tool == "ellipse":
                            painter.drawEllipse(QRect(self.temp_start_point, event.pos()).normalized())
                        painter.end()

                    self.drawing = False  # Reset drawing flag after all operations
                    self.update()  # Request repaint for the whole window
                    self.save_drawing_state()  # Çizim bittikten sonra durumu kaydet (undo stack için)
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

            # 1) Fill the entire canvas background with light gray or white based on whiteboard_mode
            if self.whiteboard_mode:
                painter.fillRect(self.rect(), Qt.white)
            else:
                painter.fillRect(self.rect(), QColor(245, 245, 245))

            # 2) Draw the background pixmap (if any) at its current position
            # Only draw background pixmap if not in whiteboard mode
            if not self.background_pixmap.isNull() and not self.whiteboard_mode:
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
            _debug_print(
                f"paintEvent: overlay_image isNull: {self.overlay_image.isNull()}, Size: {self.overlay_image.size().width()}x{self.overlay_image.size().height()}, Format: {self.overlay_image.format()}")

            # 4) Draw preview for shape tools (line, rect, ellipse) using window-relative coordinates
            # HIGHLIGHT removed from this list as it no longer uses a shape preview
            if self.drawing and self.active_tool in ["line", "rect", "ellipse"]:
                # Existing logic for line, rect, ellipse previews
                pen = QPen(self.brush_color, self.brush_size, self.line_style, Qt.RoundCap, Qt.RoundJoin)
                pen.setStyle(Qt.DashLine)
                painter.setPen(pen)
                if self.active_tool == "line":
                    painter.drawLine(self.temp_start_point, self.temp_end_point)
                elif self.active_tool == "rect":
                    painter.drawRect(QRect(self.temp_start_point, self.temp_end_point).normalized())
                elif self.active_tool == "ellipse":
                    painter.drawEllipse(QRect(self.temp_start_point, self.temp_end_point).normalized())
                # Reset composition mode to default after drawing preview to avoid affecting other elements
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            # 5) Draw the resize handle and preview rectangle if resizing is active
            if not self.background_pixmap.isNull():
                # Always draw the resize handle if the image is present
                image_rect = QRect(self.image_pos, self.background_pixmap.size())
                handle_rect = QRect(
                    image_rect.bottomRight() - QPoint(self.resize_handle_size, self.resize_handle_size),
                    QSize(self.resize_handle_size, self.resize_handle_size)
                )
                painter.fillRect(handle_rect, QColor(255, 0, 0, 255))  # red non-transparent box for handle

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
            self._save_current_drawing_auto()  # Otomatik kaydetme burada tetiklenir
            _debug_print("Çizim penceresi kapatılırken otomatik kaydetme tetiklendi.")

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
        self.setFixedSize(120, 600)  # Set fixed size for UI elements (increased for new button)
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
            _debug_print("Warning: 'selected_color_indicator' QLabel not found in pen_tool.ui.")
            log_error("UI'da 'selected_color_indicator' QLabel bulunamadı.")

        # Connect tool buttons using their object names from .ui
        pen_btn = self.findChild(QPushButton, "pen_btn")
        if pen_btn:
            # Connect to the new select_pen method
            pen_btn.clicked.connect(self.select_pen)
        else:
            _debug_print("Warning: 'pen_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'pen_btn' butonu bulunamadı.")

        eraser_btn = self.findChild(QPushButton, "eraser_btn")
        if eraser_btn:
            eraser_btn.clicked.connect(lambda: self.set_tool("eraser"))
        else:
            _debug_print("Warning: 'eraser_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'eraser_btn' butonu bulunamadı.")

        line_btn = self.findChild(QPushButton, "line_btn")
        if line_btn:
            line_btn.clicked.connect(lambda: self.set_tool("line"))
        else:
            _debug_print("Warning: 'line_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'line_btn' butonu bulunamadı.")

        rect_btn = self.findChild(QPushButton, "rect_btn")
        if rect_btn:
            rect_btn.clicked.connect(lambda: self.set_tool("rect"))
        else:
            _debug_print("Warning: 'rect_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'rect_btn' butonu bulunamadı.")

        ellipse_btn = self.findChild(QPushButton, "ellipse_btn")
        if ellipse_btn:
            ellipse_btn.clicked.connect(lambda: self.set_tool("ellipse"))
        else:
            _debug_print("Warning: 'ellipse_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'ellipse_btn' butonu bulunamadı.")

        highlight_btn = self.findChild(QPushButton, "highlight_btn")
        if highlight_btn:
            highlight_btn.clicked.connect(self.select_highlighter)
        else:
            _debug_print("Warning: 'highlight_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'highlight_btn' butonu bulunamadı.")

        self.move_btn = self.findChild(QPushButton, "move_btn")
        if self.move_btn:
            self.move_btn.clicked.connect(lambda: self.paint_window._toggle_move_tool())
        else:
            _debug_print("Warning: 'move_btn' not found in pen_tool.ui. Move tool functionality will be unavailable.")
            log_error("UI'da 'move_btn' bulunamadı.")

        self.clear_all_btn = self.findChild(QPushButton, "clear_all_btn")
        if self.clear_all_btn:
            self.clear_all_btn.clicked.connect(self.clear_all_drawings_in_paint_window)
        else:
            _debug_print(
                "Warning: 'clear_all_btn' not found in pen_tool.ui. Clear all functionality will be unavailable.")
            log_error("UI'da 'clear_all_btn' bulunamadı.")

        # --- Undo/Redo butonları bağlantısı ---
        self.undo_btn = self.findChild(QPushButton, "undo")
        if self.undo_btn:
            self.undo_btn.clicked.connect(self.paint_window.undo_drawing)
        else:
            _debug_print("Warning: 'undo' button not found in pen_tool.ui.")
            log_error("UI'da 'undo' butonu bulunamadı.")

        self.redo_btn = self.findChild(QPushButton, "redo")
        if self.redo_btn:
            self.redo_btn.clicked.connect(self.paint_window.redo_drawing)
        else:
            _debug_print("Warning: 'redo' button not found in pen_tool.ui.")
            log_error("UI'da 'redo' butonu bulunamadı.")
        # --- Undo/Redo butonları bağlantısı SONU ---

        # --- Otomatik Kayıt Yükle Butonu ---
        self.load_commands_btn = self.findChild(QPushButton, "load_commands_btn")
        if self.load_commands_btn:
            self.load_commands_btn.clicked.connect(
                self._load_auto_saved_drawing)  # Otomatik kaydı yükleyen metot bağlandı
        else:
            _debug_print(
                "Warning: 'load_commands_btn' button not found in pen_tool.ui. Load auto-saved drawing functionality will be unavailable.")
            log_error("UI'da 'load_commands_btn' butonu bulunamadı.")
        # --- Otomatik Kayıt Yükle Butonu SONU ---

        # --- KALEM RENKLERİNİ app_config.json'dan DİNAMİK YÜKLEME ---
        self.load_tool_window_colors_from_config()
        # --- KALEM RENKLERİNİ DİNAMİK YÜKLEME SONU ---

        # Connect brush size spin box (for pen and shapes)
        self.brushSizeSpinBox = self.findChild(QSpinBox, "brushSizeSpinBox")
        if self.brushSizeSpinBox:
            self.brushSizeSpinBox.setMinimum(1)
            self.brushSizeSpinBox.setMaximum(50)
            self.brushSizeSpinBox.setValue(self.paint_window.brush_size)  # Set initial value
            self.brushSizeSpinBox.valueChanged.connect(self.change_brush_size)
        else:
            _debug_print(
                "Warning: 'brushSizeSpinBox' not found in pen_tool.ui. Brush size control will be unavailable.")
            log_error("UI'da 'brushSizeSpinBox' bulunamadı.")

        # Connect pen opacity spin box
        self.penOpacitySpinBox = self.findChild(QSpinBox, "penOpacitySpinBox")
        if self.penOpacitySpinBox:
            self.penOpacitySpinBox.setMinimum(0)  # 0 for fully transparent
            self.penOpacitySpinBox.setMaximum(255)  # 255 for fully opaque
            self.penOpacitySpinBox.setValue(self.paint_window.brush_alpha)  # Set initial alpha value
            self.penOpacitySpinBox.valueChanged.connect(self.change_pen_opacity)
        else:
            _debug_print(
                "Warning: 'penOpacitySpinBox' not found in pen_tool.ui. Pen opacity control will be unavailable.")
            log_error("UI'da 'penOpacitySpinBox' bulunamadı.")

        # Connect smoothing spin box and checkbox
        self.smoothingSpinBox = self.findChild(QSpinBox, "smoothingSpinBox")
        self.smoothing_enable_checkbox = self.findChild(QtWidgets.QCheckBox, "smoothing_enable_checkbox")

        if self.smoothingSpinBox and self.smoothing_enable_checkbox:
            self.smoothingSpinBox.setMinimum(0)
            self.smoothingSpinBox.setMaximum(10)
            self.smoothingSpinBox.setValue(self.paint_window.smoothing_factor)
            self.smoothingSpinBox.valueChanged.connect(self.change_smoothing_factor)

            # Initialize checkbox state based on current smoothing factor
            initial_smoothing_enabled = (self.paint_window.smoothing_factor > 0)
            self.smoothing_enable_checkbox.setChecked(initial_smoothing_enabled)
            self.smoothingSpinBox.setEnabled(initial_smoothing_enabled)  # Disable if smoothing is off

            self.smoothing_enable_checkbox.toggled.connect(self.toggle_smoothing_enabled)
        else:
            _debug_print("Warning: 'smoothingSpinBox' or 'smoothing_enable_checkbox' not found in pen_tool.ui.")
            log_error("UI'da 'smoothingSpinBox' veya 'smoothing_enable_checkbox' bulunamadı.")

        # Store last non-zero smoothing factor, used when re-enabling
        self._last_smoothing_factor_value = self.paint_window.smoothing_factor if self.paint_window.smoothing_factor > 0 else 5  # Default to 5 if initial is 0

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
            _debug_print("Warning: 'eraser_slider' not found in pen_tool.ui. Eraser size control will be unavailable.")
            log_error("UI'da 'eraser_slider' bulunamadı.")

        exit_btn = self.findChild(QPushButton, "exit_btn")
        if exit_btn:
            exit_btn.clicked.connect(self.close)
        else:
            _debug_print("Warning: 'exit_btn' button not found in pen_tool.ui.")
            log_error("UI'da 'exit_btn' butonu bulunamadı.")

        # --- Çizgi Stili Butonları ---
        self.solid_line_btn = self.findChild(QPushButton, "solid_line_btn")
        if self.solid_line_btn:
            self.solid_line_btn.clicked.connect(lambda: self.paint_window.set_line_style(Qt.SolidLine))
            # Set a visual indicator for active line style if desired (e.g., border)
            self.solid_line_btn.setStyleSheet("QPushButton { border: 2px solid blue; }")  # Example active style
        else:
            _debug_print("Warning: 'solid_line_btn' not found in pen_tool.ui.")

        self.dash_line_btn = self.findChild(QPushButton, "dash_line_btn")
        if self.dash_line_btn:
            self.dash_line_btn.clicked.connect(lambda: self.paint_window.set_line_style(Qt.DashLine))
        else:
            _debug_print("Warning: 'dash_line_btn' not found in pen_tool.ui.")

        self.dot_line_btn = self.findChild(QPushButton, "dot_line_btn")
        if self.dot_line_btn:
            self.dot_line_btn.clicked.connect(lambda: self.paint_window.set_line_style(Qt.DotLine))
        else:
            _debug_print("Warning: 'dot_line_btn' not found in pen_tool.ui.")
        # --- Çizgi Stili Butonları SONU ---

        # --- Beyaz Tahta Modu Butonu ---
        self.whiteboard_btn = self.findChild(QPushButton, "whiteboard_btn")
        if self.whiteboard_btn:
            self.whiteboard_btn.clicked.connect(self.toggle_whiteboard_mode_in_paint_window)
            self._update_whiteboard_button_text()  # Set initial text
        else:
            _debug_print("Warning: 'whiteboard_btn' not found in pen_tool.ui.")
            log_error("UI'da 'whiteboard_btn' butonu bulunamadı.")
        # --- Beyaz Tahta Modu Butonu SONU ---

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
                if btn:  # Check if the button was successfully found in __init__
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
                                _debug_print(
                                    f"Uyarı (ToolWindow): Geçersiz renk değeri '{color_str}' app_config.json'da bulundu.")
                                log_error(f"ToolWindow: Geçersiz renk değeri app_config.json'da: {color_str}")
                                btn.hide()  # Hide button if color is invalid
                        except Exception as e:
                            _debug_print(f"ToolWindow renk butonu ayarlanırken hata oluştu: {color_str} - {e}")
                            log_error(f"ToolWindow renk butonu ayarlanırken hata: {color_str} - {e}", sys.exc_info())
                            btn.hide()  # Hide button on error
                    else:
                        btn.hide()  # Hide buttons if there are no corresponding colors in config
                else:
                    _debug_print(f"Uyarı (ToolWindow): {color_button_names[i]} isimli buton UI dosyasında bulunamadı.")
        else:
            _debug_print(
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

    def select_pen(self):
        """
        Sets the active tool to 'pen' and ensures the brush color is fully opaque (alpha 255).
        """
        try:
            if self.paint_window:
                self.paint_window.brush_alpha = 255  # Set alpha to fully opaque
                current_base_color = QColor(self.paint_window.brush_color)
                current_base_color.setAlpha(255)  # Apply full opacity to current color
                self.paint_window.set_brush_color(current_base_color)  # Update brush color in paint window
                self.paint_window.set_tool("pen")  # Set tool to pen
                self.set_selected_color_indicator(current_base_color)  # Update indicator
                if self.penOpacitySpinBox:
                    self.penOpacitySpinBox.setValue(255)  # Sync opacity spin box
        except Exception as e:
            log_error(f"Kalem seçilirken hata: {e}", sys.exc_info())

    def set_color_and_update_main(self, color):
        """
        Delegates color setting to the parent paint window and updates
        this tool window's color indicator. Ensures the brush color is
        fully opaque unless the highlighter tool is active.
        """
        try:
            q_color_obj = QColor(color)
            # When selecting a new color from the palette, apply the current brush_alpha
            # which is correctly managed by select_pen() and select_highlighter().
            q_color_obj.setAlpha(self.paint_window.brush_alpha)

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

    def change_pen_opacity(self, value):
        """Delegates pen opacity (alpha) change to the parent paint window."""
        try:
            if self.paint_window:
                self.paint_window.set_brush_alpha(value)
        except Exception as e:
            log_error(f"ToolWindow kalem saydamlığı değiştirilirken hata: {e}", sys.exc_info())

    def toggle_smoothing_enabled(self, checked):
        """Toggles smoothing on/off based on checkbox state."""
        try:
            if self.paint_window:
                self.paint_window.is_smoothing_enabled = checked
                if self.smoothingSpinBox:
                    self.smoothingSpinBox.setEnabled(checked)

                if checked:
                    # When enabling, restore the last used smoothing factor or default if it was 0
                    if self.paint_window.smoothing_factor == 0:  # If it was off, restore previous non-zero value
                        self.paint_window.set_smoothing_factor(self._last_smoothing_factor_value)
                        if self.smoothingSpinBox:
                            self.smoothingSpinBox.setValue(self._last_smoothing_factor_value)  # Sync spinbox
                    else:  # If it was already on, just ensure sync
                        if self.smoothingSpinBox:
                            self.paint_window.set_smoothing_factor(self.smoothingSpinBox.value())

                else:
                    # When disabling, store current value and set smoothing to 0
                    if self.smoothingSpinBox:
                        self._last_smoothing_factor_value = self.smoothingSpinBox.value()  # Store the current value before setting to 0
                    self.paint_window.set_smoothing_factor(0)  # Disable smoothing
                    if self.smoothingSpinBox:
                        self.smoothingSpinBox.setValue(0)  # Sync spinbox
            _debug_print(
                f"Smoothing enabled: {checked}, Current smoothing factor: {self.paint_window.smoothing_factor}")
        except Exception as e:
            log_error(f"Düzleştirme etkinleştirme/devre dışı bırakma hatası: {e}", sys.exc_info())

    def change_smoothing_factor(self, value):
        """Delegates smoothing factor change to the parent paint window and updates stored value."""
        try:
            if self.paint_window:
                # Update the paint window's smoothing factor only if smoothing is enabled
                if self.paint_window.is_smoothing_enabled:
                    self.paint_window.set_smoothing_factor(value)
                    self._last_smoothing_factor_value = value  # Also update the stored value
                else:
                    # If smoothing is disabled, we only update the stored value, not the active one
                    self._last_smoothing_factor_value = value
            _debug_print(f"Smoothing factor changed to: {value}, Last stored: {self._last_smoothing_factor_value}")
        except Exception as e:
            log_error(f"ToolWindow düzleştirme faktörü değiştirilirken hata: {e}", sys.exc_info())

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
                # Force alpha to 128 (50% transparency) for highlighter when selected
                current_base_color.setAlpha(128)
                self.paint_window.set_brush_color(current_base_color)
                self.paint_window.set_tool("highlight")  # Aracı "highlight" olarak ayarla
                self.set_selected_color_indicator(current_base_color)  # Update indicator with highlight color
                # Sync penOpacitySpinBox to highlighter's alpha if it exists
                if self.penOpacitySpinBox:
                    self.penOpacitySpinBox.setValue(128)  # Set to 128 (50% transparency) for highlighter
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
        _debug_print("ToolWindow._load_auto_saved_drawing called (Yükle butonu).")
        try:
            # Check if the auto-save file exists and has content
            if not os.path.exists(_AUTO_SAVE_DRAWING_FILE) or os.path.getsize(_AUTO_SAVE_DRAWING_FILE) == 0:
                QMessageBox.information(self, "Bilgi",
                                        "Otomatik kaydedilen çizim dosyası bulunamadı veya boş. Lütfen önce bir çizim yapın ve kaydedilmesini bekleyin.")
                _debug_print(
                    f"ToolWindow._load_auto_saved_drawing: Otomatik kayıt dosyası bulunamadı veya boş: {_AUTO_SAVE_DRAWING_FILE}")
                return

            with open(_AUTO_SAVE_DRAWING_FILE, 'r', encoding='utf-8') as f:
                base64_data = f.read()
            _debug_print(f"ToolWindow._load_auto_saved_drawing ile okunan Base64 veri uzunluğu: {len(base64_data)}")

            if not base64_data.strip():
                QMessageBox.information(self, "Bilgi", "Otomatik kaydedilen çizim dosyası boş.")
                _debug_print("ToolWindow._load_auto_saved_drawing: Otomatik kaydedilen çizim dosyası boş.")
                return

            # Decode Base64 data to PNG byte array
            png_data = QByteArray().fromBase64(base64_data.encode('utf-8'))

            loaded_image = QImage()
            # Attempt to load the QImage from the PNG byte array
            load_success = loaded_image.loadFromData(png_data, "PNG")
            _debug_print(
                f"ToolWindow._load_auto_saved_drawing ile loaded_image.loadFromData başarı: {load_success}, isNull: {loaded_image.isNull()}")

            if load_success and not loaded_image.isNull():
                _debug_print(
                    f"ToolWindow._load_auto_saved_drawing ile yüklenen orijinal resim boyutu: {loaded_image.size().width()}x{loaded_image.size().height()}")

                # Check if the loaded image has visible content
                if not _check_qimage_for_visible_content(loaded_image):
                    QMessageBox.information(self, "Bilgi",
                                            "Otomatik kaydedilen çizim başarıyla yüklendi, ancak içeriği boş veya tamamen şeffaf.")
                    _debug_print("Yüklenen çizimin görünür içeriği yok (otomatik yükleme).")
                else:
                    QMessageBox.information(self, "Yükleme Tamamlandı", "Otomatik kaydedilen çizim başarıyla yüklendi.")

                # Scale the loaded image to the current paint window size if dimensions differ
                if loaded_image.size() != self.paint_window.size():
                    scaled_image = loaded_image.scaled(self.paint_window.size(),
                                                       Qt.IgnoreAspectRatio,  # En boy oranını korumadan doldur
                                                       Qt.SmoothTransformation)  # Smooth scaling for better quality
                    self.paint_window.set_overlay_image(scaled_image)
                    _debug_print(
                        f"ToolWindow._load_auto_saved_drawing ile yüklenen resim pencere boyutuna ölçeklendi: {scaled_image.size().width()}x{scaled_image.size().height()}")
                else:
                    # If sizes match, set the image directly
                    self.paint_window.set_overlay_image(loaded_image)
                    _debug_print(
                        f"ToolWindow._load_auto_saved_drawing ile yüklenen resim doğrudan ayarlandı. Boyut: {loaded_image.size().width()}x{loaded_image.size().height()}")

            else:
                QMessageBox.critical(self, "Yükleme Hatası",
                                     "Otomatik kaydedilen dosya geçerli bir çizim verisi içermiyor veya bozuk.")
                log_error(
                    f"Otomatik kaydedilen dosya geçerli bir çizim verisi içermiyor veya bozuk: {_AUTO_SAVE_DRAWING_FILE}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Otomatik çizim yüklenirken bir hata oluştu: {e}")
            log_error(f"Otomatik çizim yüklenirken hata: {e}", sys.exc_info())

    def toggle_whiteboard_mode_in_paint_window(self):
        """Calls the toggle_whiteboard_mode method on the parent PaintCanvasWindow and updates button text."""
        try:
            if self.paint_window:
                self.paint_window.toggle_whiteboard_mode()
                self._update_whiteboard_button_text()
        except Exception as e:
            log_error(f"Beyaz tahta modu değiştirilirken hata: {e}", sys.exc_info())

    def _update_whiteboard_button_text(self):
        """Updates the text of the whiteboard button based on the current mode."""
        try:
            if self.whiteboard_btn:
                if self.paint_window and self.paint_window.whiteboard_mode:
                    self.whiteboard_btn.setText("Beyaz Tahta Kapat")
                else:
                    self.whiteboard_btn.setText("Beyaz Tahta Aç")
        except Exception as e:
            log_error(f"Beyaz tahta butonu metni güncellenirken hata: {e}", sys.exc_info())

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


class SettingsWindow(QMainWindow):
    """
    A separate window for application settings, loaded from settings.ui.
    """

    def __init__(self, main_window_ref):
        super().__init__()
        self.main_window_ref = main_window_ref
        self.app_config = main_window_ref.app_config  # Access the shared app_config dictionary

        self.setWindowTitle("Ayarlar")
        self.setFixedSize(700, 600)  # Increased size for more settings, as color management will take space

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        script_dir = os.path.dirname(__file__)
        settings_ui_path = os.path.join(script_dir, 'data', 'settings.ui')

        if not os.path.exists(settings_ui_path):
            error_msg = f"Ayarlar UI dosyası bulunamadı: {settings_ui_path}"
            QMessageBox.critical(self, "Hata", error_msg)
            log_error(error_msg)
            self.close()
            return

        try:
            uic.loadUi(settings_ui_path, self)
        except Exception as e:
            error_msg = f"Ayarlar UI dosyası '{settings_ui_path}' yüklenirken hata oluştu: {e}"
            QMessageBox.critical(self, "Ayarlar UI Yükleme Hatası", error_msg)
            log_error(error_msg, sys.exc_info())
            self.close()
            return

        # Connect UI elements
        self.close_btn = self.findChild(QPushButton, "close_settings_btn")
        if self.close_btn:
            self.close_btn.clicked.connect(self.close_settings_window)
        else:
            _debug_print("Warning: 'close_settings_btn' not found in settings.ui.")
            log_error("UI'da 'close_settings_btn' butonu bulunamadı.")

        self.save_btn = self.findChild(QPushButton, "save_settings_btn")
        if self.save_btn:
            self.save_btn.clicked.connect(self.save_settings_from_ui)
        else:
            _debug_print("Warning: 'save_settings_btn' not found in settings.ui. Settings won't be savable.")
            log_error("UI'da 'save_settings_btn' butonu bulunamadı.")

        # New: References to the static color buttons
        self.color_buttons = []
        self.color_button_names = ["color_red", "color_blue", "color_black",
                                   "color_green", "color_custom1", "color_custom2"]

        for i, btn_name in enumerate(self.color_button_names):
            btn = self.findChild(QPushButton, btn_name)
            if btn:
                self.color_buttons.append(btn)
                # Connect the button's clicked signal to the handler method, passing its index
                btn.clicked.connect(lambda checked, idx=i: self.edit_fixed_color_button(idx))
            else:
                _debug_print(f"Warning: Color button '{btn_name}' not found in settings.ui.")
                log_error(f"UI'da '{btn_name}' butonu bulunamadı.")
                # Append None or an empty button if not found to maintain index consistency if needed
                self.color_buttons.append(None)

                # Remove dynamic color management elements as per the new UI
        # The new UI doesn't have these, so we ensure they are not referenced
        self.add_color_btn = None
        self.remove_color_btn = None
        self.color_buttons_container = None  # This is no longer the dynamic container

        # Load settings into UI fields
        self.load_settings_to_ui()
        # New: Load and display pen colors on these static buttons
        self.load_pen_colors_to_settings_ui()

    def load_settings_to_ui(self):
        """Populates the UI elements with current settings from app_config."""
        _debug_print("Loading general settings to UI...")
        try:
            # Debug Mode Checkbox
            debug_checkbox = self.findChild(QtWidgets.QCheckBox, "debug_mode_checkbox")
            if debug_checkbox:
                debug_checkbox.setChecked(self.app_config.get("debug_mode", False))
                _debug_print(f"Debug Mode Checkbox set to: {self.app_config.get('debug_mode', False)}")
            else:
                _debug_print("Warning: 'debug_mode_checkbox' not found in settings.ui.")

            # Main Window Position (assuming QSpinBox for x and y)
            main_pos = self.app_config.get("main_window_position", {"x": 100, "y": 100})
            x_input = self.findChild(QtWidgets.QSpinBox, "main_window_x_input")
            y_input = self.findChild(QtWidgets.QSpinBox, "main_window_y_input")
            if x_input:
                x_input.setValue(main_pos.get("x", 100))
                _debug_print(f"Main window X set to: {main_pos.get('x', 100)}")
            else:
                _debug_print("Warning: 'main_window_x_input' not found.")
            if y_input:
                y_input.setValue(main_pos.get("y", 100))
                _debug_print(f"Main window Y set to: {main_pos.get('y', 100)}")
            else:
                _debug_print("Warning: 'main_window_y_input' not found.")

            # App Icon Path
            app_icon_path_input = self.findChild(QtWidgets.QLineEdit, "app_icon_path_input")
            if app_icon_path_input:
                app_icon_path_input.setText(self.app_config.get("app_icon_path", ""))
                _debug_print(f"App Icon Path set to: {self.app_config.get('app_icon_path', '')}")
            else:
                _debug_print("Warning: 'app_icon_path_input' not found.")

            # UI File Paths
            main_ui_file_input = self.findChild(QtWidgets.QLineEdit, "main_ui_file_input")
            if main_ui_file_input:
                main_ui_file_input.setText(self.app_config.get("main_ui_file", "undockapp.ui"))
                _debug_print(f"Main UI File set to: {self.app_config.get('main_ui_file', 'undockapp.ui')}")
            else:
                _debug_print("Warning: 'main_ui_file_input' not found.")

            tool_ui_file_input = self.findChild(QtWidgets.QLineEdit, "tool_ui_file_input")
            if tool_ui_file_input:
                tool_ui_file_input.setText(self.app_config.get("tool_ui_file", "pen_tool.ui"))
                _debug_print(f"Tool UI File set to: {self.app_config.get('tool_ui_file', 'pen_tool.ui')}")
            else:
                _debug_print("Warning: 'tool_ui_file_input' not found.")

            _debug_print("General settings loaded to UI successfully.")

        except Exception as e:
            log_error(f"Ayarlar UI'ye yüklenirken hata: {e}", sys.exc_info())

    def load_pen_colors_to_settings_ui(self):
        """Loads pen colors from app_config and displays them on the fixed color buttons."""
        colors = self.app_config.get("pen_colors", [])
        _debug_print(f"Loading {len(colors)} pen colors to settings UI (fixed buttons).")

        for i, btn in enumerate(self.color_buttons):
            if btn:  # Check if the button was successfully found in __init__
                if i < len(colors):
                    color_str = colors[i]
                    try:
                        q_color = QColor(color_str)
                        if q_color.isValid():
                            btn.setStyleSheet(
                                f"background-color: {color_str}; border: 1px solid gray; border-radius: 5px;")
                        else:
                            _debug_print(
                                f"Uyarı: Ayarlar UI: Geçersiz renk değeri '{color_str}' app_config.json'da bulundu. Varsayılan Gri kullanılacak.")
                            log_error(f"Ayarlar UI: Geçersiz renk değeri app_config.json'da: {color_str}")
                            btn.setStyleSheet(
                                "background-color: lightgray; border: 1px solid gray; border-radius: 5px;")  # Default invalid to lightgray
                    except Exception as e:
                        log_error(f"Ayarlar UI: Renk butonu ayarlanırken hata: {color_str} - {e}", sys.exc_info())
                        btn.setStyleSheet(
                            "background-color: lightgray; border: 1px solid gray; border-radius: 5px;")  # Default on error
                else:
                    # If app_config has fewer colors than buttons, set remaining buttons to a default gray
                    btn.setStyleSheet("background-color: lightgray; border: 1px solid gray; border-radius: 5px;")
                    _debug_print(f"Bilgi: Renk {i} için app_config.json'da renk bulunamadı, varsayılan gri ayarlandı.")

    def edit_fixed_color_button(self, index):
        """
        Opens a color dialog to edit a fixed color button's color.
        Updates the app_config and refreshes the UI.
        """
        if index < 0 or index >= len(self.color_buttons) or not self.color_buttons[index]:
            _debug_print(f"Error: Invalid index {index} for color button editing.")
            return

        current_color_str = self.app_config["pen_colors"][index]
        initial_color = QColor(current_color_str)

        color = QtWidgets.QColorDialog.getColor(initial_color, self)

        if color.isValid():
            new_color_name = color.name()  # Returns color in #RRGGBB format
            _debug_print(f"Editing color at index {index} from {current_color_str} to {new_color_name}")
            self.app_config["pen_colors"][index] = new_color_name
            self.save_settings_from_ui()  # Save config and reload UI
        else:
            _debug_print("Color dialog cancelled or invalid color selected.")

    # Removed add_new_color and remove_selected_color methods as per new UI

    def save_settings_from_ui(self):
        """Reads values from UI elements and saves them to app_config.json."""
        _debug_print("Saving general settings from UI...")
        try:
            # Update debug mode
            debug_checkbox = self.findChild(QtWidgets.QCheckBox, "debug_mode_checkbox")
            if debug_checkbox:
                self.app_config["debug_mode"] = debug_checkbox.isChecked()
                # Update global debug flag immediately
                global _DEBUG_MODE_ENABLED
                _DEBUG_MODE_ENABLED = self.app_config["debug_mode"]
                _debug_print(f"Updated Debug Mode: {_DEBUG_MODE_ENABLED}")
            else:
                _debug_print("Warning: 'debug_mode_checkbox' not found for saving.")

            # Update Main Window Position
            x_input = self.findChild(QtWidgets.QSpinBox, "main_window_x_input")
            y_input = self.findChild(QtWidgets.QSpinBox, "main_window_y_input")
            if x_input and y_input:
                self.app_config["main_window_position"] = {
                    "x": x_input.value(),
                    "y": y_input.value()
                }
                _debug_print(f"Saved Main Window Position: {self.app_config['main_window_position']}")
            else:
                _debug_print("Warning: Main window position inputs not found for saving.")

            # Update App Icon Path
            app_icon_path_input = self.findChild(QtWidgets.QLineEdit, "app_icon_path_input")
            if app_icon_path_input:
                self.app_config["app_icon_path"] = app_icon_path_input.text()
                _debug_print(f"Saved App Icon Path: {self.app_config['app_icon_path']}")
            else:
                _debug_print("Warning: 'app_icon_path_input' not found for saving.")

            # Update UI File Paths
            main_ui_file_input = self.findChild(QtWidgets.QLineEdit, "main_ui_file_input")
            if main_ui_file_input:
                self.app_config["main_ui_file"] = main_ui_file_input.text()
                _debug_print(f"Saved Main UI File: {self.app_config['main_ui_file']}")
            else:
                _debug_print("Warning: 'main_ui_file_input' not found for saving.")

            tool_ui_file_input = self.findChild(QtWidgets.QLineEdit, "tool_ui_file_input")
            if tool_ui_file_input:
                self.app_config["tool_ui_file"] = tool_ui_file_input.text()
                _debug_print(f"Saved Tool UI File: {self.app_config['tool_ui_file']}")
            else:
                _debug_print("Warning: 'tool_ui_file_input' not found for saving.")

            # Save the updated app_config dictionary back to the JSON file
            config_path = os.path.join(os.path.dirname(__file__), 'data', 'app_config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.app_config, f, indent=4, ensure_ascii=False)
            _debug_print(f"app_config.json saved to: {config_path}")

            QMessageBox.information(self, "Ayarlar Kaydedildi", "Ayarlar başarıyla kaydedildi!")

            # Reload pen colors in main window and tool window after config changes
            self.main_window_ref.load_pen_colors_from_config()
            # Only try to update tool_window if it exists (i.e., if paint_window was ever opened)
            if hasattr(self.main_window_ref, 'tool_window') and self.main_window_ref.tool_window:
                self.main_window_ref.tool_window.load_tool_window_colors_from_config()
            self.load_pen_colors_to_settings_ui()  # Reload in settings UI too

        except Exception as e:
            log_error(f"Ayarlar kaydedilirken hata: {e}", sys.exc_info())
            QMessageBox.critical(self, "Kaydetme Hatası", f"Ayarlar kaydedilirken bir hata oluştu: {e}")

    def close_settings_window(self):
        """Closes the settings window and shows the main window."""
        try:
            self.close()
            if self.main_window_ref:
                self.main_window_ref.show()
        except Exception as e:
            log_error(f"Ayarlar penceresi kapatılırken hata: {e}", sys.exc_info())

    def closeEvent(self, event):
        """Overrides closeEvent to ensure main window is shown when settings window is closed."""
        try:
            if self.main_window_ref:
                self.main_window_ref.show()
        except Exception as e:
            log_error(f"Ayarlar penceresi closeEvent hatası: {e}", sys.exc_info())
        super().closeEvent(event)


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
        # Always print critical errors
        print(error_msg)
        log_error(error_msg, sys.exc_info())
        sys.exit(1)

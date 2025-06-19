import sys
import os
import traceback
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QComboBox, QMessageBox, QFrame
from PyQt5.QtCore import Qt, QPoint, QRect, QSize
from PyQt5.QtGui import QColor, QPen, QPainter, QImage, QPixmap, QCursor

# Conditional import for Windows-specific modules
try:
    import win32api
    import win32con
    import win32gui
    from PIL import ImageGrab
    WIN_SPECIFIC_IMPORTS_AVAILABLE = True
except ImportError:
    WIN_SPECIFIC_IMPORTS_AVAILABLE = False
    print("Warning: win32api, win32con, win32gui, or PIL not found. Windows-specific features (transparency, ImageGrab) will be disabled.")


class Ui(QMainWindow):
    """
    Main application window that provides options to start painting,
    take full-screen screenshots, or select a region for drawing.
    """
    def __init__(self):
        super().__init__()

        # Construct path to .ui file relative to script's location
        script_dir = os.path.dirname(__file__)
        ui_path = os.path.join(script_dir, 'data', 'undockapp.ui')

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Error", f"UI file not found: {ui_path}")
            sys.exit(1)

        # Load the UI from the .ui file
        uic.loadUi(ui_path, self)

        # Apply custom styles for a translucent background and magenta border
        self.setStyleSheet("""
            QMainWindow {
                background-color: rgba(255, 255, 255, 200); /* Semi-transparent white */
                border: 2px solid magenta;
                border-radius: 10px;
            }
        """)
        self.setAttribute(Qt.WA_TranslucentBackground) # Enable translucent background
        self.setWindowFlags(Qt.WindowStaysOnTopHint) # Keep window on top

        # Connect buttons to their respective methods
        # Corrected: Using 'quit', 'pen', 'ss', 'eraser' based on original code
        self.quit.clicked.connect(self.close) # Assumed 'quit' from .ui
        self.pen.clicked.connect(self.start_full_screen_paint) # Assumed 'pen' from .ui
        self.ss.clicked.connect(self.open_region_selector) # Assumed 'ss' from .ui
        self.eraser.clicked.connect(self.close) # Assumed 'eraser' from .ui

        # Connect color buttons
        # Corrected: Using 'red', 'blue', 'green', 'black' based on original code
        self.red.clicked.connect(lambda: self.set_color(QColor(Qt.red))) # Assumed 'red'
        self.blue.clicked.connect(lambda: self.set_color(QColor(Qt.blue))) # Assumed 'blue'
        self.green.clicked.connect(lambda: self.set_color(QColor(Qt.green))) # Assumed 'green'
        self.black.clicked.connect(lambda: self.set_color(QColor(Qt.black))) # Assumed 'black'

        # Default drawing properties
        self.active_color = QColor(Qt.red)
        self.active_size = 5
        self.hwnd = None # Window handle for win32 transparency

        # Get references to UI elements for color indicator and size combo box
        self.color_indicator = self.findChild(QLabel, "colorIndicator")
        self.size_combo = self.findChild(QComboBox, "sizeCombo")

        # Initialize color indicator and size combo box
        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {self.active_color.name()}; border-radius: 5px;")

        if self.size_combo:
            self.size_combo.addItems(["1px", "3px", "5px", "7px", "10px", "15px", "20px"])
            self.size_combo.setCurrentIndex(2) # Default to 5px
            self.size_combo.currentIndexChanged.connect(self.set_size)

    def open_region_selector(self):
        """Hides the main window and opens the region selection tool."""
        self.hide() # Ana pencereyi sadece gizle, kapatma
        self.selector = RegionSelector(self.active_color, self.active_size, self) # Ana pencere referansını geçir
        self.selector.showFullScreen()

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
                0, # Alpha value (not used with LWA_COLORKEY)
                win32con.LWA_COLORKEY # Use color key transparency
            )
        except Exception as e:
            print(f"Failed to set transparency: {e}")
            traceback.print_exc()

    def set_color(self, color):
        """Sets the active drawing color and updates the color indicator."""
        self.active_color = color
        if self.color_indicator:
            self.color_indicator.setStyleSheet(f"background-color: {color.name()}; border-radius: 5px;")

    def set_size(self, index):
        """Sets the active brush size based on the combo box selection."""
        sizes = [1, 3, 5, 7, 10, 15, 20]
        if 0 <= index < len(sizes):
            self.active_size = sizes[index]

    def start_full_screen_paint(self):
        """Hides the main window and starts a full-screen paint session."""
        self.hide()
        screenshot = self._capture_screenshot_pixmap()
        if screenshot:
            try:
                self.paint_window = PaintCanvasWindow(
                    screenshot,
                    self.active_color,
                    self.active_size,
                    self # Ana pencere referansını geçir
                )
                self.paint_window.showFullScreen()
            except Exception as e:
                print(f"Failed to create full-screen paint window: {e}")
                traceback.print_exc()
                self.show() # Show main window if paint window fails
        else:
            self.show() # Show main window if screenshot fails

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
            max_width = min(screen_rect.width(), 1920)
            max_height = min(screen_rect.height(), 1080)

            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(QSize(max_width, max_height),
                                       Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
            return pixmap
        except Exception as e:
            print(f"Failed to capture screenshot: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Screenshot Error", "Failed to capture screenshot.")
            return None


class RegionSelector(QWidget):
    """
    Allows the user to select a rectangular region on the screen for screenshotting.
    """
    def __init__(self, brush_color, brush_size, main_window_ref): # Ana pencere referansını al
        super().__init__()
        self.brush_color = brush_color
        self.brush_size = brush_size
        self.main_window_ref = main_window_ref # Referansı sakla

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.3) # Semi-transparent overlay
        self.setStyleSheet("background-color: gray;")
        self.begin = QPoint()
        self.end = QPoint()
        self.setCursor(Qt.CrossCursor) # Crosshair cursor for selection

        # Set geometry to cover the primary screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def mousePressEvent(self, event):
        """Records the starting point of the selection."""
        if event.button() == Qt.LeftButton:
            self.begin = event.pos()
            self.end = event.pos()
            self.update() # Trigger repaint to show initial rectangle

    def mouseMoveEvent(self, event):
        """Updates the end point of the selection as the mouse moves."""
        if event.buttons() & Qt.LeftButton: # Only if left button is held down
            self.end = event.pos()
            self.update() # Trigger repaint to update rectangle

    def mouseReleaseEvent(self, event):
        """
        Finalizes the selection, closes the selector, and opens the paint window
        with the cropped screenshot.
        """
        if event.button() == Qt.LeftButton:
            self.close() # Close the selector window

            x1 = min(self.begin.x(), self.end.x())
            y1 = min(self.begin.y(), self.end.y())
            x2 = max(self.begin.x(), self.end.x())
            y2 = max(self.begin.y(), self.end.y())
            self.selected_rect = QRect(x1, y1, x2 - x1, y2 - y1)

            if self.selected_rect.width() > 0 and self.selected_rect.height() > 0:
                self.capture_and_open_paint()
            else:
                # If no valid region selected, just go back to main window
                if self.main_window_ref:
                    self.main_window_ref.show() # Orijinal ana pencereyi göster
                self.close() # RegionSelector'ı kapat

    def paintEvent(self, event):
        """Draws the transparent gray overlay and the red selection rectangle."""
        painter = QPainter(self)
        # Draw the semi-transparent gray background (done by stylesheet now, but can be drawn here too)
        # painter.fillRect(self.rect(), QColor(128, 128, 128, 100)) # Example: semi-transparent gray

        # Draw the selection rectangle
        painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
        painter.drawRect(QRect(self.begin, self.end))

    def capture_and_open_paint(self):
        """Captures the selected region and opens the paint window."""
        try:
            screen = QApplication.primaryScreen()
            # Grab only the selected portion of the screen
            pixmap = screen.grabWindow(0, self.selected_rect.x(), self.selected_rect.y(),
                                       self.selected_rect.width(), self.selected_rect.height())

            # Open PaintCanvasWindow with the selected region screenshot
            paint_window = PaintCanvasWindow(pixmap, self.brush_color, self.brush_size, self.main_window_ref) # Ana pencere referansını geçir
            paint_window.show()
        except Exception as e:
            print(f"Error capturing region or opening paint window: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", "Failed to capture region or open paint window.")
            # Reopen main UI if something goes wrong
            if self.main_window_ref:
                self.main_window_ref.show() # Orijinal ana pencereyi göster


class PaintCanvasWindow(QMainWindow):
    """
    A window that displays a screenshot and allows the user to draw on it
    with various tools (pen, eraser, shapes, highlighter).
    It also hosts the ToolWindow.
    """
    def __init__(self, background_pixmap, initial_brush_color, initial_brush_size, main_window_ref): # Ana pencere referansını al
        super().__init__()
        self.setWindowTitle("Portable Visual and Drawing Area")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        self.main_window_ref = main_window_ref # Referansı sakla

        self.background_pixmap = background_pixmap # The screenshot image
        # Create an empty overlay image to draw on
        # Use QImage.Format_ARGB32 for transparency support
        self.overlay_image = QImage(self.background_pixmap.size(), QImage.Format_ARGB32)
        self.overlay_image.fill(Qt.transparent) # Fill with transparent color initially

        # Drawing properties
        self.brush_color = initial_brush_color
        self.brush_size = initial_brush_size
        self.active_tool = "pen" # Default tool

        self.drawing = False # Flag to indicate if drawing is active
        self.moving_image = False # Flag to indicate if image is being moved
        self.space_pressed = False # Flag for spacebar (hand tool)

        self.last_point = QPoint() # Last point for continuous drawing (pen/eraser)
        self.temp_start_point = QPoint() # Start point for shape tools (line, rect, ellipse)
        self.temp_end_point = QPoint() # End point for shape tools

        self.image_pos = QPoint(0, 0) # Top-left position of the image on the canvas
        self.drag_offset = QPoint() # Offset for dragging the image

        # Set initial geometry to match the screenshot or full screen
        if self.background_pixmap.isNull():
            screen_rect = QApplication.primaryScreen().geometry()
            self.setGeometry(0, 0, min(screen_rect.width(), 1920), min(screen_rect.height(), 1080))
        else:
            self.setGeometry(0, 0, self.background_pixmap.width(), self.background_pixmap.height())

        # Initialize and show the tool window
        self.tool_window = ToolWindow(self)
        self.tool_window.show()
        # Position tool window to the top-right of the paint window
        self.tool_window.move(self.x() + self.width() - self.tool_window.width() - 20, self.y() + 20)

    def set_tool(self, tool):
        """Sets the active drawing tool."""
        self.active_tool = tool
        # Change cursor based on tool
        if tool == "move":
            self.setCursor(Qt.OpenHandCursor)
        elif tool == "pen" or tool == "eraser" or tool == "line" or tool == "rect" or tool == "ellipse":
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def set_brush_color(self, color):
        """Sets the current brush color."""
        self.brush_color = color

    def set_brush_size(self, size):
        """Sets the current brush size."""
        self.brush_size = size

    def mousePressEvent(self, event):
        """Handles mouse press events for drawing and moving the image."""
        if event.button() == Qt.LeftButton:
            if self.space_pressed or self.active_tool == "move":
                # Check if the click is within the image bounds for dragging
                if self.background_pixmap and QRect(self.image_pos, self.background_pixmap.size()).contains(event.pos()):
                    self.moving_image = True
                    self.drag_offset = event.pos() - self.image_pos
                    self.setCursor(Qt.ClosedHandCursor)
            else:
                self.drawing = True
                self.last_point = event.pos() # For pen/eraser
                self.temp_start_point = event.pos() # For shapes

    def mouseMoveEvent(self, event):
        """Handles mouse move events for drawing and moving the image."""
        if (self.space_pressed or self.active_tool == "move") and self.moving_image:
            self.image_pos = event.pos() - self.drag_offset
            self.update() # Repaint to show image in new position
        elif self.drawing and (event.buttons() & Qt.LeftButton):
            # Convert mouse position to coordinates relative to the image
            # This is crucial for drawing on the overlay as if it's directly on the image
            image_relative_pos = event.pos() - self.image_pos

            if self.active_tool in ["pen", "eraser"]:
                painter = QPainter(self.overlay_image)
                if self.active_tool == "eraser":
                    painter.setCompositionMode(QPainter.CompositionMode_Clear) # Clear pixels
                    pen = QPen(Qt.transparent, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                else:
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver) # Draw normally
                    pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(self.last_point - self.image_pos, image_relative_pos) # Draw relative to image
                painter.end()
                self.last_point = event.pos() # Update last point for next segment
                self.update() # Repaint for continuous drawing effect
            else:
                # For line, rect, ellipse, only update the end point for preview
                self.temp_end_point = image_relative_pos
                self.update() # Repaint to show shape preview

    def mouseReleaseEvent(self, event):
        """Finalizes drawing or image movement on mouse release."""
        if event.button() == Qt.LeftButton:
            if self.moving_image:
                self.moving_image = False
                self.setCursor(Qt.OpenHandCursor if self.space_pressed else Qt.ArrowCursor)
            elif self.drawing:
                self.drawing = False
                painter = QPainter(self.overlay_image)
                painter.setPen(QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

                # Convert final mouse position to image-relative coordinates
                final_point_relative = event.pos() - self.image_pos

                if self.active_tool == "line":
                    painter.drawLine(self.temp_start_point, final_point_relative)
                elif self.active_tool == "rect":
                    # Normalize rectangle to handle drawing in any direction
                    painter.drawRect(QRect(self.temp_start_point, final_point_relative).normalized())
                elif self.active_tool == "ellipse":
                    painter.drawEllipse(QRect(self.temp_start_point, final_point_relative).normalized())
                # Pen and eraser are already handled in mouseMoveEvent for continuous drawing

                painter.end()
                self.update() # Final repaint after drawing

    def keyPressEvent(self, event):
        """Handles keyboard shortcuts (Space for hand tool, Esc to close)."""
        if event.key() == Qt.Key_Space:
            self.space_pressed = True
            self.setCursor(Qt.OpenHandCursor) # Change cursor to hand
            self.set_tool("move") # Temporarily switch to move tool
        elif event.key() == Qt.Key_Escape:
            self.close_tool_window()
            self.close()
            # Reopen the main UI window if it was passed as a reference
            if self.main_window_ref:
                self.main_window_ref.show()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Resets cursor after Space key is released."""
        if event.key() == Qt.Key_Space:
            self.space_pressed = False
            if not self.moving_image: # Only reset if not actively dragging
                # Revert to previous tool's cursor if not moving
                self.set_tool(self.active_tool)
        else:
            super().keyReleaseEvent(event)

    def paintEvent(self, event):
        """
        Draws the background screenshot and the overlay with user drawings.
        Also draws previews for shape tools.
        """
        painter = QPainter(self)
        # 1) Draw the background screenshot, offset by image_pos
        if not self.background_pixmap.isNull():
            painter.drawPixmap(self.image_pos, self.background_pixmap)
        else:
            # Fallback if no screenshot was loaded
            painter.fillRect(self.rect(), QColor(245, 245, 245))

        # 2) Draw the overlay image (where drawings are stored), offset by image_pos
        painter.drawImage(self.image_pos, self.overlay_image)

        # 3) Draw preview for shape tools (line, rect, ellipse) while drawing
        if self.drawing and self.active_tool in ["line", "rect", "ellipse"]:
            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            pen.setStyle(Qt.DashLine) # Dashed line for preview
            painter.setPen(pen)

            # Convert image-relative start/end points to screen coordinates for preview
            p1_screen = self.temp_start_point + self.image_pos
            p2_screen = self.temp_end_point + self.image_pos
            preview_rect = QRect(p1_screen, p2_screen).normalized()

            if self.active_tool == "line":
                painter.drawLine(p1_screen, p2_screen)
            elif self.active_tool == "rect":
                painter.drawRect(preview_rect)
            elif self.active_tool == "ellipse":
                painter.drawEllipse(preview_rect)

        painter.end()

    def close_tool_window(self):
        """Safely closes the associated tool window."""
        if hasattr(self, 'tool_window') and self.tool_window:
            self.tool_window.close()
            self.tool_window = None

    def closeEvent(self, event):
        """
        Handles the window close event. Ensures tool window is closed
        and reopens the main UI window.
        """
        self.close_tool_window()
        # Ensure the main window is reopened after this window closes
        if self.main_window_ref:
            self.main_window_ref.show()
        super().closeEvent(event) # Call parent's closeEvent


class ToolWindow(QWidget):
    """
    A floating tool window for selecting drawing tools, colors, and brush size.
    """
    def __init__(self, parent_paint_window):
        super().__init__(parent_paint_window) # Parent is PaintCanvasWindow
        self.paint_window = parent_paint_window
        self.setWindowTitle("Drawing Tools")
        self.setFixedSize(120, 440) # Adjust size as needed for UI elements
        # Keep window on top and make it a tool window (doesn't appear in taskbar)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        # Construct path to .ui file
        script_dir = os.path.dirname(__file__)
        ui_path = os.path.join(script_dir, 'data', 'pen_tool.ui')

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Error", f"UI file for tools not found: {ui_path}")
            sys.exit(1)

        uic.loadUi(ui_path, self) # Load the UI from the .ui file

        # Connect tool buttons
        # Assuming 'pen_btn', 'eraser_btn', 'line_btn', 'rect_btn', 'ellipse_btn', 'highlight_btn', 'move_btn' from .ui
        self.pen_btn.clicked.connect(lambda: self.set_tool("pen"))
        self.eraser_btn.clicked.connect(lambda: self.set_tool("eraser"))
        self.line_btn.clicked.connect(lambda: self.set_tool("line"))
        self.rect_btn.clicked.connect(lambda: self.set_tool("rect"))
        self.ellipse_btn.clicked.connect(lambda: self.set_tool("ellipse"))
        self.highlight_btn.clicked.connect(self.select_highlighter)
        # Check if move_btn exists before connecting to prevent AttributeError
        if hasattr(self, 'move_btn'):
            self.move_btn.clicked.connect(lambda: self.set_tool("move")) # New move tool button
        else:
            print("Warning: 'move_btn' not found in pen_tool.ui. Move tool functionality will be unavailable.")


        # Connect color buttons
        # Assuming 'color_red', 'color_blue', 'color_black', 'color_green' from .ui
        self.color_red.clicked.connect(lambda: self.set_color_and_update_main(Qt.red))
        self.color_blue.clicked.connect(lambda: self.set_color_and_update_main(Qt.blue))
        self.color_black.clicked.connect(lambda: self.set_color_and_update_main(Qt.black))
        self.color_green.clicked.connect(lambda: self.set_color_and_update_main(Qt.green))

        # Connect brush size spin box
        self.brushSizeSpinBox.setMinimum(1)
        self.brushSizeSpinBox.setMaximum(50)
        self.brushSizeSpinBox.setValue(self.paint_window.brush_size) # Set initial value
        self.brushSizeSpinBox.valueChanged.connect(self.change_brush_size)

        self.exit_btn.clicked.connect(self.close)

    def set_tool(self, tool):
        """Delegates tool selection to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_tool(tool)

    def set_color_and_update_main(self, color):
        """Delegates color setting to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_brush_color(QColor(color))
            # Also update the color indicator in the main Ui if it's still active
            # (Though in this refactor, main Ui closes before PaintCanvasWindow opens)

    def change_brush_size(self, value):
        """Delegates brush size change to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_brush_size(value)

    def select_highlighter(self):
        """Configures the brush for a semi-transparent highlighter effect."""
        if self.paint_window:
            color = QColor(self.paint_window.brush_color) # Use current brush color
            color.setAlpha(128) # 50% transparency
            self.paint_window.set_brush_color(color)
            self.paint_window.set_tool("pen") # Highlighter is essentially a transparent pen

    def closeEvent(self, event):
        """
        Handles the tool window close event. Ensures the parent paint window
        is also closed to prevent orphaned drawing sessions.
        """
        if self.paint_window:
            try:
                self.paint_window.close() # Close the associated paint window
            except Exception as e:
                print(f"Error closing parent paint window from tool window: {e}")
                traceback.print_exc()
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
        print(f"Critical application error: {e}")
        traceback.print_exc()
        sys.exit(1)

import sys
import os
import traceback
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QComboBox, QMessageBox, QFrame, QPushButton
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QTimer # QTimer not used but kept from original imports
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


class Ui(QMainWindow):
    """
    Main application window that provides options to start painting,
    take full-screen screenshots, or select a region for drawing.
    """

    def __init__(self):
        super().__init__()

        # Construct path to .ui file relative to script's location
        script_dir = os.path.dirname(__file__)
        ui_path = os.path.join(script_dir, 'data', 'undockapp.ui') # Assuming 'data' directory for .ui file

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        # Load the UI from the .ui file
        uic.loadUi(ui_path, self)

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

        # Connect buttons to their respective methods using object names from .ui file
        self.findChild(QPushButton, "quit").clicked.connect(self.close)
        self.findChild(QPushButton, "pen").clicked.connect(self.start_full_screen_paint)
        self.findChild(QPushButton, "ss").clicked.connect(self.open_region_selector)
        # Assuming 'eraser' button in main UI might be intended to close, or for future eraser feature in main UI
        self.findChild(QPushButton, "eraser").clicked.connect(self.close)

        # Connect color buttons
        self.findChild(QPushButton, "red").clicked.connect(lambda: self.set_color(QColor(Qt.red)))
        self.findChild(QPushButton, "blue").clicked.connect(lambda: self.set_color(QColor(Qt.blue)))
        self.findChild(QPushButton, "green").clicked.connect(lambda: self.set_color(QColor(Qt.green)))
        self.findChild(QPushButton, "black").clicked.connect(lambda: self.set_color(QColor(Qt.black)))

        # Default drawing properties
        self.active_color = QColor(Qt.red)
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

    def open_region_selector(self):
        """Hides the main window and opens the region selection tool."""
        self.hide()  # Hide the main window, do not close it
        self.selector = RegionSelector(self.active_color, self.active_size, self)  # Pass main window reference
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
                0,  # Alpha value (not used with LWA_COLORKEY)
                win32con.LWA_COLORKEY  # Use color key transparency
            )
        except Exception as e:
            print(f"Transparency could not be set: {e}")
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
                    self  # Pass main window reference
                )
                self.paint_window.showFullScreen()
            except Exception as e:
                print(f"Failed to create full-screen paint window: {e}")
                traceback.print_exc()
                self.show()  # Show main window if paint window fails
        else:
            self.show()  # Show main window if screenshot fails

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
            print(f"Failed to capture screenshot: {e}")
            traceback.print_exc()
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
        self.setCursor(Qt.CrossCursor)  # Cross cursor for selection

        # Set geometry to cover the primary screen
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

    def mousePressEvent(self, event):
        """Records the starting point of the selection."""
        if event.button() == Qt.LeftButton:
            self.begin = event.pos()
            self.end = event.pos()
            self.update()  # Trigger repaint to show initial selection rectangle

    def mouseMoveEvent(self, event):
        """Updates the end point of the selection as the mouse moves."""
        if event.buttons() & Qt.LeftButton:  # Only if left button is held down
            self.end = event.pos()
            self.update()  # Trigger repaint to update the rectangle

    def mouseReleaseEvent(self, event):
        """
        Finalizes the selection, closes the selector, and opens the paint window
        with the cropped screenshot.
        """
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

    def paintEvent(self, event):
        """Draws the transparent gray overlay and the red selection rectangle."""
        painter = QPainter(self)
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
            paint_window = PaintCanvasWindow(pixmap, self.brush_color, self.brush_size,
                                             self.main_window_ref)  # Pass main window reference
            paint_window.show()
        except Exception as e:
            print(f"Error capturing region or opening paint window: {e}")
            traceback.print_exc()
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
        self.setGeometry(screen_rect) # This makes the canvas cover the whole screen.

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
        self.original_pixmap_size = QSize() # Stores initial size when resizing starts
        self.current_preview_rect = QRect() # Stores the rectangle for resize preview

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
        self.move_image_btn.clicked.connect(lambda: self.set_tool("move"))
        self.move_image_btn.setFixedSize(120, 30)

        # Determine button visibility: If it's a full-screen screenshot, the move button is less useful.
        # It's primarily for cropped images within a larger drawing area.
        if self.background_pixmap.isNull() or (self.background_pixmap.size() == screen_rect.size()):
            self.move_image_btn.hide()
        else:
            self.move_image_btn.show()
            # Position the button relative to the current image_pos
            self.move_image_btn.move(self.image_pos.x() + 10, self.image_pos.y() + 10) # 10px padding from image corner

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
        elif tool in ["pen", "eraser", "line", "rect", "ellipse"]:
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
        """Handles mouse press events for drawing, moving, and resizing the image."""
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
            self.setCursor(Qt.SizeFDiagCursor) # Diagonal resize cursor
            return

        # Check for image move interaction
        # Only consider image handle area if not already resizing
        image_handle_area = QRect(self.image_pos, QSize(self.background_pixmap.width(), 30)) # 30px handle at top
        if image_handle_area.contains(event.pos()) and not self.background_pixmap.isNull():
            self.moving_image = True
            self.drag_offset = event.pos() - self.image_pos
            self.setCursor(Qt.ClosedHandCursor)
            return # Stop here if image is being moved

        # If not resizing or moving, proceed with drawing logic
        if event.button() == Qt.LeftButton:
            if self.space_pressed or self.active_tool == "move":
                # Check if the click is within the current image bounds for dragging
                # Important: check against the current image_pos, not always (0,0)
                image_rect = QRect(self.image_pos, self.background_pixmap.size())
                if image_rect.contains(event.pos()):
                    self.moving_image = True
                    self.drag_offset = event.pos() - self.image_pos
                    self.setCursor(Qt.ClosedHandCursor)
            else:
                self.drawing = True
                self.last_point = event.pos()  # These are now always window-relative
                self.temp_start_point = event.pos()  # These are now always window-relative

    def mouseMoveEvent(self, event):
        """Handles mouse move events for drawing, moving, and resizing the image."""
        if self.resizing and self.resize_anchor == 'bottom_right':
            # Calculate new size based on mouse position relative to image_pos
            new_width = event.pos().x() - self.image_pos.x()
            new_height = event.pos().y() - self.image_pos.y()

            # Ensure minimum size
            new_width = max(10, new_width)
            new_height = max(10, new_height)

            # Maintain aspect ratio
            if self.original_pixmap_size.width() > 0 and self.original_pixmap_size.height() > 0:
                original_aspect_ratio = float(self.original_pixmap_size.width()) / self.original_pixmap_size.height()

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
            self.update() # Request repaint to draw the preview rectangle
        elif (self.space_pressed or self.active_tool == "move") and self.moving_image:
            self.image_pos = event.pos() - self.drag_offset
            # Reposition the move button with the image
            self.move_image_btn.move(self.image_pos.x() + 10, self.image_pos.y() + 10)
            self.update()
        elif self.drawing and (event.buttons() & Qt.LeftButton):
            painter = QPainter(self.overlay_image)  # Paint directly on overlay_image
            if self.active_tool == "eraser":
                painter.setCompositionMode(QPainter.CompositionMode_Clear) # Transparent for erasing
                pen = QPen(Qt.transparent, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            else:
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver) # Normal blending
                pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)

            if self.active_tool in ["pen", "eraser"]:
                painter.drawLine(self.last_point, event.pos())  # Drawing with window-relative coords
                self.last_point = event.pos()
            self.temp_end_point = event.pos()  # Always window-relative
            painter.end() # End painter for overlay_image to apply changes

            self.update() # Request repaint for the whole window

    def mouseReleaseEvent(self, event):
        """Finalizes drawing, image movement, or resizing on mouse release."""

        if event.button() == Qt.LeftButton:
            if self.resizing:
                if not self.current_preview_rect.isNull():
                    # Apply the actual scaling only once, on mouse release
                    self.background_pixmap = self.background_pixmap.scaled(
                        self.current_preview_rect.size(),
                        Qt.KeepAspectRatio, # Keep aspect ratio for final scale
                        Qt.SmoothTransformation
                    )
                    # Reposition the move button based on the new image size/position
                    self.move_image_btn.move(self.image_pos.x() + 10, self.image_pos.y() + 10)
                self.resizing = False
                self.resize_anchor = None
                self.current_preview_rect = QRect() # Clear preview rectangle
                self.setCursor(Qt.ArrowCursor) # Reset cursor
                self.update() # Request repaint after final scaling
            elif self.moving_image:
                self.moving_image = False
                self.setCursor(Qt.OpenHandCursor if self.space_pressed else Qt.ArrowCursor)
            elif self.drawing:
                self.drawing = False
                painter = QPainter(self.overlay_image)  # Paint directly on overlay_image
                painter.setPen(QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

                if self.active_tool == "line":
                    painter.drawLine(self.temp_start_point, event.pos())  # Drawing with window-relative coords
                elif self.active_tool == "rect":
                    painter.drawRect(
                        QRect(self.temp_start_point, event.pos()).normalized())  # Drawing with window-relative coords
                elif self.active_tool == "ellipse":
                    painter.drawEllipse(
                        QRect(self.temp_start_point, event.pos()).normalized())  # Drawing with window-relative coords
                painter.end() # End painter for overlay_image to apply changes
                self.update() # Request repaint for the whole window

    def keyPressEvent(self, event):
        """Handles keyboard shortcuts (Space for hand tool, Esc to close)."""
        if event.key() == Qt.Key_Space:
            self.space_pressed = True
            self.setCursor(Qt.OpenHandCursor)  # Change cursor to hand
            self.set_tool("move")  # Temporarily switch to move tool
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
            if not self.moving_image:  # Only reset if not actively dragging
                # Revert to previous tool's cursor if not moving
                self.set_tool(self.active_tool)
        else:
            super().keyReleaseEvent(event)

    def paintEvent(self, event):
        """
        Draws the background screenshot and the overlay with user drawings.
        Also draws previews for shape tools and resize indicators.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # For smoother lines/shapes

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
            pen.setStyle(Qt.DashLine) # Use dashed line for preview
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
                preview_pen = QPen(QColor(255, 165, 0, 200), 2, Qt.DashLine) # Orange dashed line for preview
                painter.setPen(preview_pen)
                painter.drawRect(self.current_preview_rect)


        painter.end() # End painter for the window

    def resizeEvent(self, event):
        """
        Resizes the overlay_image when the window resizes to maintain drawing consistency.
        """
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
        super().closeEvent(event)  # Call parent's closeEvent


class ToolWindow(QWidget):
    """
    A floating tool window for selecting drawing tools, colors, and brush size.
    """

    def __init__(self, parent_paint_window):
        super().__init__(parent_paint_window)  # Parent is PaintCanvasWindow
        self.paint_window = parent_paint_window
        self.setWindowTitle("Çizim Araçları")
        self.setFixedSize(120, 440)  # Set fixed size for UI elements
        # Keep window on top and make it a tool window (not visible in taskbar)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        # Construct path to .ui file
        script_dir = os.path.dirname(__file__)
        ui_path = os.path.join(script_dir, 'data', 'pen_tool.ui') # Assuming 'data' directory for .ui file

        # Check if the UI file exists
        if not os.path.exists(ui_path):
            QMessageBox.critical(self, "Hata", f"Araçlar için UI dosyası bulunamadı: {ui_path}")
            sys.exit(1)

        uic.loadUi(ui_path, self)  # Load the UI from the .ui file

        # Connect tool buttons using their object names from .ui
        self.findChild(QPushButton, "pen_btn").clicked.connect(lambda: self.set_tool("pen"))
        self.findChild(QPushButton, "eraser_btn").clicked.connect(lambda: self.set_tool("eraser"))
        self.findChild(QPushButton, "line_btn").clicked.connect(lambda: self.set_tool("line"))
        self.findChild(QPushButton, "rect_btn").clicked.connect(lambda: self.set_tool("rect"))
        self.findChild(QPushButton, "ellipse_btn").clicked.connect(lambda: self.set_tool("ellipse"))
        self.findChild(QPushButton, "highlight_btn").clicked.connect(self.select_highlighter)
        # Check if move_btn exists before connecting to prevent AttributeError
        if hasattr(self, 'move_btn'):
            self.findChild(QPushButton, "move_btn").clicked.connect(lambda: self.set_tool("move"))
        else:
            print("Warning: 'move_btn' not found in pen_tool.ui. Move tool functionality will be unavailable.")

        # Connect color buttons using their object names from .ui
        self.findChild(QPushButton, "color_red").clicked.connect(lambda: self.set_color_and_update_main(Qt.red))
        self.findChild(QPushButton, "color_blue").clicked.connect(lambda: self.set_color_and_update_main(Qt.blue))
        self.findChild(QPushButton, "color_black").clicked.connect(lambda: self.set_color_and_update_main(Qt.black))
        self.findChild(QPushButton, "color_green").clicked.connect(lambda: self.set_color_and_update_main(Qt.green))

        # Connect brush size spin box
        self.brushSizeSpinBox = self.findChild(QtWidgets.QSpinBox, "brushSizeSpinBox")
        if self.brushSizeSpinBox:
            self.brushSizeSpinBox.setMinimum(1)
            self.brushSizeSpinBox.setMaximum(50)
            self.brushSizeSpinBox.setValue(self.paint_window.brush_size)  # Set initial value
            self.brushSizeSpinBox.valueChanged.connect(self.change_brush_size)
        else:
            print("Warning: 'brushSizeSpinBox' not found in pen_tool.ui.")


        self.findChild(QPushButton, "exit_btn").clicked.connect(self.close)

    def set_tool(self, tool):
        """Delegates tool selection to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_tool(tool)

    def set_color_and_update_main(self, color):
        """Delegates color setting to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_brush_color(QColor(color))

    def change_brush_size(self, value):
        """Delegates brush size change to the parent paint window."""
        if self.paint_window:
            self.paint_window.set_brush_size(value)

    def select_highlighter(self):
        """Configures the brush for a semi-transparent highlighter effect."""
        if self.paint_window:
            color = QColor(self.paint_window.brush_color)  # Use current brush color
            color.setAlpha(128)  # 50% transparency
            self.paint_window.set_brush_color(color)
            self.paint_window.set_tool("pen")  # Highlighter is essentially a transparent pen

    def closeEvent(self, event):
        """
        Handles the tool window close event. Ensures the parent paint window
        is also closed to prevent orphaned drawing sessions.
        """
        if self.paint_window:
            try:
                self.paint_window.close()  # Close the associated drawing window
            except Exception as e:
                print(f"Error closing main drawing window from tool window: {e}")
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
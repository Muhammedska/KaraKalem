import sys
import datetime
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QToolBar, QAction, QColorDialog,
                             QInputDialog, QMessageBox, QShortcut, QButtonGroup, QToolButton) # Added QToolButton
from PyQt5.QtGui import (QPainter, QPainterPath, QPen, QColor, QFont,
                         QKeySequence, QPixmap, QPolygonF)
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QPointF


class Canvas(QWidget):
    """
    The main drawing canvas where annotations are made.
    It captures the screen, allows drawing, shape creation, text input,
    and manages the drawing history for undo functionality.
    """
    def __init__(self):
        super().__init__()
        # Set window flags for a frameless, transparent, and always-on-top window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Get the primary screen geometry and set the canvas to cover it
        screen_rect = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_rect)

        # Drawing properties
        self.drawing = False  # Flag to indicate if a drawing action is currently active
        self.last_point = QPoint()  # Stores the last point for continuous drawing
        self.pen_color = QColor(255, 0, 0)  # Default pen color (Red)
        self.pen_width = 4  # Default pen width
        self.mode = "draw"  # Current drawing mode: "draw", "rectangle", "circle", "arrow", "text"
        self.current_action = None # Holds the dictionary of the action currently being drawn/modified

        # Unified history for undo/redo. Each item is a dictionary representing an action.
        self.history = []
        # self.undo_stack could be used for a 'redo' feature, but not implemented in this version.
        self.undo_stack = []

        self.background_image = None  # Stores the captured screenshot as the canvas background

        # Keyboard shortcuts using QShortcut for global application-wide actions
        self.shortcut_undo = QShortcut(QKeySequence.Undo, self)
        self.shortcut_undo.activated.connect(self.undo)

        self.shortcut_clear = QShortcut(QKeySequence('Ctrl+C'), self)
        self.shortcut_clear.activated.connect(self.clear_canvas)

        self.shortcut_quit = QShortcut(QKeySequence('Esc'), self)
        self.shortcut_quit.activated.connect(self.close) # Closes the canvas window directly

        self.shortcut_save = QShortcut(QKeySequence.Save, self)
        self.shortcut_save.activated.connect(self.capture_screen)

    def capture_background(self):
        """
        Captures the entire primary screen and sets it as the background image
        for the canvas. This allows drawing directly onto a screenshot.
        """
        screen = QApplication.primaryScreen()
        screenshot = screen.grabWindow(0) # Grab the entire desktop
        self.background_image = screenshot
        self.update() # Request a repaint to show the background image

    def mousePressEvent(self, event):
        """
        Handles mouse press events. Initiates drawing, shape creation, or text input.
        """
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = event.pos()

            if self.mode == "draw":
                # For freehand drawing, create a new path and add it to history
                path = QPainterPath()
                path.moveTo(self.last_point)
                self.current_action = {
                    "type": "path",
                    "data": path,
                    "color": self.pen_color,
                    "width": self.pen_width
                }
                self.history.append(self.current_action)
            elif self.mode == "text":
                # For text input, open an input dialog
                text, ok = QInputDialog.getText(self, "Add Text", "Enter your text:")
                if ok and text:
                    text_action = {
                        "type": "text",
                        "text": text,
                        "position": event.pos(),
                        "color": self.pen_color,
                        "font": QFont("Arial", 16) # Default font, could be made configurable
                    }
                    self.history.append(text_action)
                    self.update() # Request repaint to show the new text
                self.drawing = False # Text input is a discrete action, not continuous drawing
            else:
                # For shapes (rectangle, circle, arrow), initialize the shape action
                self.current_action = {
                    "type": "shape",
                    "shape_type": self.mode,
                    "start": event.pos(),
                    "end": event.pos(), # End is initially the same as start
                    "color": self.pen_color,
                    "width": self.pen_width
                }
                self.history.append(self.current_action) # Add shape to history immediately

    def mouseMoveEvent(self, event):
        """
        Handles mouse move events. Updates the current drawing action (path or shape).
        """
        if event.buttons() == Qt.LeftButton and self.drawing and self.current_action:
            if self.mode == "draw":
                # For freehand drawing, extend the current path
                # The path object in self.current_action["data"] is modified directly
                self.current_action["data"].lineTo(event.pos())
                self.last_point = event.pos()
                self.update() # Request repaint to show the updated path
            elif self.mode in ["rectangle", "circle", "arrow"]:
                # For shapes, update the end point to stretch the shape
                self.current_action["end"] = event.pos()
                self.update() # Request repaint to show the updated shape

    def mouseReleaseEvent(self, event):
        """
        Handles mouse release events. Finalizes the current drawing action.
        """
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            self.current_action = None # Reset current action after drawing is complete

    def paintEvent(self, event):
        """
        Paints the canvas content, including the background image and all drawing actions
        from the history.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing) # Enable anti-aliasing for smoother lines

        # Draw the captured background image first
        if self.background_image:
            painter.drawPixmap(0, 0, self.background_image)

        # Iterate through the history and draw each action
        for action in self.history:
            if action["type"] == "path":
                # Draw freehand paths
                pen = QPen(action["color"], action["width"])
                painter.setPen(pen)
                painter.drawPath(action["data"])
            elif action["type"] == "shape":
                # Draw shapes (rectangle, circle, arrow)
                self.draw_shape(painter, action)
            elif action["type"] == "text":
                # Draw text elements
                painter.setPen(action["color"])
                painter.setFont(action["font"])
                painter.drawText(action["position"], action["text"])

    def draw_shape(self, painter, shape_action):
        """
        Helper function to draw a specific shape based on its action dictionary.
        """
        pen = QPen(shape_action["color"], shape_action["width"])
        painter.setPen(pen)
        start = shape_action["start"]
        end = shape_action["end"]
        # Create a normalized QRect to handle drawing from any corner (e.g., top-left to bottom-right or vice-versa)
        rect = QRect(start, end).normalized()

        if shape_action["shape_type"] == "rectangle":
            painter.drawRect(rect)
        elif shape_action["shape_type"] == "circle":
            painter.drawEllipse(rect)
        elif shape_action["shape_type"] == "arrow":
            painter.drawLine(start, end)

            # Calculate and draw the arrow head
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            arrow_size = 15 # Size of the arrow head wings

            # Points for the arrow head
            p1 = end - QPointF(
                arrow_size * math.cos(angle - math.pi / 6), # Angle - 30 degrees
                arrow_size * math.sin(angle - math.pi / 6)
            )
            p2 = end - QPointF(
                arrow_size * math.cos(angle + math.pi / 6), # Angle + 30 degrees
                arrow_size * math.sin(angle + math.pi / 6)
            )

            arrow_head = QPolygonF()
            arrow_head.append(end)
            arrow_head.append(p1)
            arrow_head.append(p2)

            # Fill the arrow head for a solid appearance
            painter.setBrush(QColor(shape_action["color"]))
            painter.drawPolygon(arrow_head)
            painter.setBrush(Qt.NoBrush) # Reset brush to default (no fill)

    def undo(self):
        """
        Undoes the last drawing action by removing it from the history.
        """
        if self.history:
            # Pop the last action from history. Could be pushed to undo_stack for redo feature.
            self.undo_stack.append(self.history.pop())
            self.update() # Request a repaint to reflect the change

    def clear_canvas(self):
        """
        Clears all drawing actions from the canvas.
        """
        self.history = []
        self.undo_stack = [] # Also clear redo history
        self.update() # Request a repaint to show an empty canvas

    def capture_screen(self):
        """
        Saves the current annotated screen (background image + all drawings) to a file.
        """
        if not self.background_image:
            QMessageBox.warning(self, "Error", "Background image not captured yet!")
            return

        # Create a new QPixmap with the size of the background image
        combined_screenshot = QPixmap(self.background_image.size())
        combined_screenshot.fill(Qt.transparent) # Start with a transparent background

        painter = QPainter(combined_screenshot)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the original background image onto the new pixmap
        painter.drawPixmap(0, 0, self.background_image)

        # Draw all actions from history onto this combined pixmap
        for action in self.history:
            if action["type"] == "path":
                pen = QPen(action["color"], action["width"])
                painter.setPen(pen)
                painter.drawPath(action["data"])
            elif action["type"] == "shape":
                self.draw_shape(painter, action)
            elif action["type"] == "text":
                painter.setPen(action["color"])
                painter.setFont(action["font"])
                painter.drawText(action["position"], action["text"])

        painter.end() # End painting on the combined pixmap

        # Generate a unique filename with a timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screen_note_{timestamp}.png"

        # Save the combined screenshot to a PNG file
        if combined_screenshot.save(filename, "PNG"):
            QMessageBox.information(self, "Saved", f"Screenshot saved as '{filename}'.")
        else:
            QMessageBox.critical(self, "Error", "Failed to save screenshot.")


class MainWindow(QMainWindow):
    """
    The main application window, which hosts the Canvas and the toolbar.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Epic Pen Clone")
        # Set window flags to be frameless and always on top, similar to the Canvas
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # Make main window background translucent

        # Create the drawing canvas and set it as the central widget
        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)

        # Create the toolbar
        self.toolbar = QToolBar("Tools")
        self.toolbar.setIconSize(QSize(32, 32))
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Apply custom stylesheet to the toolbar and its buttons for a dark, rounded look
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: rgba(50, 50, 50, 200); /* Dark translucent background */
                border: 1px solid #333;
                border-radius: 5px;
                padding: 5px;
            }
            QToolButton {
                background-color: rgba(70, 70, 70, 200); /* Slightly lighter button background */
                border: 1px solid #555;
                border-radius: 3px;
                padding: 5px;
                color: white; /* Ensure emoji icons are visible on dark background */
            }
            QToolButton:hover {
                background-color: rgba(90, 90, 90, 200); /* Hover effect */
            }
            QToolButton:pressed, QToolButton:checked { /* Pressed and checked (active) state styling */
                background-color: rgba(110, 110, 110, 200);
            }
        """)

        # Create all actions and their corresponding QToolButtons for the toolbar
        self.create_actions()
        # Add the QToolButtons to the toolbar and QButtonGroup
        self.add_toolbar_actions()

        # Create a QButtonGroup to make mode selection actions mutually exclusive
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True) # Only one button can be checked at a time

        # Add the QToolButton instances to the button group
        self.mode_button_group.addButton(self.draw_button)
        self.mode_button_group.addButton(self.rect_button)
        self.mode_button_group.addButton(self.circle_button)
        self.mode_button_group.addButton(self.arrow_button)
        self.mode_button_group.addButton(self.text_button)

        # Set the default checked state for the draw button
        self.draw_button.setChecked(True)

        # Capture the initial screen background after the window is set up
        # This ensures the canvas has the desktop content behind it when it appears.
        self.canvas.capture_background()

    def create_actions(self):
        """
        Initializes and configures all QAction objects and their associated QToolButtons
        for the toolbar.
        """
        # Drawing modes
        self.draw_action = QAction("✏️", self)
        self.draw_action.setToolTip("Free Draw (D)")
        self.draw_action.triggered.connect(lambda: self.set_mode("draw"))
        self.draw_action.setCheckable(True)
        self.draw_button = QToolButton(self)
        self.draw_button.setDefaultAction(self.draw_action)

        self.rect_action = QAction("⬜", self)
        self.rect_action.setToolTip("Rectangle (R)")
        self.rect_action.triggered.connect(lambda: self.set_mode("rectangle"))
        self.rect_action.setCheckable(True)
        self.rect_button = QToolButton(self)
        self.rect_button.setDefaultAction(self.rect_action)

        self.circle_action = QAction("⭕", self)
        self.circle_action.setToolTip("Circle (C)")
        self.circle_action.triggered.connect(lambda: self.set_mode("circle"))
        self.circle_action.setCheckable(True)
        self.circle_button = QToolButton(self)
        self.circle_button.setDefaultAction(self.circle_action)

        self.arrow_action = QAction("➡️", self)
        self.arrow_action.setToolTip("Arrow (A)")
        self.arrow_action.triggered.connect(lambda: self.set_mode("arrow"))
        self.arrow_action.setCheckable(True)
        self.arrow_button = QToolButton(self)
        self.arrow_button.setDefaultAction(self.arrow_action)

        self.text_action = QAction("T", self)
        self.text_action.setToolTip("Add Text (T)")
        self.text_action.triggered.connect(lambda: self.set_mode("text"))
        self.text_action.setCheckable(True)
        self.text_button = QToolButton(self)
        self.text_button.setDefaultAction(self.text_action)


        # Color picker
        self.color_action = QAction("🎨", self)
        self.color_action.setToolTip("Choose Color")
        self.color_action.triggered.connect(self.choose_color)

        # Pen width settings
        self.thin_action = QAction("─", self)
        self.thin_action.setToolTip("Thin Pen (1)")
        self.thin_action.triggered.connect(lambda: self.set_width(2))

        self.medium_action = QAction("──", self)
        self.medium_action.setToolTip("Medium Pen (2)")
        self.medium_action.triggered.connect(lambda: self.set_width(4))

        self.thick_action = QAction("━━", self)
        self.thick_action.setToolTip("Thick Pen (3)")
        self.thick_action.triggered.connect(lambda: self.set_width(8))

        # Operations
        self.undo_action = QAction("↩️", self)
        self.undo_action.setToolTip("Undo (Ctrl+Z)")
        self.undo_action.triggered.connect(self.canvas.undo)

        self.clear_action = QAction("❌", self)
        self.clear_action.setToolTip("Clear All (Ctrl+C)")
        self.clear_action.triggered.connect(self.canvas.clear_canvas)

        self.save_action = QAction("💾", self)
        self.save_action.setToolTip("Save Screenshot (Ctrl+S)")
        self.save_action.triggered.connect(self.canvas.capture_screen)

        self.exit_action = QAction("🚪", self)
        self.exit_action.setToolTip("Exit (Esc)")
        self.exit_action.triggered.connect(self.close)

    def add_toolbar_actions(self):
        """
        Adds all created QToolButtons and other actions to the toolbar in a logical order.
        """
        self.toolbar.addWidget(self.draw_button)
        self.toolbar.addWidget(self.rect_button)
        self.toolbar.addWidget(self.circle_button)
        self.toolbar.addWidget(self.arrow_button)
        self.toolbar.addWidget(self.text_button)
        self.toolbar.addSeparator() # Visual separator
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
        """
        Sets the current drawing mode in the canvas.
        The QButtonGroup handles the checked state of the associated QToolButtons automatically.
        """
        self.canvas.mode = mode

    def choose_color(self):
        """
        Opens a color dialog to allow the user to select a new pen color.
        """
        color = QColorDialog.getColor(self.canvas.pen_color, self, "Select Pen Color")
        if color.isValid(): # Check if a color was selected
            self.canvas.pen_color = color

    def set_width(self, width):
        """
        Sets the pen width in the canvas.
        """
        self.canvas.pen_width = width

    def keyPressEvent(self, event):
        """
        Handles global key press events for mode and width selection.
        QShortcuts handle Undo, Clear, Save, Exit, etc.
        """
        if event.key() == Qt.Key_D:
            self.draw_button.setChecked(True) # Set the button's checked state
            self.set_mode("draw")
        elif event.key() == Qt.Key_R:
            self.rect_button.setChecked(True)
            self.set_mode("rectangle")
        elif event.key() == Qt.Key_C:
            self.circle_button.setChecked(True)
            self.set_mode("circle")
        elif event.key() == Qt.Key_A:
            self.arrow_button.setChecked(True)
            self.set_mode("arrow")
        elif event.key() == Qt.Key_T:
            self.text_button.setChecked(True)
            self.set_mode("text")
        elif event.key() == Qt.Key_1:
            self.set_width(2)
        elif event.key() == Qt.Key_2:
            self.set_width(4)
        elif event.key() == Qt.Key_3:
            self.set_width(8)
        else:
            # Pass unhandled events to the base class's keyPressEvent
            super().keyPressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Apply the 'Fusion' style for a modern look

    # Configure a dark theme palette for the entire application
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
    dark_palette.setColor(dark_palette.Highlight, QColor(142, 45, 197).lighter()) # Highlight color
    dark_palette.setColor(dark_palette.HighlightedText, Qt.black)
    app.setPalette(dark_palette) # Apply the dark palette to the application

    # Create and show the main window in full screen mode
    window = MainWindow()
    window.showFullScreen()

    # Start the Qt event loop
    sys.exit(app.exec_())

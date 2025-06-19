# importing libraries
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import win32api
import win32con
import win32gui



from PIL import Image
from PIL import ImageQt
import pyautogui

class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()

        uic.loadUi('./data/undockapp.ui',self)
        #self.setWindowFlags(Qt.FramelessWindowHint)
        #
        self.setAttribute(Qt.WA_TranslucentBackground)


        #self.setWindowFlags(Qt.WindowStaysOnTopHint)
        hwnd = self.pos()
        fuchsia = (255, 0, 128)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) | win32con.WS_EX_LAYERED)
        # Set window transparency color
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*fuchsia), 0, win32con.LWA_COLORKEY)

        #-- tools --
        self.quit.clicked.connect(self.qq)
        self.pen.clicked.connect(self.tss)
        self.ss.clicked.connect(self.srss)
        self.eraser.clicked.connect(self.qq)
        
        #--colors--
        self.red.clicked.connect(self.qq)
        self.blue.clicked.connect(self.qq)
        self.green.clicked.connect(self.qq)
        self.black.clicked.connect(self.qq)
    def tss(self):
        self.destroy()

        image = pyautogui.screenshot()
        imageguru = pyautogui.screenshot()
        imageguru.save('./curr_screen_cozeltisoftware.png')

        quandro = Windowx   ()
        quandro.show()
        """self.showFullScreen()
        print(image.size)
        print(self.imgur.size())
        self.imgur.setGeometry(0,0,image.size[0],image.size[1])
        self.img = image
        self.qim = ImageQt(self.img)
        self.pixmap = QPixmap.fromImage(self.qim)
        self.imgur.setPixmap(self.pixmap)
        print(image)"""
    def srss(self):
        self.destroy()
        appx = Windowx()
        appx.showFullScreen()
    def qq(self):
        self.destroy()
        sys.exit()


# window class
class Windowx(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # setting title
        self.setWindowTitle("Paint with PyQt5")
        imageguru = pyautogui.screenshot()
        # setting geometry to main window
        self.setGeometry(0, 0, imageguru.size[0],imageguru.size[1] )

        # creating image object
        self.image = QImage(self.size(), QImage.Format_RGB32)

        # making image color to white
        fuchsia = (255, 0, 128)
        #self.image.fill()
        replica = open('./curr_screen_cozeltisoftware.png', 'rb')
        #self.image.loadFromData(replica.read())
        # variables
        # drawing flag
        self.drawing = False
        # default brush size
        self.brushSize = 2
        # default color
        self.brushColor = Qt.black

        # QPoint object to tract the point
        self.lastPoint = QPoint()

        # creating menu bar
        mainMenu = self.menuBar()

        # creating file menu for save and clear action
        fileMenu = mainMenu.addMenu("File")

        # adding brush size to main menu
        b_size = mainMenu.addMenu("Brush Size")

        # adding brush color to ain menu
        b_color = mainMenu.addMenu("Brush Color")

        # creating save action
        saveAction = QAction("Save", self)
        # adding short cut for save action
        saveAction.setShortcut("Ctrl + S")
        # adding save to the file menu
        fileMenu.addAction(saveAction)
        # adding action to the save
        saveAction.triggered.connect(self.save)

        # creating clear action
        clearAction = QAction("Clear", self)
        # adding short cut to the clear action
        clearAction.setShortcut("Ctrl + C")
        # adding clear to the file menu
        fileMenu.addAction(clearAction)
        # adding action to the clear
        clearAction.triggered.connect(self.clear)

        # creating options for brush sizes
        # creating action for selecting pixel of 4px
        pix_4 = QAction("4px", self)
        # adding this action to the brush size
        b_size.addAction(pix_4)
        # adding method to this
        pix_4.triggered.connect(self.Pixel_4)

        # similarly repeating above steps for different sizes
        pix_7 = QAction("7px", self)
        b_size.addAction(pix_7)
        pix_7.triggered.connect(self.Pixel_7)

        pix_9 = QAction("9px", self)
        b_size.addAction(pix_9)
        pix_9.triggered.connect(self.Pixel_9)

        pix_12 = QAction("12px", self)
        b_size.addAction(pix_12)
        pix_12.triggered.connect(self.Pixel_12)

        # creating options for brush color
        # creating action for black color
        black = QAction("Black", self)
        # adding this action to the brush colors
        b_color.addAction(black)
        # adding methods to the black
        black.triggered.connect(self.blackColor)

        # similarly repeating above steps for different color
        white = QAction("White", self)
        b_color.addAction(white)
        white.triggered.connect(self.whiteColor)

        green = QAction("Green", self)
        b_color.addAction(green)
        green.triggered.connect(self.greenColor)

        yellow = QAction("Yellow", self)
        b_color.addAction(yellow)
        yellow.triggered.connect(self.yellowColor)

        red = QAction("Red", self)
        b_color.addAction(red)
        red.triggered.connect(self.redColor)

    # method for checking mouse cicks
    def mousePressEvent(self, event):

        # if left mouse button is pressed
        if event.button() == Qt.LeftButton:
            # make drawing flag true
            self.drawing = True
            # make last point to the point of cursor
            self.lastPoint = event.pos()

    # method for tracking mouse activity
    def mouseMoveEvent(self, event):

        # checking if left button is pressed and drawing flag is true
        if (event.buttons() & Qt.LeftButton) & self.drawing:
            # creating painter object
            painter = QPainter(self.image)

            # set the pen of the painter
            painter.setPen(QPen(self.brushColor, self.brushSize,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

            # draw line from the last point of cursor to the current point
            # this will draw only one step
            painter.drawLine(self.lastPoint, event.pos())

            # change the last point
            self.lastPoint = event.pos()
            # update
            self.update()

    # method for mouse left button release
    def mouseReleaseEvent(self, event):

        if event.button() == Qt.LeftButton:
            # make drawing flag false
            self.drawing = False

    # paint event
    def paintEvent(self, event):
        # create a canvas
        canvasPainter = QPainter(self)

        # draw rectangle on the canvas
        canvasPainter.drawImage(self.rect(), self.image, self.image.rect())

    # method for saving canvas
    def save(self):
        filePath, _ = QFileDialog.getSaveFileName(self, "Save Image", "",
                                                  "PNG(*.png);;JPEG(*.jpg *.jpeg);;All Files(*.*) ")

        if filePath == "":
            return
        self.image.save(filePath)

    # method for clearing every thing on canvas
    def clear(self):
        import time
        # make the whole canvas white
        #self.image.fill(Qt.white)
        self.showMinimized()
        if self.isMinimized():
            time.sleep(1.0)
            imageguru = pyautogui.screenshot()
            imageguru.save('./curr_screen_cozeltisoftware.png')
            self.showFullScreen()
            self.image.loadFromData(open('./curr_screen_cozeltisoftware.png','rb').read())
            # update
            #self.paintEngine().painter().eraseRect(0,0,imageguru.size[0],imageguru.size[1])
            self.update()

    # methods for changing pixel sizes
    def Pixel_4(self):
        self.brushSize = 4

    def Pixel_7(self):
        self.brushSize = 7

    def Pixel_9(self):
        self.brushSize = 9

    def Pixel_12(self):
        self.brushSize = 12

    # methods for changing brush color
    def blackColor(self):
        self.brushColor = Qt.black

    def whiteColor(self):
        self.brushColor = Qt.white

    def greenColor(self):
        self.brushColor = Qt.green

    def yellowColor(self):
        self.brushColor = Qt.yellow

    def redColor(self):
        self.brushColor = Qt.red

class MainWindow(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(
            QtWidgets.QStyle.alignedRect(
                Qt.LeftToRight, Qt.AlignCenter,
                QSize(220, 32),
                QtWidgets.qApp.desktop().availableGeometry()
        ))


    def mousePressEvent(self, event):
        QtWidgets.qApp.quit()


if __name__ == '__main__':
    # create pyqt5 app
    App = QApplication(sys.argv)

    # create the instance of our Window
    window = Ui()

    # showing the window
    window.show()

    # start the app
    sys.exit(App.exec())
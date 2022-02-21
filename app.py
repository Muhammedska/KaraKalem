# importing libraries
import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


from PIL import Image
from PIL.ImageQt import ImageQt
import pyautogui

class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()

        uic.loadUi('./data/app.ui',self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        #-- tools --
        self.quit.clicked.connect(self.qq)
        self.pen.clicked.connect(self.qq)
        self.ss.clicked.connect(self.qq)
        self.eraser.clicked.connect(self.qq)
        
        #--colors--
        self.red.clicked.connect(self.qq)
        self.blue.clicked.connect(self.qq)
        self.green.clicked.connect(self.qq)
        self.black.clicked.connect(self.qq)
    def tss(self):
        image = pyautogui.screenshot()
    def qq(self):
        self.destroy()
        sys.exit()
if __name__ == '__main__':
    # create pyqt5 app
    App = QApplication(sys.argv)

    # create the instance of our Window
    window = Ui()

    # showing the window
    window.show()

    # start the app
    sys.exit(App.exec())
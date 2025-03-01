"""
Animated label component for Sabrina's Presence System
Provides an enhanced QLabel with animation and opacity support
"""
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtProperty
from PyQt5.QtGui import QPainter


class AnimatedLabel(QLabel):
    """Enhanced QLabel with animation properties and opacity control"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 1.0
        self.setStyleSheet("background: transparent;")

        # Add resource tracking
        self.movie_resource_id = None

    def setOpacity(self, opacity):
        """Set the opacity level of the label"""
        self._opacity = opacity
        self.update()

    def getOpacity(self):
        """Get the current opacity level"""
        return self._opacity

    # Define property for QPropertyAnimation
    opacity = pyqtProperty(float, getOpacity, setOpacity)

    def paintEvent(self, event):
        """Override paintEvent for custom opacity rendering"""
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        super().paintEvent(event)

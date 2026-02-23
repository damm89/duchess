from PyQt6.QtCore import Qt, pyqtProperty, pyqtSignal, QPropertyAnimation, QAbstractAnimation
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QScrollArea, QFrame, QSizePolicy, QToolButton
)

class AccordionSection(QWidget):
    """A single accordion section with a toggle button and a content area."""
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Toggle Button
        self.toggle_button = QToolButton(self)
        self.toggle_button.setText(f"▶ {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                font-weight: bold;
                text-align: left;
                padding: 4px;
            }
        """)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle_button.clicked.connect(self._on_toggled)

        self.layout.addWidget(self.toggle_button)

        # Content Area
        self.content_area = QScrollArea(self)
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # The actual widget holding the layout items
        self.main_content = QWidget()
        self.main_layout = QVBoxLayout(self.main_content)
        self.main_layout.setContentsMargins(8, 4, 8, 4)
        self.content_area.setWidget(self.main_content)
        self.content_area.setWidgetResizable(True)

        self.layout.addWidget(self.content_area)

        # Animation
        self.toggle_animation = QPropertyAnimation(self, b"maximumHeight")
        self.toggle_animation.setDuration(200)
        self.toggle_animation.finished.connect(self._on_animation_finished)

    @pyqtProperty(int)
    def maximumHeight(self):
        return self.content_area.maximumHeight()

    @maximumHeight.setter
    def maximumHeight(self, height):
        self.content_area.setMaximumHeight(height)

    def _on_toggled(self, checked: bool):
        title_text = self.toggle_button.text()[2:] # strip arrow
        self.toggle_button.setText(f"▼ {title_text}" if checked else f"▶ {title_text}")

        # Stop any running animation
        if self.toggle_animation.state() == QAbstractAnimation.State.Running:
            self.toggle_animation.stop()

        self.toggle_animation.setStartValue(self.content_area.maximumHeight())
        if checked:
            content_height = self.main_content.sizeHint().height()
            self.toggle_animation.setEndValue(content_height)
        else:
            self.toggle_animation.setEndValue(0)

        self.toggle_animation.start()

    def _on_animation_finished(self):
        """After collapse, ask the top-level window to reclaim freed space."""
        if self.content_area.maximumHeight() == 0:
            window = self.window()
            if window:
                hint = window.sizeHint()
                current = window.size()
                new_h = min(current.height(), max(hint.height(), window.minimumHeight()))
                if new_h < current.height():
                    window.resize(current.width(), new_h)

    def add_widget(self, widget: QWidget):
        self.main_layout.addWidget(widget)

    def add_layout(self, layout):
        self.main_layout.addLayout(layout)


class AccordionWidget(QWidget):
    """A container for multiple AccordionSections."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.sections = []

    def add_section(self, title: str) -> AccordionSection:
        section = AccordionSection(title, self)
        self.sections.append(section)
        self.layout.addWidget(section)
        return section

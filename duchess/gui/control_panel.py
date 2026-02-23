"""Control panel widget for Duchess, extracted from MainWindow for cleaner UI composition."""

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, 
    QTextEdit, QGroupBox, QGridLayout, QHBoxLayout, QScrollArea, QFrame
)
from duchess.gui.opening_explorer import OpeningExplorerWidget
from duchess.gui.accordion import AccordionWidget

# Thinking time options: (label, milliseconds)
TIME_OPTIONS = [
    ("0.5s", 500),
    ("1s", 1000),
    ("2s", 2000),
    ("5s", 5000),
    ("10s", 10000),
]

class ControlPanelWidget(QWidget):
    # Setup all signals
    new_game_requested = pyqtSignal(str)  # "white" or "black"
    resign_requested = pyqtSignal()
    load_external_engine_requested = pyqtSignal()
    heatmap_toggled = pyqtSignal()
    load_book_requested = pyqtSignal()
    reset_book_requested = pyqtSignal()
    db_explorer_requested = pyqtSignal()
    explorer_move_clicked = pyqtSignal(str) # UCI move text
    syzygy_files_selected = pyqtSignal(list) # list of file paths

    def __init__(self, initial_book_name: str, parent=None):
        super().__init__(parent)
        self._analysis_rows = {}
        self._setup_ui(initial_book_name)

    def _setup_ui(self, book_name):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        controls = QVBoxLayout(content)
        controls.setContentsMargins(0, 0, 0, 0)
        
        # New Game / Resign
        btn_white = QPushButton("New Game (White)")
        btn_white.clicked.connect(lambda: self.new_game_requested.emit("white"))
        btn_black = QPushButton("New Game (Black)")
        btn_black.clicked.connect(lambda: self.new_game_requested.emit("black"))
        btn_resign = QPushButton("Resign")
        btn_resign.clicked.connect(self.resign_requested.emit)
        
        controls.addWidget(btn_white)
        controls.addWidget(btn_black)
        controls.addWidget(btn_resign)

        # Thinking time selector
        controls.addWidget(QLabel("Engine time:"))
        self._time_combo = QComboBox()
        for label, _ in TIME_OPTIONS:
            self._time_combo.addItem(label)
        self._time_combo.setCurrentIndex(1)  # default 1s
        controls.addWidget(self._time_combo)

        # Move log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumWidth(200)
        controls.addWidget(QLabel("Moves:"))
        controls.addWidget(self._log)

        # Analysis panel
        self._analysis_box = QGroupBox("Analysis")
        self._analysis_layout = QGridLayout()
        self._analysis_layout.setColumnStretch(2, 1)  # PV column stretches
        self._analysis_box.setLayout(self._analysis_layout)
        controls.addWidget(self._analysis_box)

        # Advanced Settings Accordion
        accordion = AccordionWidget()
        
        # 1. External Engines
        engine_sec = accordion.add_section("External Engines")
        btn_load = QPushButton("Load External Engine...")
        btn_load.clicked.connect(self.load_external_engine_requested.emit)
        engine_sec.add_widget(btn_load)
        
        # Threat heatmap toggle
        self._btn_heatmap = QPushButton("Threat Heatmap")
        self._btn_heatmap.setCheckable(True)
        self._btn_heatmap.clicked.connect(self.heatmap_toggled.emit)
        engine_sec.add_widget(self._btn_heatmap)

        # 2. Opening Books & Database
        book_sec = accordion.add_section("Opening Book & Database")
        self._book_label = QLabel(f"Book: {book_name or 'None'}")
        book_sec.add_widget(self._book_label)
        
        book_btn = QPushButton("Load Book...")
        book_btn.clicked.connect(self.load_book_requested.emit)
        book_sec.add_widget(book_btn)

        book_reset = QPushButton("Reset to Default")
        book_reset.clicked.connect(self.reset_book_requested.emit)
        book_sec.add_widget(book_reset)
        
        db_explorer_btn = QPushButton("Colossal Database Explorer")
        db_explorer_btn.clicked.connect(self.db_explorer_requested.emit)
        book_sec.add_widget(db_explorer_btn)

        # 3. Syzygy Tablebases
        syzygy_sec = accordion.add_section("Syzygy Tablebases")
        self._tb_label = QLabel("Files: None")
        syzygy_sec.add_widget(self._tb_label)
        
        tb_btn = QPushButton("Select Files (.rtbw/.rtbz)")
        tb_btn.clicked.connect(self._select_syzygy_files)
        syzygy_sec.add_widget(tb_btn)

        controls.addWidget(accordion)

        # Opening Explorer panel (data from Lichess Masters database)
        self._explorer = OpeningExplorerWidget()
        self._explorer.move_clicked.connect(self.explorer_move_clicked.emit)
        controls.addWidget(self._explorer)

        controls.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def selected_time_ms(self) -> int:
        return TIME_OPTIONS[self._time_combo.currentIndex()][1]

    def set_book_name(self, name: str):
        self._book_label.setText(f"Book: {name or 'None'}")
        
    def _select_syzygy_files(self):
        from PyQt6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Syzygy Tablebase Files",
            "",
            "Syzygy (*.rtbw *.rtbz);;All Files (*)"
        )
        if files:
            self._tb_label.setText(f"Files: {len(files)} loaded")
            self.syzygy_files_selected.emit(files)
        
    def append_log(self, text: str):
        self._log.append(text)
        
    def insert_log(self, text: str):
        self._log.insertPlainText(text)
        
    def clear_log(self):
        self._log.clear()

    @property
    def heatmap_button(self) -> QPushButton:
        return self._btn_heatmap
        
    @property
    def explorer(self) -> OpeningExplorerWidget:
        return self._explorer

    def add_analysis_row(self, name: str):
        row = self._analysis_layout.rowCount()
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight: bold;")
        depth_label = QLabel("--")
        score_label = QLabel("--")
        pv_label = QLabel("")
        pv_label.setWordWrap(True)
        
        self._analysis_layout.addWidget(name_label, row, 0)
        self._analysis_layout.addWidget(depth_label, row, 1)
        self._analysis_layout.addWidget(score_label, row, 2)
        self._analysis_layout.addWidget(pv_label, row, 3)
        
        self._analysis_rows[name] = {
            "depth": depth_label,
            "score": score_label,
            "pv": pv_label,
        }
        
    def get_analysis_row(self, name: str) -> dict:
        return self._analysis_rows.get(name)

    def clear_analysis(self):
        for row in self._analysis_rows.values():
            row["depth"].setText("--")
            row["score"].setText("--")
            row["pv"].setText("")

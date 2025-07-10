LIGHT_THEME_STYLESHEET = """
QWidget { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e0eafc, stop:1 #cfdef3); font-size: 10pt; }
QLabel { color: #333; background-color: transparent; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget { padding: 6px; border: 1px solid #bdc3c7; border-radius: 4px; background-color: white; color: #333; }
QPushButton { padding: 8px 12px; border-radius: 4px; font-weight: bold; }
QPushButton#go_button { background-color: #2ecc71; color: white; border: 1px solid #27ae60; }
QPushButton#go_button:hover { background-color: #27ae60; }
QPushButton#settings_button { background-color: #3498db; color: white; border: 1px solid #2980b9; }
QPushButton#settings_button:hover { background-color: #2980b9; }
QPushButton#info_button { background-color: #9b59b6; color: white; border: 1px solid #8e44ad; }
QPushButton#info_button:hover { background-color: #8e44ad; }
QProgressBar { border: 1px solid #bdc3c7; border-radius: 5px; text-align: center; background-color: #ecf0f1; color: #2c3e50; }
QProgressBar::chunk { background-color: #2ecc71; border-radius: 4px; }
QMenuBar { background-color: #dde4eb; color: #333; }
QMenuBar::item:selected { background-color: #c5d0dd; }
QMenu { background-color: #f0f4f8; border: 1px solid #c5d0dd; }
QMenu::item:selected { background-color: #d0dae4; }
QDialog { background-color: #f8f9fa; }
QListWidget::item { padding: 5px; }
"""
DARK_THEME_STYLESHEET = """
QWidget { background-color: #2b2b2b; color: #f0f0f0; font-size: 10pt; border: none; }
QMainWindow, QDialog { background-color: #2b2b2b; }
QLabel { color: #f0f0f0; background-color: transparent; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QTextBrowser { padding: 6px; border: 1px solid #555555; border-radius: 4px; background-color: #3c3c3c; color: #f0f0f0; selection-background-color: #0078d7; }
QPushButton { padding: 8px 12px; border-radius: 4px; font-weight: bold; color: white; }
QPushButton#go_button { background-color: #4CAF50; border: 1px solid #45a049; }
QPushButton#go_button:hover { background-color: #45a049; }
QPushButton#settings_button { background-color: #008CBA; border: 1px solid #007ba7; }
QPushButton#settings_button:hover { background-color: #007ba7; }
QPushButton#info_button { background-color: #9b59b6; border: 1px solid #8e44ad; }
QPushButton#info_button:hover { background-color: #8e44ad; }
QProgressBar { border: 1px solid #555; border-radius: 5px; text-align: center; background-color: #3c3c3c; color: #f0f0f0; }
QProgressBar::chunk { background-color: #4CAF50; border-radius: 4px; }
QMenuBar { background-color: #3c3c3c; color: #f0f0f0; }
QMenuBar::item:selected { background-color: #555555; }
QMenu { background-color: #3c3c3c; border: 1px solid #555555; }
QMenu::item:selected { background-color: #555555; }
QListWidget::item:selected { background-color: #0078d7; color: white; }
QListWidget::item { padding: 5px; }
QCheckBox::indicator { border: 1px solid #555; border-radius: 3px; background-color: #3c3c3c; }
QCheckBox::indicator:checked { background-color: #0078d7; border-color: #0078d7; }
"""

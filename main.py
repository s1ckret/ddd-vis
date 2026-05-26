import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QScrollArea, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QIcon

class ModernCard(QFrame):
    """A beautifully styled card to display domain components."""
    def __init__(self, name, comp_type, desc, parent=None):
        super().__init__(parent)
        self.setObjectName("ModernCard")
        
        # Design layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # Header layout (Name + Type Badge)
        header_layout = QHBoxLayout()
        
        name_label = QLabel(name)
        name_label.setObjectName("CardName")
        name_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        
        badge_label = QLabel(comp_type.upper())
        badge_label.setObjectName("CardBadge")
        badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        badge_label.setFont(badge_font)
        
        # Color badge depending on the DDD stereotype
        if comp_type.lower() == "aggregate":
            badge_label.setStyleSheet("background-color: rgba(147, 51, 234, 0.25); color: #c084fc; border: 1px solid rgba(147, 51, 234, 0.4);")
        elif comp_type.lower() == "entity":
            badge_label.setStyleSheet("background-color: rgba(59, 130, 246, 0.25); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4);")
        elif comp_type.lower() == "value object":
            badge_label.setStyleSheet("background-color: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);")
        else: # Event / Command
            badge_label.setStyleSheet("background-color: rgba(245, 158, 11, 0.25); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);")
            
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(badge_label)
        
        layout.addLayout(header_layout)
        
        # Description
        desc_label = QLabel(desc if desc else "No description provided.")
        desc_label.setObjectName("CardDescription")
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(desc_label)
        
        # Styling sheet for the card
        self.setStyleSheet("""
            #ModernCard {
                background-color: #1e1e24;
                border: 1px solid #2e2e38;
                border-radius: 12px;
            }
            #ModernCard:hover {
                border: 1px solid #7c3aed;
                background-color: #23232a;
            }
            #CardName {
                color: #f3f4f6;
            }
            #CardDescription {
                color: #9ca3af;
            }
            #CardBadge {
                padding: 4px 10px;
                border-radius: 6px;
                min-width: 80px;
            }
        """)
        
        # Subtle shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

class DDDVisualizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DDD Visualizer Studio")
        self.setMinimumSize(QSize(960, 640))
        
        # Set central widget and layout
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        
        main_layout = QHBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Sidebar / Control Panel
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(340)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 28, 24, 28)
        sidebar_layout.setSpacing(20)
        
        # Header / Title
        title_label = QLabel("DDD Visualizer")
        title_label.setObjectName("SidebarTitle")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        
        subtitle_label = QLabel("Modeling Ubiquitous Language")
        subtitle_label.setObjectName("SidebarSubtitle")
        subtitle_label.setFont(QFont("Segoe UI", 9))
        
        title_container = QVBoxLayout()
        title_container.addWidget(title_label)
        title_container.addWidget(subtitle_label)
        title_container.setSpacing(4)
        sidebar_layout.addLayout(title_container)
        
        # Divider Line
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("DividerLine")
        sidebar_layout.addWidget(divider)
        
        # Input Form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(14)
        
        # Component Name Input
        name_container = QVBoxLayout()
        name_container.setSpacing(6)
        name_title = QLabel("Component Name")
        name_title.setObjectName("InputLabel")
        name_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. OrderAggregate, PaymentProcessed")
        self.name_input.setObjectName("ModernInput")
        name_container.addWidget(name_title)
        name_container.addWidget(self.name_input)
        form_layout.addLayout(name_container)
        
        # Stereotype Dropdown
        type_container = QVBoxLayout()
        type_container.setSpacing(6)
        type_title = QLabel("DDD Stereotype")
        type_title.setObjectName("InputLabel")
        type_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.type_dropdown = QComboBox()
        self.type_dropdown.setObjectName("ModernCombo")
        self.type_dropdown.addItems(["Aggregate", "Entity", "Value Object", "Domain Event"])
        type_container.addWidget(type_title)
        type_container.addWidget(self.type_dropdown)
        form_layout.addLayout(type_container)
        
        # Description Input
        desc_container = QVBoxLayout()
        desc_container.setSpacing(6)
        desc_title = QLabel("Description")
        desc_title.setObjectName("InputLabel")
        desc_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Describe the ubiquitous language definition, attributes, or business rules...")
        self.desc_input.setObjectName("ModernTextEdit")
        desc_container.addWidget(desc_title)
        desc_container.addWidget(self.desc_input)
        form_layout.addLayout(desc_container)
        
        sidebar_layout.addLayout(form_layout)
        
        # Buttons
        self.add_button = QPushButton("Create Component")
        self.add_button.setObjectName("AddButton")
        self.add_button.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.add_button.clicked.connect(self.add_component)
        sidebar_layout.addWidget(self.add_button)
        
        sidebar_layout.addStretch()
        
        # Footer Credits
        footer_label = QLabel("Design: Antigravity Studio 2026")
        footer_label.setObjectName("FooterLabel")
        footer_label.setFont(QFont("Segoe UI", 8))
        sidebar_layout.addWidget(footer_label)
        
        # Main Visual Area / Canvas
        canvas = QWidget()
        canvas.setObjectName("Canvas")
        
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(32, 28, 32, 28)
        canvas_layout.setSpacing(20)
        
        # Canvas Header
        canvas_header = QHBoxLayout()
        canvas_title = QLabel("Domain Model Architecture")
        canvas_title.setObjectName("CanvasTitle")
        canvas_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        
        self.stats_label = QLabel("0 elements")
        self.stats_label.setObjectName("StatsLabel")
        self.stats_label.setFont(QFont("Segoe UI", 10))
        
        canvas_header.addWidget(canvas_title)
        canvas_header.addStretch()
        canvas_header.addWidget(self.stats_label)
        canvas_layout.addLayout(canvas_header)
        
        # Scroll Area for Model Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("ModernScroll")
        
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("ScrollContent")
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(16)
        self.cards_layout.addStretch() # Push everything up initially
        
        self.scroll_area.setWidget(self.scroll_content)
        canvas_layout.addWidget(self.scroll_area)
        
        # Add side panel and canvas to the main window
        main_layout.addWidget(sidebar)
        main_layout.addWidget(canvas)
        
        # Global Stylesheet for Modern Dark UI
        self.setStyleSheet("""
            #CentralWidget {
                background-color: #0b0f19;
            }
            #Sidebar {
                background-color: #0f172a;
                border-right: 1px solid #1e293b;
            }
            #Canvas {
                background-color: #020617;
            }
            #SidebarTitle {
                color: #f8fafc;
            }
            #SidebarSubtitle {
                color: #94a3b8;
            }
            #DividerLine {
                color: #1e293b;
                background-color: #1e293b;
                max-height: 1px;
            }
            #InputLabel {
                color: #38bdf8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            #ModernInput {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                color: #f8fafc;
                selection-background-color: #7c3aed;
            }
            #ModernInput:focus {
                border: 1px solid #7c3aed;
                background-color: #0f172a;
            }
            #ModernCombo {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                color: #f8fafc;
            }
            #ModernCombo:focus {
                border: 1px solid #7c3aed;
            }
            #ModernCombo QAbstractItemView {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #1e293b;
                selection-background-color: #7c3aed;
            }
            #ModernTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px 12px;
                color: #f8fafc;
                min-height: 100px;
            }
            #ModernTextEdit:focus {
                border: 1px solid #7c3aed;
                background-color: #0f172a;
            }
            #AddButton {
                background-color: #7c3aed;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 12px;
                margin-top: 10px;
            }
            #AddButton:hover {
                background-color: #8b5cf6;
            }
            #AddButton:pressed {
                background-color: #6d28d9;
            }
            #FooterLabel {
                color: #475569;
            }
            #CanvasTitle {
                color: #f8fafc;
            }
            #StatsLabel {
                color: #10b981;
                background-color: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 20px;
                padding: 4px 14px;
            }
            #ModernScroll {
                border: none;
                background-color: transparent;
            }
            #ScrollContent {
                background-color: transparent;
            }
        """)
        
        # Track items count
        self.items_count = 0
        
        # Populate with some beautiful pre-configured example data cards
        self.add_initial_mock_data()

    def add_initial_mock_data(self):
        """Adds a couple of sample cards to showcase visual aesthetics immediately."""
        self.add_item("OrderAggregate", "Aggregate", "Root element representing customers' purchasing lifecycle. Validates invariant constraints across line items.")
        self.add_item("OrderPaidEvent", "Domain Event", "Emitted asynchronously when the payment gateway successfully processes the customer's invoice.")
        self.add_item("Money", "Value Object", "Immutably models financial values, specifying an ISO currency and amount. Prevents invalid mixed-currency operations.")

    def add_item(self, name, comp_type, desc):
        """Creates a card widget and inserts it into the canvas listing."""
        card = ModernCard(name, comp_type, desc)
        
        # Insert card at the top, shifting the stretch down
        self.cards_layout.insertWidget(self.items_count, card)
        
        self.items_count += 1
        self.stats_label.setText(f"{self.items_count} elements")

    def add_component(self):
        """Action handler when user clicks Create Component."""
        name = self.name_input.text().strip()
        comp_type = self.type_dropdown.currentText()
        desc = self.desc_input.toPlainText().strip()
        
        if not name:
            # Simple soft validation feedback - reset focus highlight
            self.name_input.setFocus()
            self.name_input.setStyleSheet("border: 1px solid #ef4444; background-color: #1e293b; color: #f8fafc;")
            return
            
        # Reset border styles on successful input
        self.name_input.setStyleSheet("")
        
        self.add_item(name, comp_type, desc)
        
        # Clear inputs
        self.name_input.clear()
        self.desc_input.clear()
        self.name_input.setFocus()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion') # Clean cross-platform baseline style
    
    window = DDDVisualizerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

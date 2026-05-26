from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF
from collections import deque
import numpy as np

class MultiChannelChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history_size = 150  # Number of historical points to display along time axis
        self.history = []        # List of deques, one per active channel
        self.num_channels = 0
        
        # High-contrast standard colors for up to 8 channels
        self.channel_colors = [
            QColor(220, 53, 69),    # Red
            QColor(0, 123, 255),    # Blue
            QColor(40, 167, 69),    # Green
            QColor(253, 126, 20),   # Orange
            QColor(111, 66, 193),   # Purple
            QColor(23, 162, 184),   # Teal
            QColor(232, 62, 140),   # Pink
            QColor(255, 193, 7)     # Amber/Yellow
        ]
        self.setMinimumHeight(280)

    def update_levels(self, levels):
        """Receive a list of level floats (one per channel) and push them onto rolling queues."""
        n_ch = len(levels)
        if n_ch == 0:
            return

        # If number of active channels changes, reset queues to prevent indexing issues
        if n_ch != self.num_channels:
            self.num_channels = n_ch
            self.history = [
                deque([0.0] * self.history_size, maxlen=self.history_size) 
                for _ in range(n_ch)
            ]

        # Add new level data and clip to normal 0.0 -> 1.0 limits
        for i in range(n_ch):
            val = max(0.0, min(1.0, levels[i]))
            self.history[i].append(val)

        # Trigger a redraw of the QWidget
        self.update()

    def reset_chart(self):
        """Wipe channel history and reset layout status."""
        self.history = []
        self.num_channels = 0
        self.update()

    def paintEvent(self, event):
        """Draw the coordinate plane, grid divisions, labels, legend, and multi-channel paths."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Canvas padding offsets
        left_margin = 55
        right_margin = 25
        top_margin = 35
        bottom_margin = 35

        chart_w = w - left_margin - right_margin
        chart_h = h - top_margin - bottom_margin

        if chart_w <= 0 or chart_h <= 0:
            return

        # Draw chart bounding frame
        painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(left_margin, top_margin, chart_w, chart_h)

        # Draw horizontal amplitude markers & grid dashed lines
        painter.setFont(QFont("Arial", 8))
        divisions = 5
        for i in range(divisions):
            ratio = i / (divisions - 1)
            y_coord = int(top_margin + chart_h * (1 - ratio))
            
            # Horizontal lines
            if i > 0 and i < divisions - 1:
                painter.setPen(QPen(Qt.GlobalColor.lightGray, 1, Qt.PenStyle.DashLine))
                painter.drawLine(left_margin, y_coord, left_margin + chart_w, y_coord)
                
            # Text values (0.00, 0.25, 0.50, 0.75, 1.00)
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            val_text = f"{ratio:.2f}"
            painter.drawText(12, y_coord + 4, val_text)

        # Draw X-axis label
        painter.drawText(left_margin + chart_w // 2 - 25, h - 10, "Time (rolling) ->")

        # Draw empty helper if no audio streams are running
        if self.num_channels == 0:
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(
                left_margin + 30, 
                top_margin + chart_h // 2, 
                "Audio stream inactive. Start capture or load a WAV file to visualize."
            )
            return

        # Draw level paths for each active audio channel
        for ch in range(self.num_channels):
            # Resolve color code
            color = self.channel_colors[ch % len(self.channel_colors)]
            painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            
            # Generate linear coordinate maps
            path_coords = QPolygonF()
            for idx in range(self.history_size):
                # X coordinate: proportional step along the buffer width
                x = left_margin + (idx * chart_w) / (self.history_size - 1)
                
                # Y coordinate: inverse level representation
                level_val = self.history[ch][idx]
                y = top_margin + chart_h * (1.0 - level_val)
                
                path_coords.append(QPointF(x, y))
                
            # Render path
            painter.drawPolyline(path_coords)

        # Draw Legend Indicators
        legend_x = left_margin + 15
        legend_y = top_margin - 12
        for ch in range(self.num_channels):
            color = self.channel_colors[ch % len(self.channel_colors)]
            
            # Small colored box
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            painter.drawRect(legend_x, legend_y - 8, 12, 8)
            
            # Label
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.drawText(legend_x + 18, legend_y, f"Ch {ch + 1}")
            
            # Advance column position
            legend_x += 65
            if legend_x + 55 > left_margin + chart_w:
                legend_x = left_margin + 15
                legend_y += 15  # Wrap to next legend row if required

import sys
import time
import itertools
from queue import Queue, Empty
from PyQt6.QtCore import QThread, QObject, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QHBoxLayout, QVBoxLayout, QWidget, QLabel

# --- 1. THE DATA PIPELINE ---

def raw_generator():
    """Stage 1: Generates raw numbers."""
    count = 0
    while True:
        yield (time.time(), count)
        count += 1
        time.sleep(0.05) # Generate raw data every 50ms

def processed_generator(upstream):
    """Stage 2: Multiplies the raw value by 10."""
    for timestamp, val in upstream:
        yield (timestamp, val * 10)

def filtered_generator(upstream):
    """Stage 3: Only lets even processed numbers through."""
    for timestamp, val in upstream:
        if val % 20 == 0:
            yield (timestamp, val)

# --- 2. THE THREADED PIPELINE SPY ---

class PipelineWorker(QObject):
    def __init__(self, raw_q, proc_q, filt_q):
        super().__init__()
        # Separate queues for each stage's debug view
        self.raw_q = raw_q
        self.proc_q = proc_q
        self.filt_q = filt_q
        self.running = True

    def run(self):
        # Initialize the base generator
        raw_stream = raw_generator()

        while self.running:
            # --- STAGE 1: Spy on Raw ---
            # Split into 2 independent streams
            raw_stream, raw_spy = itertools.tee(raw_stream, 2)
            # Push the next item from the spy stream to the UI queue
            self.raw_q.put(next(raw_spy))

            # --- STAGE 2: Process & Spy ---
            # Pass the main raw stream into the processor
            proc_stream = processed_generator(raw_stream)
            proc_stream, proc_spy = itertools.tee(proc_stream, 2)
            self.proc_q.put(next(proc_spy))

            # --- STAGE 3: Filter & Spy ---
            # Pass the main processed stream into the filter
            filt_stream = filtered_generator(proc_stream)
            filt_stream, filt_spy = itertools.tee(filt_stream, 2)
            
            # Because filtering skips items, 'next()' might block until a match is found.
            # To keep things moving, we consume exactly one item per loop iteration.
            self.filt_q.put(next(filt_spy))

            # Advance the main stream by one item for the next loop cycle
            next(filt_stream)

# --- 3. THE MULTI-COLUMN UI ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pipeline Debugger")
        self.setGeometry(100, 100, 800, 400)

        # Create three queues for the three stages
        self.raw_queue = Queue()
        self.proc_queue = Queue()
        self.filt_queue = Queue()

        self.setup_ui()
        self.start_pipeline()

        # Wake up every 200ms to empty all queues
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_displays)
        self.timer.start()

    def setup_ui(self):
        layout = QHBoxLayout()
        
        # Helper to create debug columns
        def create_column(title):
            col_layout = QVBoxLayout()
            col_layout.addWidget(QLabel(title))
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            col_layout.addWidget(text_edit)
            layout.addLayout(col_layout)
            return text_edit

        self.raw_view = create_column("1. Raw Data")
        self.proc_view = create_column("2. Processed (x10)")
        self.filt_view = create_column("3. Filtered (Evens)")

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def start_pipeline(self):
        self.thread = QThread()
        self.worker = PipelineWorker(self.raw_queue, self.proc_queue, self.filt_queue)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def drain_queue_to_widget(self, queue, widget):
        """Helper to empty a queue and append to a specific text widget."""
        while True:
            try:
                ts, val = queue.get_nowait()
                time_str = time.strftime("%H:%M:%S", time.localtime(ts))
                widget.append(f"[{time_str}] -> {val}")
                queue.task_done()
            except Empty:
                break

    def update_displays(self):
        """Wakes up every 200ms and flushes all three pipelines to the screen."""
        self.drain_queue_to_widget(self.raw_queue, self.raw_view)
        self.drain_queue_to_widget(self.proc_queue, self.proc_view)
        self.drain_queue_to_widget(self.filt_queue, self.filt_view)

    def closeEvent(self, event):
        self.worker.running = False
        self.thread.quit()
        self.thread.wait()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
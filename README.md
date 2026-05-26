# 8-Channel Microphone Reader

A clean, stock-UI Python desktop utility built with PyQt6. The application dynamically queries your system's input audio devices (microphones), lists them alongside their maximum channel capability, and provides real-time 8-channel input level metering.

---

## Technical Stack
* **Python 3.8+**
* **PyQt6** (GUI Toolkit)
* **sounddevice** (PortAudio bindings)
* **numpy** (High-performance array manipulation)

---

## Quick Start Setup

Follow these simple instructions to set up your environment, install the required dependencies, and launch the utility.

### 1. Create a Virtual Environment
Navigate to this project directory and run:

```bash
python -m venv .venv
```

### 2. Activate the Virtual Environment
Depending on your terminal and Operating System, run one of the following commands:

#### **Windows (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
```

#### **Windows (Command Prompt - cmd)**
```cmd
.venv\Scripts\activate.bat
```

#### **macOS / Linux / Git Bash**
```bash
source .venv/bin/activate
```

---

### 3. Install Dependencies
Ensure your environment is active, then run:

```bash
pip install -r requirements.txt
```

---

### 4. Run the Application
Start the microphone reader by running:

```bash
python main.py
```

---

## Application Layout and Features
* **Select Microphone Dropdown**: Dynamically queries the system's active sound cards and lists all input devices showing their maximum hardware channels.
* **8-Channel Real-Time Levels**: Displays 8 native OS progress bars. Audio capture takes place asynchronously on a separate high-priority audio callback thread.
* **Automatic Hardware Fallback**: If an 8-channel audio device is selected, the stream binds all 8 channels. If a standard stereo/mono microphone is selected, the application gracefully initializes using the hardware's maximum capability, zeroing out inactive channels to prevent PortAudio thread crashes.
* **Refresh Button**: Allows you to plug in a new USB microphone/soundcard and scan for it instantly without restarting the app.

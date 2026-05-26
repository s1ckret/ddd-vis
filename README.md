# DDD Visualizer Studio

A beautifully styled, high-fidelity Domain-Driven Design (DDD) utility developed with Python and PyQt6. This application leverages customized dark mode stylesheets (QSS), glowing components, responsive canvas layouts, and custom badges to document, model, and visualize your domain model's aggregates, entities, value objects, and domain events.

---

## Technical Stack
* **Python 3.8+**
* **PyQt6** (GUI Toolkit)
* **Fusion Style** (Cross-platform GUI engine configuration)

---

## Quick Start Setup

Follow these simple instructions to create a virtual environment, install the required dependencies, and launch the visualizer.

### 1. Create a Virtual Environment
Navigate to this project directory and run the following command:

```bash
python -m venv .venv
```

This creates a local, isolated environment named `.venv` in the root of your project directory.

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
Start the visualizer by running:

```bash
python main.py
```

---

## Features Showcase
* **Ubiquitous Language Tracker**: Add Aggregates, Entities, Value Objects, and Domain Events instantly.
* **Premium Dark Mode Palette**: Styled with a deep charcoal and slate blue canvas, highlighted with purple/teal gradients and soft rounded corners.
* **Badged Categorization**: Visual separation of core DDD stereotypes.
* **Local Sandboxed Virtual Environment**: Self-contained workspace without modifying global Python installations.

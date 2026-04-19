**Matika** | Version: **1.0.7** | Copyright (c) 2026 Patrick James Tallman

# Matika Installation Guide

Matika can be installed as a standalone application using native installers or setup manually from source for development.

## 1. Standalone Installation (Recommended for Users)

### macOS (.dmg)
1. **Download:** Get the latest `matika-macos.dmg` from the Releases page.
2. **Install:** Drag the Matika icon to your `Applications` folder.
3. **Launch:** Open Matika from your Applications. If you see a security warning, go to **System Settings > Privacy & Security** and click **Open Anyway**.

### Windows (.exe)
1. **Download:** Get the latest `matika-setup.exe`.
2. **Install:** Run the installer and follow the prompts.
3. **Launch:** Use the Desktop shortcut to start the application.

---

## 2. Manual Installation (For Developers)

### Prerequisites
- **Python 3.14+**
- **Node.js 18+**
- **uv** (Optional but recommended)

### Step-by-Step Setup
1. **Clone Repository:**
   ```bash
   git clone https://github.com/pjtallman/Matika.git
   cd Matika
   ```

2. **Setup Virtual Environment:**
   ```bash
   uv venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate     # Windows
   ```

3. **Install Dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Build Frontend Assets:**
   ```bash
   npm install
   npm run build
   ```

5. **Start Server:**
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   python src/matika/main.py
   ```

---

## 3. Accessing the Application
Open your browser and navigate to: **http://127.0.0.1:8000**

### Initial Admin Credentials
- **Username:** `admin`
- **Password:** `adminpassword`
- *Note: You will be prompted to change this password on your first login.*

---

## 4. Managing Plugins
Matika is a framework. To add functionality:
1. Navigate to the `plugins/` directory.
2. Add your plugin folders (e.g., `eyerate`).
3. Restart the server.

---

## 5. Troubleshooting
- **ModuleNotFoundError:** Ensure your `PYTHONPATH` includes the `src` directory.
- **Port 8000 Busy:** Kill any existing `uvicorn` or `python` processes running on that port.
- **Bcrypt Errors:** Ensure you are using Python 3.14+ and have the latest `bcrypt` package installed.

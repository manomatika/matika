**Matika** | Version: **1.0.7** | Copyright (c) 2026 Patrick James Tallman. All Rights Reserved.

# Matika Installation Guide

Thank you for choosing Matika! This guide will help you get the application running on your computer in just a few minutes.

## 1. Installation

### macOS (.dmg)
1.  **Open:** Double-click the downloaded `matika-macos.dmg`.
2.  **Install:** Drag the Matika icon to your `Applications` folder.
3.  **Launch:** You can now launch Matika from your Applications folder.

### Windows (.exe Installer)
1.  **Run:** Open the `matika-setup.exe` file.
2.  **Install:** Follow the on-screen prompts to select your installation folder.
3.  **Shortcut:** A shortcut will be created on your Desktop.

---

## 2. Running for the First Time

### macOS Instructions
1.  **Security Warning:** You may see a message saying: *"Apple could not verify “matika” is free of malware..."*
2.  **Bypass Warning:**
    -   Click **OK** or **Cancel** on the popup.
    -   Go to **System Settings** > **Privacy & Security**.
    -   Scroll down to the **Security** section.
    -   Click **Open Anyway** next to the message about Matika being blocked.
    -   Enter your Mac password if prompted, then click **Open** on the final confirmation.
3.  **Keep Terminal Open:** A Terminal window will open to run the server. Leave this window open while you use Matika.

### Windows Instructions
1.  **SmartScreen:** If a blue Windows SmartScreen window appears, click **More info** and then **Run anyway**.
2.  **Keep Console Open:** A command prompt window will open. Leave this window open while you use Matika.

---

## 3. Accessing Matika
Matika is designed to open your web browser automatically once it starts. If it does not, open your web browser and go to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

### Initial Login (Admin)
For security, you must use these temporary credentials for your first login. The system will immediately prompt you to change your password.
- **Username:** `admin`
- **Password:** `adminpassword`

---

## 4. Important Note on Data
Matika will automatically create a `data/` folder in its installation directory to store your database. **Do not delete this folder**, as it contains all your saved yield and security information.

---

## 5. Troubleshooting
- **Port 8000 in use:** Ensure no other application is using port 8000.
- **Support:** Please contact your system administrator if you experience further issues.

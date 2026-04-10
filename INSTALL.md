**Matika** | Version: **0.0.1** | Copyright (c) 2026 Patrick James Tallman



# Matika Installation Guide

Thank you for choosing Matika! This guide will help you get the application running on your computer in just a few minutes.

## 1. Prepare Installation Directory
Before extracting the files, create a new folder where you want Matika to live (e.g., on your Desktop or in your Applications folder).
- **Name it:** `matika`

## 2. Extract the ZIP
Move the downloaded `.zip` file into your new `matika` folder and extract its contents there.

## 3. Run the Application

### macOS Instructions
1.  **Open:** Double-click the `matika` executable.
2.  **Security Warning:** You will likely see a message saying: *"Apple could not verify “matika” is free of malware..."*
3.  **Bypass Warning:**
    -   Click **OK** or **Cancel** on the popup.
    -   Go to **System Settings** > **Privacy & Security**.
    -   Scroll down to the **Security** section.
    -   You will see a message about "matika" being blocked. Click **Open Anyway**.
    -   Enter your Mac password if prompted, then click **Open** on the final confirmation.
4.  **Keep Terminal Open:** A Terminal window will open. Leave this window open while you use Matika.

### Windows Instructions
1.  **Open:** Double-click `matika.exe`.
2.  **SmartScreen:** If a blue Windows SmartScreen window appears, click **More info** and then **Run anyway**.
3.  **Keep Console Open:** A command prompt window will open. Leave this window open while you use Matika.

## 4. Access Matika
Once the application starts, open your web browser and go to:
**[http://localhost:8000](http://localhost:8000)**

### Default Credentials:
- **Username:** `admin`
- **Password:** `adminpassword`

## 5. Troubleshooting
- **Port 8000 in use:** Ensure no other application is using port 8000.
- **Files Created:** On the first run, Matika will automatically create `data/` and `logs/` folders in your installation directory. Do not delete these, as they contain your database and activity history.

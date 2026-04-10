**Matika** | Version: **0.0.1** | Copyright (c) 2026 Patrick James Tallman



# Matika

Matika is a high-performance yield tracking and security maintenance application built with FastAPI and TypeScript.

## Quick Start

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/pjtallman/matika.git
    cd matika
    ```

2.  **Automated Installation:**
    Matika provides a unified installer that handles environment setup, frontend building, and validation.
    ```bash
    # Mac/Linux:
    python3 install.py

    # Windows:
    python install.py
    ```

3.  **Access the Application:**
    Once the installer finishes, open your browser and navigate to:
    `http://localhost:8000`

## Documentation

For more detailed information, please refer to the following guides:

- [Technical Architecture & Design](doc/ARCHITECTURE.md) - Deep dive into the stack, folder structure, and data model.
- [Deployment & Installation Guide](doc/DEPLOYMENT.md) - Detailed instructions for automated and manual setups on different OS.
- [Automation Scripts](scripts/README.md) - Documentation for development lifecycle scripts (milestones, releases).

## Features

- **Real-time Security Tracking:** Lookup and maintain security data (ETFs, Stocks, Mutual Funds).
- **Advanced Permissions:** Granular RBAC for pages and subjects (users/roles).
- **Data Mobility:** Export and import system and user data for backup or migration.
- **Internationalization:** Multi-language support (English, Spanish) with dynamic translation.
- **Maintenance Activity Pattern:** Consistent UI for administrative and data-entry tasks.

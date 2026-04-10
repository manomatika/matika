**Matika** | Version: **0.0.1** | Copyright (c) 2026 Patrick James Tallman



# Matika Technical Architecture & Design

## 1. Executive Summary
Matika is a high-performance yield tracking and security maintenance application built with a modern, layered architecture. It provides real-time security data lookups, bulk operations, and localized administrative controls.

## 2. Technology Stack
- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.14+)
- **Database:** [SQLite](https://sqlite.org/) with [SQLAlchemy](https://www.sqlalchemy.org/) ORM
- **Frontend:** [Jinja2](https://palletsprojects.com/p/jinja/) Templates, [TypeScript](https://www.typescriptlang.org/) (ESNext), Vanilla CSS
- **Tooling:** `npm` for TypeScript compilation, `pytest` for unit testing

## 3. Folder Structure (Best Practices)
The project follows a standard "src layout" to ensure clear separation between source code, tests, and data.

```
/
├── .gitignore              # Git ignore rules (node_modules, data, etc. are excluded)
├── README.md               # Basic project info and quick start
├── VERSION                 # Current application version
├── package.json            # Node.js dependencies and build scripts
├── tsconfig.json           # TypeScript configuration
├── pyproject.toml          # Python project configuration
├── pytest.ini              # Test configuration
├── requirements.txt        # Python dependencies
├── install.py              # Automated installation and deployment script
├── data/                   # Persistent storage (SQLite .db files)
├── doc/                    # Technical documentation
├── scripts/                # Dev/Ops automation scripts (release, milestone)
├── src/                    # Source code root
│   ├── frontend/           # TypeScript source files
│   └── matika/            # Main Python package
│       ├── main.py         # Application entry point and API routes
│       ├── database.py     # Data models and session management
│       ├── i18n.py         # Internationalization logic
│       ├── locales/        # Translation JSON files
│       ├── metadata/       # Activity-specific UI metadata
│       ├── static/         # Compiled JS, CSS, and uploaded assets
│       └── templates/      # HTML templates (Jinja2)
└── tests/                  # Unit and integration tests
```

## 4. Component Architecture

### 4.1. Maintenance Activity Pattern
Administrative pages follow a standardized pattern for consistency and rapid development.
- **`maintenance_activity_base.html`:** Implements a two-vertical-panel layout (Browse vs. Maintenance).
- **`MaintenanceActivityManager` (TS):** Base class for handling CRUD lifecycle events via AJAX.
- **Title Panel (TP):** Split into a Label Panel (LP) and a Button Bar Panel (BBP) for centralized actions.

## 6. Scalability & Distributed Architecture

While Matika is designed as a streamlined monolith, it follows cloud-native principles that allow it to scale from a single-node local setup to a distributed, high-availability environment.

### 6.1. Component Decoupling
The application is structured to allow independent scaling of its primary layers:

- **Frontend (Static Assets):** All TypeScript assets are compiled into standard JavaScript and CSS. In a scaled environment, these can be offloaded from the FastAPI server and served via Nginx, an AWS S3 bucket, or a global Content Delivery Network (CDN) like CloudFront.
- **Backend (API Service):** The FastAPI application is stateless (session state is currently handled via signed cookies/`SECRET_KEY`). Multiple instances can be run behind a Load Balancer (e.g., Nginx, HAProxy, AWS ALB).
- **Database (Persistence):** By default, Matika uses SQLite for simplicity. For scaling, the `DATABASE_URL` environment variable can be pointed to a client-server database like **PostgreSQL** or **MySQL** hosted on a separate, dedicated server or a managed service (e.g., AWS RDS).

### 6.2. Scaling Strategies

| Strategy | Local/Small (Default) | Distributed/Production |
| :--- | :--- | :--- |
| **Compute** | Single `uvicorn` process | Multiple containers (Docker/K8s) |
| **Database** | SQLite (`data/matika.db`) | PostgreSQL / RDS |
| **Storage** | Local SQLite (`data/`) | Central Database (PostgreSQL) |
| **Networking** | Direct Access (Port 8000) | Reverse Proxy (Nginx) + SSL |

### 6.3. Profile Photo Storage Strategy
Unlike traditional filesystem-based uploads, Matika uses **Database BLOB Storage** for profile photos.
- **Portability:** Eliminates the need for persistent volume mounts (like Docker volumes or NFS) for user media.
- **Consistency:** Database backups automatically include all user profile photos.
- **Serving:** Photos are served via a dedicated FastAPI route (`/settings/user/photo/{user_id}`) which retrieves the `LargeBinary` data and serves it with the correct `MIME` type.

### 6.4. Environment Variables
Scaling is managed primarily through environment configuration:
- `DATABASE_URL`: Connection string (e.g., `postgresql://user:pass@db-host:5432/matika`).
- `SECRET_KEY`: Must be identical across all backend nodes to allow consistent session validation.
- `PYTHONPATH`: Should include the `src` directory.

## 7. Data Model & Segregation

### 7.1. System vs. User Data
Matika distinguishes between **System Data** (distributed with the application) and **User Data** (created and maintained by the end-user).

- **System Data (`is_system=True`):**
    - **Default Roles:** `Admin` and `User` roles.
    - **Initial Permissions:** Standardized access control for all application pages.
    - **Core Settings:** Baseline configurations like `log_lines` and `version`.
    - *Purpose:* Provides the foundational environment required for the application to function. System data is typically protected from deletion to ensure system stability.

- **User Data (`is_system=False`):**
    - **Users:** Account information for all registered users.
    - **User Settings:** Personalizations like profile photos and language preferences.
    - **Custom Roles/Permissions:** Any additional access control entities defined by an administrator.
    - *Purpose:* Holds the personalized data and configuration that makes the application useful for a specific user or organization.

### 7.2. Persistence
All data is persisted in a local **SQLite** database file (`data/matika.db`).
- **Backup/Restore:** Users can use the built-in Export/Import functionality to migrate their data.
- **Relational Integrity:** Foreign key constraints ensure that deleting a user or role correctly handles associated permissions and settings.

```mermaid
erDiagram
    User ||--o{ UserSetting : has
    User }|..|{ Role : belongs_to
    Role ||--o{ Permission : grants
    User ||--o{ Permission : has_custom
    SystemSetting ||--o| App : configures

    User {
        int id PK
        string email UK
        string username UK
        string hashed_password
        bool is_authorized
        bool force_password_change
        string provider
        string photo_url
        blob photo_blob
        string photo_mime_type
    }
    Role {
        int id PK
        string name UK
        string description
        bool is_system
    }
    Permission {
        int id PK
        string page_path
        string page_type
        int role_id FK
        int user_id FK
        string level
        bool is_system
    }
    SystemSetting {
        string name PK
        string value
        bool is_system
    }
    UserSetting {
        int id PK
        int user_id FK
        string name
        string value
    }
```
- **Granular RBAC:** Permissions are tied to page paths and roles/users.
- **Sub-path Inheritance:** APIs automatically inherit permissions from their parent pages.
- **AJAX Validation:** All destructive or modifying actions are validated on the backend.

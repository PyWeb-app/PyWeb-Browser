<div align="center">
  <h1>🌐 PyWeb</h1>
  <p><b>A Minimalist, High-Performance Web Browser Built Entirely in Python</b></p>
</div>

---

## 📖 About The Project

**PyWeb** is a fully independent, minimalist web browser engineered from the ground up using Python. Unlike typical browser wrappers that rely on Chromium or WebKit, PyWeb is designed with a custom-built internal architecture. 

It handles everything from raw network requests and TLS handshakes to DOM tree construction, CSS parsing, and UI rendering. This project serves as a lightweight alternative to bloated modern browsers, providing developers and tech enthusiasts with a transparent, highly modular, and educational browser engine.

---

## ✨ Features & Technical Deep Dive

PyWeb is divided into specialized, decoupled modules. Here is a detailed look at what powers the browser under the hood:

### 1. ⚙️ Custom Browser Engine (`core/engine/`)
At the heart of PyWeb is its bespoke rendering and execution engine:
* **DOM API (`dom_api.py`):** Constructs and manages the Document Object Model tree dynamically, allowing structural manipulation of web pages.
* **Page Context (`page_context.py`):** Isolates the state and lifecycle of individual web pages, ensuring memory safety.
* **Layout & Styling (`layout.py`, `style.py`):** Calculates element geometries, applies CSS rules, and determines visual placement.
* **V8 Bridge (`v8_bridge.py`):** Acts as a secure intermediary layer, allowing communication between Python and JavaScript execution environments.

### 2. 📡 Advanced Network Stack (`core/network/`)
PyWeb manages its own network traffic:
* **HTTP Client (`http_client.py`):** Custom-built client to handle GET, POST, and other HTTP methods with full header parsing.
* **DNS Resolver (`dns_resolver.py`):** Resolves domain names to IP addresses internally for faster lookup.
* **TLS Handshake (`tls_handshake.py`):** Manages secure (HTTPS) connections, certificates, and cryptographic protocols.

### 3. 🧩 Native Parsers (`core/parser/`)
* **HTML Parser (`html_parser.py`):** A fault-tolerant parser that reads raw HTML byte streams and converts them into structured node trees.
* **CSS Parser (`css_parser.py`):** Interprets cascading style sheets, resolves selectors, and computes styles for the layout engine.

### 4. 🛡️ Security Architecture (`security/`)
* **Sandbox (`sandbox.py`):** Isolates web page execution from the host OS, preventing malicious script access.
* **CORS Policy (`cors_policy.py`):** Enforces Cross-Origin Resource Sharing rules.

### 5. 🗄️ Storage & Data Management (`storage/`)
* **History & Bookmarks:** Optimized local database management for browsing history and bookmarks.
* **Cookie Manager (`cookies.py`):** Handles session persistence and secure cookie storage.
* **Download Manager (`download_manager.py`):** A robust system for tracking, pausing, and resuming file downloads.

---

## 📂 Repository Structure

```text
PyWeb/
├── core/
│   ├── engine/          # DOM, V8 Bridge, Layout, Styles
│   ├── network/         # HTTP Client, DNS, TLS
│   ├── parser/          # Custom HTML & CSS Parsers
│   └── scheduler/       # Event Loop & Thread Pool
├── pages/               # Offline UI pages (New Tab, History, 404)
├── security/            # Sandbox and CORS enforcement
├── storage/             # Database & storage handlers
├── ui/                  # Window, Tab, and Render logic
├── install.bat          # Windows Setup Script
├── main.py              # Application Entry Point
├── pyweb.bat            # Quick Launch Script
└── register_browser.py  # OS Default Browser registration tool

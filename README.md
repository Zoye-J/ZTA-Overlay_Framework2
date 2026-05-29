# 🇧🇩 ZTA Overlay Network — OpenZiti‑inspired Zero Trust Architecture

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3.3-black?logo=flask&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-auth-00C7B7?logo=jsonwebtokens&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![HTTPS](https://img.shields.io/badge/TLS-1.3-green?logo=cloudflare&logoColor=white)

A production‑ready, OpenZiti‑inspired **Zero Trust Architecture** framework built with Python Flask.  
All services run on `localhost` only — **zero inbound ports exposed**. Every request flows through an overlay proxy (Edge Router) that enforces policy, terminates mTLS and routes traffic inside a dark network.

---

##  Core concept

Traditional ZTA gateways listen on open ports. This framework inverts the model:

- All services bind to **127.0.0.1** only  
- A single **Edge Router** proxies every request  
- Services never know each other’s network address  
- The overlay network is invisible to port scanners  

You get **true zero trust** without changing your application code — just wrap existing Flask apps with an Edge Router.

---

##  Components


**Edge Router** | 9999 (HTTPS) | Overlay proxy, policy enforcer, single entry point 
**Gateway** | 5000 (HTTPS) | JWT authentication, user sessions, admin endpoints 
**API Server** | 5001 (HTTPS) | Business logic, document encryption, access control 
**Controller** | 8080 (HTTP) | Policy Decision Point (PDP), identity enrollment 

---

## 🇧🇩 Bangladesh government context

The framework implements real‑world clearance and department rules:

- Clearance hierarchy: **BASIC → CONFIDENTIAL → SECRET → TOP_SECRET**  
- Department isolation: users see only their department’s documents + General documents  
- TOP_SECRET documents: **business hours only** (08:00 – 16:00 BST)  
- JWT access token (8h) + refresh token (7d)  

---

##  End‑to‑end encryption (same as Framework 1)

Documents are encrypted at rest with **AES‑256‑GCM**. The AES key is wrapped with the user’s **RSA‑2048** public key. Decryption happens exclusively in the browser using the user’s private key. The server never sees plaintext content.

For the demo, we use **base64 simulation** of AES+RSA — the same architecture as the production implementation.

---

##  Quick start

### 1. Clone & environment
```bash
git clone https://github.com/yourusername/ZTA-Overlay-Framework.git
cd ZTA-Overlay-Framework
python -m venv venv
source venv/bin/activate      # or venv\Scripts\activate (Windows)
pip install -r requirements.txt
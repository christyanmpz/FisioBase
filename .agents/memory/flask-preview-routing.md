---
name: Flask preview routing
description: Replit artifact workflows route the preview through the registered artifact service.
---

The Flask app must be registered as the web-facing service at the root preview path, and artifact workflow commands run from the artifact directory. Root-level Flask entrypoints therefore need a relative path such as `../../app.py` in the service command.

**Why:** A standalone workflow can show a healthy local port while the preview domain still returns the router's 404 page when no registered artifact owns `/`.

**How to apply:** When serving a root-level Flask app through an existing artifact service, keep the service path and preview path at `/`, match `localPort` and `PORT`, and use the correct relative entrypoint from the artifact working directory.
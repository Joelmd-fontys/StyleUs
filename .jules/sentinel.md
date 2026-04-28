## 2026-04-28 - [Tightening API Response Security with Standard Headers]
**Vulnerability:** Lack of essential security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`) on API responses.
**Learning:** Even if an API is primarily used by a specific frontend, failing to provide security headers exposes the service to standard web attacks like clickjacking and MIME-sniffing when accessed directly via a browser.
**Prevention:** Always implement a security header middleware or configuration at the application level as a baseline defense-in-depth measure, regardless of the expected client.

from __future__ import annotations


def test_security_headers(client):
    response = client.get("/health")
    assert response.status_code == 200

    # Check for security headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

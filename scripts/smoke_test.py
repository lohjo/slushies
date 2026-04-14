#!/usr/bin/env python3
"""
Production smoke test.

Checks endpoints:
- /login
- /dashboard
- /api/sync
- /api/export/csv
- /webhook/form-submit

Exit code:
- 0 when all checks pass
- 1 when any check fails
"""

import argparse
import sys
from dataclasses import dataclass

import requests


@dataclass
class SmokeContext:
    base_url: str
    email: str
    password: str


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def check_login_page(ctx: SmokeContext, session: requests.Session):
    response = session.get(f"{ctx.base_url}/login", timeout=20)
    _assert(response.status_code == 200, f"/login expected 200, got {response.status_code}")


def check_login_and_dashboard(ctx: SmokeContext, session: requests.Session):
    response = session.post(
        f"{ctx.base_url}/login",
        data={"email": ctx.email, "password": ctx.password},
        allow_redirects=True,
        timeout=20,
    )
    _assert(response.status_code == 200, f"POST /login expected 200 after redirects, got {response.status_code}")

    dashboard = session.get(f"{ctx.base_url}/dashboard", timeout=20)
    _assert(dashboard.status_code == 200, f"/dashboard expected 200, got {dashboard.status_code}")


def check_sync(ctx: SmokeContext, session: requests.Session):
    response = session.post(f"{ctx.base_url}/api/sync", timeout=60)
    _assert(response.status_code == 200, f"/api/sync expected 200, got {response.status_code}")
    payload = response.json()
    _assert("total" in payload, "/api/sync payload missing 'total'")


def check_export_csv(ctx: SmokeContext, session: requests.Session):
    response = session.get(f"{ctx.base_url}/api/export/csv", timeout=20)
    _assert(response.status_code == 200, f"/api/export/csv expected 200, got {response.status_code}")
    content_type = response.headers.get("Content-Type", "")
    _assert("text/csv" in content_type, f"/api/export/csv expected text/csv, got {content_type}")


def check_webhook(ctx: SmokeContext):
    # Intentional unauthenticated request: should fail closed with 401.
    session = requests.Session()
    response = session.post(
        f"{ctx.base_url}/webhook/form-submit",
        json={"row_index": 9999, "values": []},
        timeout=20,
    )
    _assert(response.status_code == 401, f"/webhook/form-submit expected 401 without secret, got {response.status_code}")


def run(ctx: SmokeContext) -> int:
    checks = [
        ("GET /login", lambda s: check_login_page(ctx, s)),
        ("Auth + GET /dashboard", lambda s: check_login_and_dashboard(ctx, s)),
        ("POST /api/sync", lambda s: check_sync(ctx, s)),
        ("GET /api/export/csv", lambda s: check_export_csv(ctx, s)),
    ]

    failures = 0
    session = requests.Session()

    for name, check in checks:
        try:
            check(session)
            print(f"PASS {name}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")

    try:
        check_webhook(ctx)
        print("PASS POST /webhook/form-submit")
    except Exception as exc:
        failures += 1
        print(f"FAIL POST /webhook/form-submit: {exc}")

    if failures:
        print(f"Smoke test failed: {failures} check(s)")
        return 1

    print("Smoke test passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run production smoke test")
    parser.add_argument("--url", required=True, help="Base URL, e.g. https://app.example.com")
    parser.add_argument("--email", required=True, help="Login email")
    parser.add_argument("--password", required=True, help="Login password")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    context = SmokeContext(
        base_url=args.url.rstrip("/"),
        email=args.email,
        password=args.password,
    )
    sys.exit(run(context))

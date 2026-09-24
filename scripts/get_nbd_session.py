#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Authenticate against the NBD API using the Google auth flow and print the session cookies."
    )
    parser.add_argument(
        "--google-id-token",
        required=True,
        help="Google ID token obtained from the browser's Google Sign-In flow.",
    )
    parser.add_argument(
        "--api-url",
        default="https://nbd.akvo.org/api",
        help="Base URL for the NBD API.",
    )
    parser.add_argument(
        "--email",
        help="Optional email value for display only. The API does not accept email for auth; it expects the Google ID token.",
    )
    parser.add_argument(
        "--save-cookies",
        action="store_true",
        help="Save the returned session cookies to a local JSON file.",
    )
    parser.add_argument(
        "--cookie-file",
        default=".nbd_session.json",
        help="Path to write saved cookies JSON when --save-cookies is used.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.email:
        print(f"Email provided for reference: {args.email}")
        print("Note: the API auth endpoint expects a Google ID token, not the email itself.")

    endpoint = f"{args.api_url.rstrip('/')}/api/v1/auth/google"

    response = requests.post(
        endpoint,
        json={"token": args.google_id_token},
        timeout=30,
        allow_redirects=False,
    )

    print(f"\nRequest URL: {endpoint}")
    print(f"HTTP Status: {response.status_code}")
    print("Response body:")
    print(response.text or "(empty response body)")

    print("\nSet-Cookie headers:")
    cookie_headers = response.headers.get_list("Set-Cookie")
    if cookie_headers:
        for header in cookie_headers:
            print(f"  {header}")
    else:
        print("  (no Set-Cookie headers returned)")

    if response.cookies:
        print("\nParsed cookies:")
        for name, value in response.cookies.items():
            print(f"  {name}={value}")

    if args.save_cookies:
        cookie_path = Path(args.cookie_file)
        cookie_path.write_text(json.dumps(dict(response.cookies), indent=2), encoding="utf-8")
        print(f"\nSaved cookies to: {cookie_path}")


if __name__ == "__main__":
    main()

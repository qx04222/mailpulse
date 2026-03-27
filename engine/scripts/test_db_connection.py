"""
Test Supabase database connection via REST API (no SDK dependency).

Usage:
    python scripts/test_db_connection.py
    SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python scripts/test_db_connection.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

# Try loading .env file manually
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.")
        print("Set them in engine/.env or as environment variables.")
        sys.exit(1)

    # Supabase REST endpoint: GET /rest/v1/companies?select=id&limit=1
    rest_url = f"{url}/rest/v1/companies?select=id&limit=1"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "count=exact",
    }

    print(f"Connecting to: {url}")
    try:
        req = urllib.request.Request(rest_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            content_range = resp.headers.get("Content-Range", "")
            # Content-Range looks like "0-0/5" or "*/0"
            if "/" in content_range:
                total = content_range.split("/")[-1]
            else:
                total = str(len(data))
            print(f"SUCCESS: Connected! companies table has {total} record(s).")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"FAILED (HTTP {e.code}): {body}")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

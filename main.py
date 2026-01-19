# data = METHOD + "\n" + CONTENT_TYPE + "\n" + DATE + "\n" + ENDPOINT
# digest = base64(HMAC_SHA256(private_key, data))
#!/usr/bin/env python3
"""
Export all items from Luigi's Box catalog to a CSV file using Content Export API.

Docs:
- Content export: https://docs.luigisbox.com/indexing/api/v1/export.html
- Authentication / HMAC: https://docs.luigisbox.com/api_principles.html#authentication
"""

import base64
import csv
import datetime as dt
import hashlib
import hmac
import json
import os
from urllib.parse import urlparse, parse_qs
from email.utils import format_datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode, urlparse

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =======================
# CONFIG – EDIT THESE
# =======================
# Public key (tracker_id) and private key from Luigi's Box app loaded from .env
PUBLIC_KEY = os.getenv("TRACKER_ID")
PRIVATE_KEY = os.getenv("API_KEY")

# Optional: restrict which fields are returned for each object.
# If empty, all fields will be returned.
HIT_FIELDS: List[str] = [
    "title",
    "web_url",
]

# Optional: restrict which types are returned.
# If empty, all types except "query" will be returned.
REQUESTED_TYPES: List[str] = [
    "serie",
]

# =======================
# CONFIG END
# =======================

# Page size (max according to docs is 500)
PAGE_SIZE = 500

# Output CSV filename
OUTPUT_CSV = "catalog/luigisbox_catalog_export.csv"

# Base URL of Luigi's Box API
BASE_URL = "https://live.luigisbox.com"


# =======================
# HMAC AUTH HELPERS
# =======================

CONTENT_TYPE = "application/json; charset=utf-8"


def compute_digest(
    private_key: str,
    method: str,
    endpoint: str,
    date_str: str,
    content_type: str = CONTENT_TYPE,
) -> str:
    """
    Compute HMAC digest as described in Luigi's Box docs:
      data = METHOD + "\n" + CONTENT_TYPE + "\n" + DATE + "\n" + ENDPOINT
      digest = base64( HMAC_SHA256(private_key, data) )
    """
    data = f"{method}\n{content_type}\n{date_str}\n{endpoint}"
    signature = hmac.new(
        private_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(signature).decode("ascii").strip()


def build_signed_headers(full_url: str, method: str = "GET") -> Dict[str, str]:
    """
    Build headers for an authenticated request.

    `endpoint` for the signature is the path WITHOUT query part,
    e.g. '/v1/content_export'
    """
    parsed = urlparse(full_url)
    endpoint = parsed.path  # IMPORTANT: no query string here

    now_utc = dt.datetime.now(dt.timezone.utc)
    date_str = format_datetime(now_utc)  # RFC 7231 / HTTP-date

    digest = compute_digest(PRIVATE_KEY, method, endpoint, date_str)

    headers = {
        "Content-Type": CONTENT_TYPE,
        "Date": date_str,
        "Authorization": f"ApiAuth {PUBLIC_KEY}:{digest}",
        "Accept-Encoding": "gzip, deflate",
    }
    return headers


# =======================
# EXPORT / PAGINATION
# =======================


def build_first_page_url() -> str:
    """
    Build URL for the first /v1/content_export request with query parameters.
    """
    params = {}

    if PAGE_SIZE:
        params["size"] = PAGE_SIZE

    if HIT_FIELDS:
        # docs: comma-separated list of fields
        params["hit_fields"] = ",".join(HIT_FIELDS)

    if REQUESTED_TYPES:
        # docs: comma-separated list of types
        params["requested_types"] = ",".join(REQUESTED_TYPES)

    endpoint = "/v1/content_export"
    if params:
        query = urlencode(params)
        endpoint = f"{endpoint}?{query}"

    return f"{BASE_URL}{endpoint}"


def request_json(url: str) -> Dict[str, Any]:
    headers = build_signed_headers(url, method="GET")
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        print("Status:", resp.status_code)
        print("Body:", resp.text)
    resp.raise_for_status()
    return resp.json()


def iterate_all_objects() -> List[Dict[str, Any]]:
    """
    Fetch all objects by following `links[rel=='next']` until exhausted.

    Luigi's Box peculiarity:
    - `links[rel='next'].href` can stay the SAME for multiple pages.
    - When there is nothing more to fetch, API returns:
        { "total": null, "objects": [], "links": [] }
      i.e. no `next` link at all.

    So we:
    - Ignore cursor repetition completely.
    - Stop only when there is no `next` link in the response.
    """
    objects: List[Dict[str, Any]] = []

    url: Optional[str] = build_first_page_url()

    while url:
        print(f"Fetching page: {url}")
        data = request_json(url)

        page_objects = data.get("objects", []) or []
        print(f"  -> got {len(page_objects)} objects on this page")
        objects.extend(page_objects)

        # find `next` link if present
        next_link = None
        for link in data.get("links", []) or []:
            if link.get("rel") == "next":
                next_link = link.get("href")
                break

        if not next_link:
            print("No `next` link in response, done.")
            break

        # API may return the same link repeatedly; that's fine,
        # we just keep calling it until it finally disappears.
        url = next_link

    print(f"Total objects fetched: {len(objects)}")
    return objects


# =======================
# CSV EXPORT
# =======================


def collect_attribute_keys(objects: List[Dict[str, Any]]) -> List[str]:
    """
    Collect all attribute keys present in the `attributes` dict across all objects.
    """
    keys = set()
    for obj in objects:
        attrs = obj.get("attributes") or {}
        keys.update(attrs.keys())
    return sorted(keys)


def write_objects_to_csv(objects: List[Dict[str, Any]], output_path: str) -> None:
    """
    Flatten Luigi's Box objects into a CSV:
      columns: url, type, exact, <all attribute keys>, nested

    - attributes.* values that are lists/dicts are JSON-dumped
    - nested is stored as JSON
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    attr_keys = collect_attribute_keys(objects)

    fieldnames = ["url", "type", "exact"] + attr_keys + ["nested"]

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for obj in objects:
            row: Dict[str, Any] = {k: "" for k in fieldnames}

            row["url"] = obj.get("url", "")
            row["type"] = obj.get("type", "")
            row["exact"] = obj.get("exact", "")

            attrs = obj.get("attributes") or {}
            for key in attr_keys:
                value = attrs.get(key)
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    row[key] = value

            # nested structures as JSON
            row["nested"] = json.dumps(obj.get("nested", []), ensure_ascii=False)

            writer.writerow(row)

    print(f"CSV written to: {output_path}")


# =======================
# MAIN
# =======================


def export_catalog() -> None:
    if not PUBLIC_KEY or PUBLIC_KEY.startswith("<"):
        raise RuntimeError("Please set PUBLIC_KEY at the top of the script.")
    if not PRIVATE_KEY or PRIVATE_KEY.startswith("<"):
        raise RuntimeError("Please set PRIVATE_KEY at the top of the script.")

    objects = iterate_all_objects()
    write_objects_to_csv(objects, OUTPUT_CSV)


if __name__ == "__main__":
    export_catalog()

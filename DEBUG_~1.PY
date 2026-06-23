"""
Debug script for download flow.
Run on Windows with a fresh BTSP_SESSION.

Usage:
  set BTSP_SESSION=JSESSIONID=<your_value>
  python debug_download.py TS26501G
"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(__file__))

TICKET_ID = sys.argv[1] if len(sys.argv) > 1 else "TS26501G"

import btsp_client as btsp

BASE_URL = "https://btsp.samsunggsbn.com/b2t"

print("\n=== STEP 1: get_ticket (metadata + comments) ===")
ticket = btsp.get_ticket(TICKET_ID)
comments = ticket.get("comments", [])
print("  title:", ticket.get("title", ""))
print("  comments:", len(comments))
print("  total_attachments:", ticket.get("total_attachments", 0))

all_atts = []
for c in comments:
    for a in c.get("attachments", []):
        all_atts.append((c, a))

if not all_atts:
    print("\n  NO attachments found.")
    sys.exit(0)

print("\n  Found %d attachment(s):" % len(all_atts))
for c, a in all_atts[:5]:
    print("    %s | %s | file=%s" % (a["comment_id"], a["obs_file_id"], a["filename"]))

c, a = all_atts[0]
print("\n=== STEP 2 + 3: downloadInfo then IMMEDIATELY download ===")
print("  Target file:", a["filename"])
print("  (Calling downloadInfo -- PAR expires in 2 seconds, downloading immediately...)")

session = btsp._build_session()

# Call downloadInfo
resp = session.post(
    BASE_URL + "/ts/objectStorage.do",
    params={"method": "downloadInfo"},
    data={
        "seqId":     a["comment_id"],
        "obsFileId": a["obs_file_id"],
        "obsNo":     a["obs_no"],
        "preFix":    "TICKET",
    },
    timeout=10,
)

if resp.status_code != 200:
    print("  downloadInfo FAILED: HTTP", resp.status_code)
    print("  Body:", resp.text[:300])
    sys.exit(1)

js = resp.json()
r = js.get("result", {})
namespace  = r.get("namespaceName", "")
region     = r.get("regionUri", "")
access_uri = r.get("parAccessUri", "")

if not (namespace and region and access_uri):
    print("  Missing URL fields in response:")
    print("    namespaceName:", repr(namespace))
    print("    regionUri    :", repr(region))
    print("    parAccessUri :", repr(access_uri))
    sys.exit(1)

dl_url = "https://%s.objectstorage.%s.oci.customer-oci.com%s" % (namespace, region, access_uri)
print("  Constructed URL:", dl_url[:100], "...")

# Download immediately (within 2 second window)
dest = "./%s" % a["filename"]
try:
    dr = requests.get(dl_url, timeout=30, stream=True, allow_redirects=True)
    print("  HTTP status:", dr.status_code)
    if dr.status_code == 200:
        with open(dest, "wb") as f:
            for chunk in dr.iter_content(65536):
                f.write(chunk)
        size = os.path.getsize(dest)
        print("  SAVED: %s (%d bytes)" % (dest, size))
    else:
        print("  Direct GET failed, trying with BTSP cookie...")
        dr2 = session.get(dl_url, timeout=30, stream=True, allow_redirects=True)
        print("  HTTP status with cookie:", dr2.status_code)
        if dr2.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in dr2.iter_content(65536):
                    f.write(chunk)
            size = os.path.getsize(dest)
            print("  SAVED with cookie: %s (%d bytes)" % (dest, size))
        else:
            print("  Both failed.")
            print("  Response:", dr2.text[:300])
except Exception as e:
    print("  Exception:", e)

print("\n=== STEP 4: Print downloadInfo response (for reference) ===")
print(json.dumps(js, indent=2))

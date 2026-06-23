"""
BTSP HTTP Client — JSON API + HTML detail parser
--------------------------------------------------
Two-layer approach:
  1. JSON API (ticketSearch.do) — fast ticket metadata, search, listing
  2. HTML parse (ticketNwS.do)  — full ticket detail: comments + file attachments

Confirmed endpoints:
  POST /ts/ticketSearch.do?method=getTicketSearchList   → ticket list / search
  GET  /ts/ticketNwS.do?method=getMgrTicketModifyProblemPage  → full ticket HTML
  POST /ts/objectStorage.do?method=downloadInfo         → OCI pre-auth download URL

Auth: JSESSIONID cookie in BTSP_SESSION env var (set once after Chrome login + MFA).
"""

import os
import re
import json
import time
import requests
from pathlib import Path

BASE_URL = "https://btsp.samsunggsbn.com/b2t"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL + "/ts/ticketSearch.do?method=page",
}

# Mock mode — set BTSP_MOCK=true to run without network/VPN
MOCK_MODE = os.environ.get("BTSP_MOCK", "").lower() in ("1", "true", "yes")


# ─── Session ──────────────────────────────────────────────────────────────────

def _build_session() -> requests.Session:
    raw = os.environ.get("BTSP_SESSION", "").strip()
    if not raw:
        raise EnvironmentError(
            "BTSP_SESSION is not set.\n"
            "In Cline MCP config add:  \"BTSP_SESSION\": \"JSESSIONID=<value>\""
        )
    session = requests.Session()
    session.headers.update(HEADERS)
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, value = part.split("=", 1)
            session.cookies.set(name.strip(), value.strip(),
                                domain="btsp.samsunggsbn.com")
    return session


def _check_auth(resp: requests.Response):
    """Raise if the response is a login redirect."""
    if "loginMain" in resp.url or resp.status_code == 403:
        raise PermissionError(
            "BTSP session expired. Log in to Chrome again, copy a fresh "
            "JSESSIONID from DevTools, and update BTSP_SESSION."
        )


# ─── Core API calls ───────────────────────────────────────────────────────────

def _post_json(path: str, params: dict = None, data: dict = None) -> dict:
    """POST to a BTSP JSON endpoint, return parsed response."""
    if MOCK_MODE:
        import mock_data
        return mock_data.mock_api_response(path, params, data)

    session = _build_session()
    url = BASE_URL + path
    resp = session.post(url, params=params, data=data, timeout=15)
    _check_auth(resp)
    resp.raise_for_status()
    return resp.json()


def _get_html(path: str, params: dict = None) -> str:
    """GET a BTSP page, return raw HTML."""
    if MOCK_MODE:
        import mock_data
        return mock_data.mock_html_response(path, params)

    session = _build_session()
    # Ticket detail page returns HTML — override Accept header
    html_headers = dict(HEADERS)
    html_headers["Accept"] = "text/html,application/xhtml+xml,*/*"
    html_headers.pop("X-Requested-With", None)
    session.headers.update(html_headers)

    url = BASE_URL + path
    resp = session.get(url, params=params, timeout=20)
    _check_auth(resp)
    resp.raise_for_status()
    return resp.text


# ─── Field mapping from confirmed JSON response ────────────────────────────────

def _map_ticket(row: dict) -> dict:
    """Map raw API row to a clean ticket dict using confirmed field names."""
    return {
        "ticket_id":      row.get("ticketNo", ""),
        "title":          row.get("title", ""),
        "status":         row.get("ticketStatusNm", ""),
        "request_type":   row.get("reqTypeNm", ""),
        "country":        row.get("countryCd", ""),
        "current_owner":  row.get("currentOwner", ""),
        "agent_group":    row.get("agentGrpNm", ""),
        "submitted_by":   row.get("sbmtUserNm", ""),
        "submitted_at":   row.get("sbmtDttm", ""),
        "last_updated":   row.get("lastUpdateDttm", ""),
        "sla_due":        row.get("slaDueDttm", ""),
        "close_date":     row.get("closeDate", ""),
        "business_unit":  row.get("bizUnitCd", ""),
        "product": " / ".join(filter(None, [
            row.get("productCtgry1Nm"),
            row.get("productCtgry2Nm"),
            row.get("productCtgry3Nm"),
            row.get("productCtgry4Nm"),
        ])),
        "system_impact":  row.get("sysImpactNm", ""),
        "related_ticket": row.get("relatedTicketNo", ""),
        "contact_email":  row.get("emailAddr", ""),
        "site":           row.get("siteNm", ""),
        "ticket_enc":     row.get("ticketNoEnc", ""),
    }


# ─── Profile loader ───────────────────────────────────────────────────────────

def _load_profile() -> dict:
    """Load user profile params from btsp_profile.json (same dir as this file)."""
    profile_path = os.path.join(os.path.dirname(__file__), "btsp_profile.json")
    if not os.path.exists(profile_path):
        raise FileNotFoundError(
            "btsp_profile.json not found. "
            "Copy it next to btsp_client.py and fill in your profile values."
        )
    with open(profile_path, encoding="utf-8") as f:
        return json.load(f)


# ─── Search params builder ────────────────────────────────────────────────────

def _search_params(ticket_id: str = None, free_text: str = None,
                   status: str = None, page: int = 1) -> dict:
    """Build POST body for getTicketSearchList using confirmed payload structure."""
    from datetime import datetime
    p = _load_profile()
    today = datetime.now().strftime("%m/%d/%Y")

    data = {
        "page":   str(page),
        "punit":  p.get("punit", "15"),
        "sidx":   p.get("sidx", "SBMT_DTTM"),
        "sort":   p.get("sort", "desc"),
        "searchDtType":       p.get("searchDtType", "C"),
        "searchSubCounType":  p.get("searchSubCounType", "S"),
        "rSearchSubCounType": p.get("rSearchSubCounType", "S"),
        "dateSearchYn":       p.get("dateSearchYn", "N"),
        "range":              p.get("range", "365"),
        "dtStart":            today,
        "dtEnd":              today,
        "bizUnitCd":    p.get("bizUnitCd", ""),
        "secorgId":     p.get("secorgId", ""),
        "accountIds":   p.get("accountIds", ""),
        "ticketStatusCds": p.get("ticketStatusCds", "10,20,30,40,50,60"),
        "reqTypeCd":  "",
        "countryCd":  "",
        "countryCds": "",
        "accountId":  "",
    }

    for v in p.get("ticketStatusCdMulti", ["10","20","30","40","50","60"]):
        data.setdefault("ticketStatusCdMulti", [])
        if isinstance(data["ticketStatusCdMulti"], list):
            data["ticketStatusCdMulti"].append(v)

    for v in p.get("secorgIdMulti", []):
        data.setdefault("secorgIdMulti", [])
        if isinstance(data["secorgIdMulti"], list):
            data["secorgIdMulti"].append(v)

    for v in p.get("accountIdMulti", []):
        data.setdefault("accountIdMulti", [])
        if isinstance(data["accountIdMulti"], list):
            data["accountIdMulti"].append(v)

    if ticket_id:
        data["txtSearchField"] = "ticketId"
        data["txtSearchData"]  = ticket_id
    elif free_text:
        data["txtSearchField"] = "title"
        data["txtSearchData"]  = free_text
    else:
        data["txtSearchField"] = ""
        data["txtSearchData"]  = ""

    if status and status.lower() == "open":
        data["ticketStatusCdMulti"] = ["10","20","30","40"]
        data["ticketStatusCds"] = "10,20,30,40"
    elif status and status.lower() == "closed":
        data["ticketStatusCdMulti"] = ["50","60"]
        data["ticketStatusCds"] = "50,60"

    return data


# ─── HTML detail parser ───────────────────────────────────────────────────────

def _parse_ticket_detail(html: str) -> dict:
    """
    Parse ticketNwS.do HTML to extract:
      - title (span.con_title1)
      - comments (div.comment_wrap): author, date, body, attachments
      - attachments: commentId, obsFileId, obsNo, filename
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # ── Title ──────────────────────────────────────────────────────────────────
    title_el = soup.find("span", class_="con_title1")
    title = title_el.get_text(strip=True) if title_el else ""

    ticket_num_el = soup.find("span", class_="ticket_num")
    ticket_num = ticket_num_el.get_text(strip=True).lstrip("#") if ticket_num_el else ""

    # ── Comments ───────────────────────────────────────────────────────────────
    comments = []
    for wrap in soup.find_all("div", class_="comment_wrap"):

        # Author: first significant text in dt.name
        author = ""
        name_el = wrap.find("dt", class_="name")
        if name_el:
            # Remove nested divs (user info popup), take first text
            for nested in name_el.find_all("div"):
                nested.decompose()
            author = name_el.get_text(" ", strip=True)
            author = re.sub(r"\s+", " ", author).strip()

        # Date: dd.date
        date_el = wrap.find("dd", class_="date")
        date = date_el.get_text(strip=True) if date_el else ""

        # Body: div.comm_txt
        body_el = wrap.find("div", class_="comm_txt")
        body = body_el.get_text("\n", strip=True) if body_el else ""

        # Files: <a href="javascript:downloadObs('CMT...','OBS...','N');">filename</a>
        attachments = []
        for link in wrap.find_all("a", href=re.compile(r"downloadObs")):
            href = link.get("href", "")
            m = re.search(
                r"downloadObs\('([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\)",
                href
            )
            if m:
                attachments.append({
                    "comment_id": m.group(1),
                    "obs_file_id": m.group(2),
                    "obs_no": m.group(3),
                    "filename": link.get_text(strip=True),
                })

        if author or body or attachments:
            comments.append({
                "author": author,
                "date": date,
                "body": body,
                "attachments": attachments,
            })

    return {
        "ticket_id": ticket_num,
        "title": title,
        "comments": comments,
        "total_comments": len(comments),
        "total_attachments": sum(len(c["attachments"]) for c in comments),
    }


# --- Download helper ---------------------------------------------------------

def _resolve_download_url(comment_id, obs_file_id, obs_no):
    """
    Call downloadInfo and build the OCI PAR download URL.

    The response contains:
      result.namespaceName  e.g. "cncdwkxfqewh"
      result.regionUri      e.g. "ap-seoul-1"
      result.parAccessUri   e.g. "/p/<token>/n/<ns>/b/<bucket>/o/<path>"

    Full URL = https://{namespaceName}.objectstorage.{regionUri}.oci.customer-oci.com{parAccessUri}
    """
    resp_data = _post_json(
        "/ts/objectStorage.do",
        params={"method": "downloadInfo"},
        data={
            "seqId":     comment_id,
            "obsFileId": obs_file_id,
            "obsNo":     obs_no,
            "preFix":    "TICKET",
        },
    )
    r = resp_data.get("result", {})
    namespace   = r.get("namespaceName", "")
    region      = r.get("regionUri", "")
    access_uri  = r.get("parAccessUri", "")

    if not (namespace and region and access_uri):
        raise ValueError(
            "downloadInfo missing fields for %s/%s. Got: namespace=%r region=%r uri=%r"
            % (obs_file_id, obs_no, namespace, region, access_uri)
        )

    url = "https://%s.objectstorage.%s.oci.customer-oci.com%s" % (namespace, region, access_uri)
    return url


def _download_file(url, dest_path):
    """Download from OCI PAR URL. Tries direct GET first; falls back to BTSP session cookie."""
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    # Attempt 1: direct GET (OCI PAR URLs are usually public pre-signed)
    resp = requests.get(url, timeout=60, stream=True, allow_redirects=True)
    if resp.status_code in (401, 403):
        # Attempt 2: BTSP may proxy OCI through JEUS -- send session cookie
        resp = _build_session().get(url, timeout=60, stream=True, allow_redirects=True)
    resp.raise_for_status()
    size = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            size += len(chunk)
    return size


# --- Public API --------------------------------------------------------------

def get_ticket(ticket_id):
    """Fetch full ticket: metadata from JSON API + comments/attachments from HTML."""
    result = _post_json(
        "/ts/ticketSearch.do",
        params={"method": "getTicketSearchList"},
        data=_search_params(ticket_id=ticket_id),
    )
    rows = result.get("rows", [])
    if not rows:
        raise ValueError("Ticket %s not found. Check the ID and session." % ticket_id)

    metadata = _map_ticket(rows[0])
    ticket_enc = metadata.get("ticket_enc", "")

    detail = {}
    if ticket_enc and not MOCK_MODE:
        try:
            html = _get_html(
                "/ts/ticketNwS.do",
                params={
                    "method": "getMgrTicketModifyProblemPage",
                    "bizUnitCd": "G3",
                    "reqTypeCd": "01",
                    "ticketNo": ticket_enc,
                },
            )
            detail = _parse_ticket_detail(html)
        except Exception as e:
            detail = {"detail_error": str(e)}
    elif MOCK_MODE:
        import mock_data
        detail = mock_data.mock_ticket_detail(ticket_id)

    merged = dict(metadata)
    merged["comments"] = detail.get("comments", [])
    merged["total_comments"] = detail.get("total_comments", 0)
    merged["total_attachments"] = detail.get("total_attachments", 0)
    if "detail_error" in detail:
        merged["detail_error"] = detail["detail_error"]
    return merged


def get_ticket_detail(ticket_enc):
    """Fetch and parse ticket detail page by encoded ticket number."""
    html = _get_html(
        "/ts/ticketNwS.do",
        params={
            "method": "getMgrTicketModifyProblemPage",
            "bizUnitCd": "G3",
            "reqTypeCd": "01",
            "ticketNo": ticket_enc,
        },
    )
    return _parse_ticket_detail(html)


def list_tickets(status="open"):
    """List tickets. status = 'open' | 'closed' | 'all'"""
    result = _post_json(
        "/ts/ticketSearch.do",
        params={"method": "getTicketSearchList"},
        data=_search_params(status=status),
    )
    return [_map_ticket(r) for r in result.get("rows", [])]


def search_tickets(query):
    """Search tickets by keyword in title/subject."""
    result = _post_json(
        "/ts/ticketSearch.do",
        params={"method": "getTicketSearchList"},
        data=_search_params(free_text=query),
    )
    return [_map_ticket(r) for r in result.get("rows", [])]


def download_logs(ticket_id, save_dir="."):
    """
    Download all file attachments for a ticket.
    Returns list of dicts: [{filename, path, size_bytes, comment_id, date}]
    """
    ticket = get_ticket(ticket_id)
    ticket_enc = ticket.get("ticket_enc", "")
    if not ticket_enc:
        raise ValueError("No ticket_enc for %s -- cannot fetch attachments." % ticket_id)

    comments = ticket.get("comments", [])
    if not comments:
        return []

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    downloaded = []
    for comment in comments:
        for att in comment.get("attachments", []):
            comment_id  = att["comment_id"]
            obs_file_id = att["obs_file_id"]
            obs_no      = att["obs_no"]
            filename    = att["filename"] or ("%s_%s" % (obs_file_id, obs_no))

            safe_name = re.sub(r'[<>:"/\\|?*]', "_", filename)
            dest = str(save_path / safe_name)

            try:
                if MOCK_MODE:
                    Path(dest).write_text("[MOCK] %s\nComment: %s\n" % (filename, comment_id))
                    size = len(filename)
                else:
                    dl_url = _resolve_download_url(comment_id, obs_file_id, obs_no)
                    size = _download_file(dl_url, dest)

                downloaded.append({
                    "filename": filename,
                    "path": dest,
                    "size_bytes": size,
                    "comment_id": comment_id,
                    "comment_date": comment.get("date", ""),
                    "comment_author": comment.get("author", ""),
                })
            except Exception as e:
                downloaded.append({
                    "filename": filename,
                    "error": str(e),
                    "comment_id": comment_id,
                })

    return downloaded


def debug_raw(path, method, extra_data=None):
    """Call any BTSP endpoint and return raw JSON -- for discovery."""
    session = _build_session()
    url = BASE_URL + path
    resp = session.post(url, params={"method": method}, data=extra_data or {}, timeout=15)
    _check_auth(resp)
    try:
        return resp.json()
    except Exception:
        return {"raw_text": resp.text[:3000]}


# --- LLM context builder -----------------------------------------------------

# File extensions we can read as text and include in LLM context
TEXT_EXTENSIONS = {".txt", ".log", ".csv", ".xml", ".json", ".cfg", ".conf",
                   ".ini", ".out", ".sh", ".py", ".yaml", ".yml"}


def get_ticket_context(ticket_id, save_dir=None, include_file_contents=True):
    """
    Collect everything about a ticket into a single dict for LLM consumption:
      - Full ticket metadata
      - All comments (author, date, body)
      - All attachments downloaded to save_dir
      - Contents of text/log files inline (if include_file_contents=True)

    Returns:
      {
        "ticket": {...},              # metadata
        "comments": [...],           # list of {author, date, body, attachments}
        "files": [...],              # list of {filename, path, size_bytes, content}
        "llm_prompt": "..."          # ready-to-use text block for LLM
      }
    """
    if save_dir is None:
        save_dir = "./btsp_logs/" + ticket_id

    # 1. Get full ticket with comments
    ticket = get_ticket(ticket_id)
    comments = ticket.get("comments", [])

    # 2. Download all attachments
    downloaded = download_logs(ticket_id, save_dir)

    # 3. Read text files inline
    files_with_content = []
    for f in downloaded:
        entry = dict(f)
        if include_file_contents and "path" in f and "error" not in f:
            ext = Path(f["path"]).suffix.lower()
            if ext in TEXT_EXTENSIONS:
                try:
                    content = Path(f["path"]).read_text(encoding="utf-8", errors="replace")
                    # Cap at 50KB per file to avoid overwhelming LLM
                    if len(content) > 51200:
                        content = content[:51200] + "\n... [truncated at 50KB] ..."
                    entry["content"] = content
                except Exception as e:
                    entry["content"] = "[Could not read: %s]" % e
            else:
                entry["content"] = "[Binary file — %s, not included inline]" % ext
        files_with_content.append(entry)

    # 4. Build LLM prompt text
    lines = []
    lines.append("=" * 60)
    lines.append("BTSP TICKET: " + ticket.get("ticket_id", ""))
    lines.append("=" * 60)
    lines.append("Title       : " + ticket.get("title", ""))
    lines.append("Status      : " + ticket.get("status", ""))
    lines.append("Type        : " + ticket.get("request_type", ""))
    lines.append("Product     : " + ticket.get("product", ""))
    lines.append("Impact      : " + ticket.get("system_impact", ""))
    lines.append("Owner       : " + ticket.get("current_owner", ""))
    lines.append("Group       : " + ticket.get("agent_group", ""))
    lines.append("Submitted by: " + ticket.get("submitted_by", "")
                 + "  at  " + ticket.get("submitted_at", ""))
    lines.append("Last updated: " + ticket.get("last_updated", ""))
    lines.append("Country     : " + ticket.get("country", ""))
    lines.append("Related     : " + ticket.get("related_ticket", ""))
    lines.append("")

    # Comments
    lines.append("-" * 60)
    lines.append("DISCUSSION (%d comments)" % len(comments))
    lines.append("-" * 60)
    for i, c in enumerate(comments, 1):
        lines.append("")
        lines.append("[Comment %d]  %s  |  %s" % (i, c.get("date", ""), c.get("author", "")))
        body = c.get("body", "").strip()
        if body:
            lines.append(body)
        atts = c.get("attachments", [])
        if atts:
            lines.append("  Attached files: " + ", ".join(a["filename"] for a in atts))
    lines.append("")

    # Files
    text_files = [f for f in files_with_content if f.get("content") and not f["content"].startswith("[Binary")]
    bin_files  = [f for f in files_with_content if "content" not in f or f.get("content", "").startswith("[Binary")]

    if text_files:
        lines.append("-" * 60)
        lines.append("LOG FILES (%d text files)" % len(text_files))
        lines.append("-" * 60)
        for f in text_files:
            lines.append("")
            lines.append("### FILE: " + f["filename"] + " ###")
            lines.append(f.get("content", ""))

    if bin_files:
        lines.append("")
        lines.append("Binary/non-text files (not included inline):")
        for f in bin_files:
            lines.append("  - " + f["filename"])

    llm_prompt = "\n".join(lines)

    return {
        "ticket": ticket,
        "comments": comments,
        "files": files_with_content,
        "llm_prompt": llm_prompt,
    }


# --- Owner filter + View tickets ---------------------------------------------

def list_tickets_by_owner(owner_id, status="open"):
    """
    List tickets where the current owner matches owner_id.

    owner_id: Samsung user ID ('rajneesh.r') or partial display name ('Rajneesh').
    status:   'open' (default) | 'closed' | 'all'
              Keep 'open' — BTSP times out when fetching all statuses at once
              across a large account set. Run twice for open+closed if needed.

    Strategy: client-side filter on currentOwner display name.
    BTSP server-side txtSearchField=ticketOwner hangs (15s timeout), so we
    fetch the same scoped list that list_tickets() uses (fast) and filter here.

    Matches:
      - display name substring: 'Rajneesh' → 'Rajneesh Rana ***'
      - dot-separated user ID tokens: 'rajneesh.r' → checks 'rajneesh' in name
    """
    result = _post_json(
        "/ts/ticketSearch.do",
        params={"method": "getTicketSearchList"},
        data=_search_params(status=status),   # same fast path as list_tickets()
    )
    all_tickets = [_map_ticket(r) for r in result.get("rows", [])]

    # Normalise: split on '.' for user IDs like 'rajneesh.r'
    query_lower = owner_id.lower()
    tokens = [t for t in query_lower.split(".") if len(t) > 1]

    def _matches(owner_display):
        d = owner_display.lower()
        if query_lower in d:
            return True
        return any(tok in d for tok in tokens)

    return [t for t in all_tickets if _matches(t.get("current_owner", ""))]


def list_views():
    """
    List saved ticket views for the current user.

    Note: getTicketViewList returns 500 on this BTSP instance — the correct
    method name may differ. Returns raw response dict for inspection.
    Use get_view_tickets(view_id=...) directly if you already know the viewId.
    """
    try:
        result = _post_json(
            "/ts/ticketView.do",
            params={"method": "getTicketViewList"},
            data={},
        )
    except Exception as e:
        # Return error info instead of crashing — caller can inspect
        return [{"error": str(e), "hint": "getTicketViewList may not be supported; use debug_raw to find the correct method"}]

    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        rows = result.get("rows") or result.get("list") or result.get("data")
        if rows is not None:
            return rows
        # Return the         return [result]
    return []


def get_view_tickets(view_id=None, view_name=None):
    """
    Fetch all tickets in a saved BTSP view.

    Args:
      view_id:   viewId string, e.g. 'FV2605080001'
      view_name: viewNm string, e.g. 'Clone : Core Platform Pending Issues'

    Calls POST /ts/ticketView.do?method=getTicketView
    """
    if not view_id and not view_name:
        raise ValueError("Provide either view_id or view_name.")

    data = {}
    if view_id:
        data["viewId"] = view_id
    if view_name:
        data["viewNm"] = view_name

    result = _post_json(
        "/ts/ticketView.do",
        params={"method": "getTicketView"},
        data=data,
    )

    rows = (result.get("rows")
            or result.get("list")
            or result.get("data")
            or [])

    if rows and isinstance(rows[0], dict) and "ticketNo" in rows[0]:
        return [_map_ticket(r) for r in rows]

    return result

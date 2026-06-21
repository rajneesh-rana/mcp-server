"""
BTSP MCP Server
----------------
Exposes BTSP ticket operations as MCP tools for Cline / VS Code.

Tools:
  get_ticket(ticket_id)              -> full ticket + comments + attachments
  download_logs(ticket_id, save_dir) -> download all log attachments to disk
  list_tickets(status)               -> list open/closed/all tickets
  search_tickets(query)              -> keyword search across tickets
  debug_raw(path, method, data)      -> call any endpoint, dump raw JSON

Setup:
  1. pip install -r requirements.txt
  2. Set BTSP_SESSION env var in Cline MCP config (JSESSIONID=<value>)
  3. Register this server in cline_mcp_settings.json
"""

import json
import sys
import traceback

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

import btsp_client as btsp

app = Server("btsp-mcp")


@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="get_ticket",
            description=(
                "Fetch full details for a BTSP telecom support ticket. "
                "Returns: ticket metadata (status, owner, product, SLA), "
                "all comments with author/date/body, and list of attached log files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "BTSP ticket ID, e.g. 'TS26501G'",
                    }
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="download_logs",
            description=(
                "Download all file attachments (logs, packet captures, configs) "
                "from a BTSP ticket to a local directory. "
                "Returns the list of saved files with paths and sizes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "BTSP ticket ID",
                    },
                    "save_dir": {
                        "type": "string",
                        "description": "Directory to save files into. Default: ./btsp_logs/<ticket_id>",
                        "default": "",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
        types.Tool(
            name="list_tickets",
            description="List BTSP tickets assigned to you or your team.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by ticket status. Default: open",
                        "default": "open",
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="search_tickets",
            description="Search BTSP tickets by keyword in the title.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keyword or phrase, e.g. 'BFD alarm'",
                    }
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="debug_raw",
            description=(
                "DEVELOPER TOOL: Call any BTSP endpoint and return raw JSON. "
                "Use this to discover new API endpoints."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "URL path under /b2t/, e.g. '/ts/ticketView.do'",
                    },
                    "method": {
                        "type": "string",
                        "description": "Value of the 'method' query param",
                    },
                    "data": {
                        "type": "object",
                        "description": "Optional POST body key-value pairs",
                        "default": {},
                    },
                },
                "required": ["path", "method"],
            },
        ),
        types.Tool(
            name="list_tickets_by_owner",
            description=(
                "List BTSP tickets currently owned/assigned to a specific user. "
                "Pass their Samsung user ID (e.g. 'rajneesh.r') or partial display name (e.g. 'Rajneesh'). "
                "Uses client-side filtering on the open ticket list (fast). "
                "Set status='all' to include closed tickets (slower)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "owner_id": {
                        "type": "string",
                        "description": "Samsung user ID e.g. 'rajneesh.r', or partial display name e.g. 'Rajneesh'",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Ticket status scope. Default: open (fastest).",
                        "default": "open",
                    },
                },
                "required": ["owner_id"],
            },
        ),
        types.Tool(
            name="list_views",
            description="List all saved ticket views for the current BTSP user.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_view_tickets",
            description=(
                "Fetch all tickets in a saved BTSP view. "
                "Provide either the viewId (e.g. 'FV2605080001') or the viewNm "
                "(e.g. 'Clone : Core Platform Pending Issues')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "view_id": {
                        "type": "string",
                        "description": "View ID, e.g. FV2605080001",
                        "default": "",
                    },
                    "view_name": {
                        "type": "string",
                        "description": "View name, e.g. Clone : Core Platform Pending Issues",
                        "default": "",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_ticket_context",
            description=(
                "Fetch a BTSP ticket and prepare a complete LLM investigation context: "
                "ticket metadata, all comments/discussion, and all log file contents. "
                "Downloads attachments to disk and reads text/log files inline. "
                "Use this as the starting point for any ticket investigation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "BTSP ticket ID, e.g. TS26501G",
                    },
                    "save_dir": {
                        "type": "string",
                        "description": "Directory to save attachments. Default: ./btsp_logs/<ticket_id>",
                        "default": "",
                    },
                },
                "required": ["ticket_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name, arguments):
    try:
        if name == "get_ticket":
            ticket_id = arguments["ticket_id"].strip()
            result = btsp.get_ticket(ticket_id)
            text = _format_ticket(result)

        elif name == "download_logs":
            ticket_id = arguments["ticket_id"].strip()
            save_dir = arguments.get("save_dir", "").strip()
            if not save_dir:
                save_dir = "./btsp_logs/" + ticket_id
            files = btsp.download_logs(ticket_id, save_dir)
            if not files:
                text = "No attachments found on ticket " + ticket_id + "."
            else:
                lines = ["Downloaded %d file(s) to %s:\n" % (len(files), save_dir)]
                for f in files:
                    if "error" in f:
                        lines.append("  FAIL  " + f["filename"] + " -- " + f["error"])
                    else:
                        kb = f.get("size_bytes", 0) // 1024
                        lines.append("  OK    " + f["filename"] + " (%d KB) -> %s" % (kb, f["path"]))
                text = "\n".join(lines)

        elif name == "list_tickets":
            status = arguments.get("status", "open")
            tickets = btsp.list_tickets(status)
            if not tickets:
                text = "No " + status + " tickets found."
            else:
                lines = ["Found %d %s ticket(s):\n" % (len(tickets), status)]
                for t in tickets:
                    lines.append(
                        "  [%s] %s | %s | %s" % (
                            t["ticket_id"], t["title"][:60],
                            t["status"], t.get("current_owner", "")
                        )
                    )
                text = "\n".join(lines)

        elif name == "search_tickets":
            query = arguments["query"]
            tickets = btsp.search_tickets(query)
            if not tickets:
                text = "No tickets found matching '%s'." % query
            else:
                lines = ["Found %d ticket(s) matching '%s':\n" % (len(tickets), query)]
                for t in tickets:
                    lines.append("  [%s] %s | %s" % (t["ticket_id"], t["title"][:60], t["status"]))
                text = "\n".join(lines)

        elif name == "list_tickets_by_owner":
            owner_id = arguments["owner_id"].strip()
            status   = arguments.get("status", "open")
            tickets  = btsp.list_tickets_by_owner(owner_id, status=status)
            if not tickets:
                text = "No tickets found owned by '%s'." % owner_id
            else:
                lines = ["Found %d ticket(s) owned by %s:\n" % (len(tickets), owner_id)]
                for t in tickets:
                    lines.append("  [%s] %s | %s" % (t["ticket_id"], t["title"][:60], t["status"]))
                text = "\n".join(lines)

        elif name == "list_views":
            views = btsp.list_views()
            if not views:
                text = "No saved views found."
            elif len(views) == 1 and isinstance(views[0], dict) and "error" in views[0]:
                text = (
                    "list_views is not supported on this BTSP instance "
                    "(getTicketViewList returned an error).\n\n"
                    "Error: %s\n\n"
                    "Workaround: use get_view_tickets with a known viewId, e.g. 'FV2605080001'.\n"
                    "To discover view IDs, open BTSP in Chrome, switch to a view, "
                    "then check Network tab for getTicketView calls."
                ) % views[0].get("error", "unknown")
            else:
                lines = ["Saved views (%d):\n" % len(views)]
                for v in views:
                    if isinstance(v, dict):
                        lines.append("  [%s] %s  (%s tickets)" % (
                            v.get("viewId", "?"),
                            v.get("viewNm", "?"),
                            v.get("ticketCnt", "?"),
                        ))
                    else:
                        lines.append("  " + str(v))
                text = "\n".join(lines)

        elif name == "get_view_tickets":
            view_id   = arguments.get("view_id", "").strip()
            view_name = arguments.get("view_name", "").strip()
            result = btsp.get_view_tickets(
                view_id   = view_id   or None,
                view_name = view_name or None,
            )
            if isinstance(result, list):
                if not result:
                    text = "No tickets found in view."
                else:
                    label = view_id or view_name
                    lines = ["Tickets in view %s (%d):\n" % (label, len(result))]
                    for t in result:
                        if isinstance(t, dict) and "ticket_id" in t:
                            lines.append("  [%s] %s | %s | %s" % (
                                t["ticket_id"], t["title"][:55], t["status"], t.get("current_owner","")
                            ))
                        else:
                            lines.append("  " + str(t)[:80])
                    text = "\n".join(lines)
            else:
                # Raw response -- format as JSON for inspection
                text = "Raw response (unexpected shape):\n" + json.dumps(result, indent=2, default=str)[:3000]

        elif name == "get_ticket_context":
            ticket_id = arguments["ticket_id"].strip()
            save_dir = arguments.get("save_dir", "").strip()
            if not save_dir:
                save_dir = "./btsp_logs/" + ticket_id
            ctx = btsp.get_ticket_context(ticket_id, save_dir)
            text = ctx["llm_prompt"]
            n_files = len([f for f in ctx["files"] if "error" not in f])
            n_text  = len([f for f in ctx["files"] if f.get("content") and not f["content"].startswith("[Binary")])
            summary = (
                "\n\n[Summary: %d comment(s), %d file(s) downloaded, "
                "%d text file(s) included inline. Logs saved to: %s]"
                % (len(ctx["comments"]), n_files, n_text, save_dir)
            )
            text += summary

        elif name == "debug_raw":
            path = arguments["path"]
            method = arguments["method"]
            data = arguments.get("data", {})
            result = btsp.debug_raw(path, method, data or None)
            text = json.dumps(result, indent=2, default=str)[:6000]

        else:
            text = "Unknown tool: " + name

    except PermissionError as e:
        text = "AUTH ERROR (session expired):\n" + str(e)
    except EnvironmentError as e:
        text = "CONFIG ERROR:\n" + str(e)
    except Exception as e:
        text = "ERROR in '%s':\n%s\n\n%s" % (name, e, traceback.format_exc())

    return [types.TextContent(type="text", text=text)]


def _format_ticket(t):
    sep = "=" * 50
    lines = [
        sep,
        "  TICKET: " + t.get("ticket_id", ""),
        sep,
        "  Title       : " + t.get("title", ""),
        "  Status      : " + t.get("status", ""),
        "  Type        : " + t.get("request_type", ""),
        "  Product     : " + t.get("product", ""),
        "  System impact: " + t.get("system_impact", ""),
        "  Owner       : " + t.get("current_owner", ""),
        "  Group       : " + t.get("agent_group", ""),
        "  Submitted by: " + t.get("submitted_by", "") + "  at  " + t.get("submitted_at", ""),
        "  Last updated: " + t.get("last_updated", ""),
        "  SLA due     : " + t.get("sla_due", ""),
        "  Country     : " + t.get("country", ""),
        "  Related     : " + t.get("related_ticket", ""),
        "",
    ]

    detail_err = t.get("detail_error")
    if detail_err:
        lines.append("  [WARN] Could not load comment detail: " + detail_err)
        lines.append("")

    comments = t.get("comments", [])
    n_att = t.get("total_attachments", 0)

    if comments:
        lines.append("-- Comments (%d), Attachments (%d) " % (len(comments), n_att) + "-" * 20)
        for i, c in enumerate(comments, 1):
            lines.append("")
            lines.append("  [%d] %s  |  %s" % (i, c.get("date", ""), c.get("author", "")))
            body = c.get("body", "")
            if body:
                for line in body.split("\n"):
                    lines.append("       " + line)
            atts = c.get("attachments", [])
            if atts:
                lines.append("       Files (%d):" % len(atts))
                for a in atts:
                    lines.append("         - " + a.get("filename", ""))
        lines.append("")
    else:
        lines.append("  (No comments loaded)")
        lines.append("")

    return "\n".join(lines)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

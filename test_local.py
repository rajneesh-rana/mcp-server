"""
Local test script for BTSP MCP server.

Usage:
    # Mock mode - no network needed
    python test_local.py

    # Live mode - real BTSP site
    set BTSP_SESSION=JSESSIONID=<your_value>
    python test_local.py --live TS26501G

    # Download mode - also download attachments
    python test_local.py --live TS26501G --download
"""

import os
import sys
import json

LIVE_MODE = "--live" in sys.argv
DOWNLOAD_MODE = "--download" in sys.argv

if not LIVE_MODE:
    os.environ["BTSP_MOCK"] = "true"
    TICKET_ID = "TS26501G"
else:
    idx = sys.argv.index("--live")
    TICKET_ID = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "TS26501G"

import btsp_client as btsp

SEP = "-" * 60


def run_test(label, fn, *args, **kwargs):
    print("\n" + SEP)
    print("  TEST: " + label)
    print(SEP)
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            comments = result.pop("comments", [])
            print(json.dumps(result, indent=2, default=str))
            if comments:
                print("\n  --- Comments (%d) ---" % len(comments))
                for i, c in enumerate(comments[:3], 1):
                    atts = c.get("attachments", [])
                    author = c.get("author", "")[:40]
                    date = c.get("date", "")
                    body = c.get("body", "").replace("\n", " ")[:100]
                    print("  [%d] %s | %s" % (i, date, author))
                    print("       " + body)
                    if atts:
                        names = [a["filename"] for a in atts]
                        print("       Files: " + str(names))
                if len(comments) > 3:
                    print("  ... and %d more comments" % (len(comments) - 3))
            result["comments"] = comments
        elif isinstance(result, list):
            print("  [%d items]" % len(result))
            for item in result[:3]:
                if isinstance(item, dict):
                    if "ticket_id" in item:
                        print("  - %s | %s | %s" % (
                            item.get("ticket_id", "?"),
                            item.get("title", "?")[:55],
                            item.get("status", "?"),
                        ))
                    elif "viewId" in item:
                        print("  - [%s] %s (%s tickets)" % (
                            item.get("viewId", "?"),
                            item.get("viewNm", "?")[:45],
                            item.get("ticketCnt", "?"),
                        ))
                    else:
                        print("  - " + str(item)[:80])
                else:
                    print("  - " + str(item)[:80])
            if len(result) > 3:
                print("  ... and %d more" % (len(result) - 3))
        else:
            print(result)
        print("  PASSED")
        return result
    except Exception as e:
        print("  FAILED: " + str(e))
        import traceback
        traceback.print_exc()
        return None


def main():
    mode = "MOCK" if not LIVE_MODE else ("LIVE (ticket: " + TICKET_ID + ")")
    print("\n" + "=" * 60)
    print("  BTSP MCP Server - Local Test  [" + mode + "]")
    print("=" * 60)

    run_test("list_tickets(status='open')", btsp.list_tickets, "open")
    run_test("search_tickets('BFD')", btsp.search_tickets, "BFD")

    ticket = run_test(
        "get_ticket('%s') -- full detail with comments" % TICKET_ID,
        btsp.get_ticket,
        TICKET_ID,
    )

    run_test("list_tickets_by_owner('rajneesh.r')", btsp.list_tickets_by_owner, "rajneesh.r")
    run_test("list_views()", btsp.list_views)
    run_test("get_view_tickets(view_id='FV2605080001')", btsp.get_view_tickets, view_id="FV2605080001")

    if DOWNLOAD_MODE and LIVE_MODE:
        run_test(
            "download_logs('%s')" % TICKET_ID,
            btsp.download_logs,
            TICKET_ID,
            "./btsp_logs/" + TICKET_ID,
        )
    elif not LIVE_MODE:
        run_test(
            "download_logs('%s') [mock]" % TICKET_ID,
            btsp.download_logs,
            TICKET_ID,
            "./btsp_logs_mock/" + TICKET_ID,
        )
    else:
        print("\n" + SEP)
        print("  TEST: download_logs -- skipped (add --download flag to enable)")
        print("  HINT: python test_local.py --live " + TICKET_ID + " --download")
        print(SEP)

    print("\n" + "=" * 60)
    if LIVE_MODE:
        print("  All live tests complete.")
        if ticket:
            n_c = ticket.get("total_comments", 0)
            n_f = ticket.get("total_attachments", 0)
            print("  Ticket has %d comments, %d attachments." % (n_c, n_f))
        if not DOWNLOAD_MODE:
            print("  Add --download to actually save the files.")
    else:
        print("  Mock tests passed.")
        print("  Run with --live <TICKET_ID> and real BTSP_SESSION to test against live site.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

Here are all 9 tools in your BTSP MCP server and how to invoke them in Cline:
get_ticket — Full ticket detail: metadata, all comments, attachment list
Fetch ticket TS26501G
Show me full details of TS26501G
get_ticket_context — Best for investigation: downloads all files + reads log contents + all comments, returns one big LLM-ready block
Investigate ticket TS26501G and give me a root cause analysis
Analyze TS26501G — download all logs and summarize what's happening
download_logs — Downloads all attachments to disk, returns file paths
Download all log files from TS26501G to C:\btsp_logs
list_tickets — Your team's tickets filtered by status
List my open BTSP tickets
Show all closed tickets
search_tickets — Keyword search on ticket titles
Search BTSP tickets for "BFD alarm"
Find tickets about BGP neighbor failure
list_tickets_by_owner — Tickets assigned to a specific person
Show tickets owned by rajneesh.r
List open tickets assigned to shreerang.b
List all tickets (open and closed) owned by rajneesh.r
get_view_tickets — All tickets in a saved view
Get tickets from view FV2605080001
Show tickets in view "Clone : Core Platform Pending Issues"
list_views — List your saved views (may not work on this BTSP instance)
List my BTSP saved views
debug_raw — Developer tool to call any BTSP endpoint directly
Call BTSP endpoint /ts/ticketView.do with method getTicketViewList
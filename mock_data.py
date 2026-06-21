"""
Mock API responses matching the real BTSP JSON structure (confirmed from Network tab).
Used when BTSP_MOCK=true.
"""

MOCK_ROWS = [
    {
        "ticketNo": "TS26501G",
        "ticketNoEnc": "wo50mRP4r2TAOGIIruINZoMHFtATAOGEETAOGEE",
        "title": "Observing BFD Session alarm and BGP neighbor fail alarm in 5nos of MH3vGWU",
        "ticketStatusNm": "In-progress",
        "ticketStatusCd": "40",
        "reqTypeNm": "Incident",
        "reqTypeCd": "01",
        "currentOwner": "Shreerang Bandurao ***",
        "ownerUserId": "shreerang.b",
        "agentGrpNm": "[SIEL][CORE] TAC",
        "sbmtUserNm": "Anurag Kumar ***",
        "sbmtDttm": "05/02/2026 20:10:13",
        "lastUpdateDttm": "06/19/2026 20:26:21",
        "countryCd": "(IN) India",
        "emailAddr": "anu.tiwari@samsung.com",
        "bizUnitCd": "System Network",
        "productCtgry1Nm": "LTE-Core",
        "productCtgry2Nm": "vEPC",
        "productCtgry3Nm": "vGW-U",
        "productCtgry4Nm": None,
        "sysImpactNm": "None",
        "relatedTicketNo": "IM367817883",
        "slaDueDttm": "20260509121013",
        "closeDate": "",
        "siteNm": "",
        "secorgId": "SIEL",
    },
    {
        "ticketNo": "TS26100A",
        "ticketNoEnc": "abc123TAOGEETAOGEE",
        "title": "5G NR gNB handover failure rate increased on Cluster WEST-07",
        "ticketStatusNm": "Open",
        "ticketStatusCd": "10",
        "reqTypeNm": "Incident",
        "reqTypeCd": "01",
        "currentOwner": "Rajneesh Rana ***",
        "ownerUserId": "rajneesh.r",
        "agentGrpNm": "[SIEL][RAN] TAC",
        "sbmtUserNm": "Field Engineer ***",
        "sbmtDttm": "06/10/2026 08:00:00",
        "lastUpdateDttm": "06/18/2026 14:30:00",
        "countryCd": "(IN) India",
        "emailAddr": "engineer@operator.com",
        "bizUnitCd": "System Network",
        "productCtgry1Nm": "5G-RAN",
        "productCtgry2Nm": "gNB",
        "productCtgry3Nm": "CU-CP",
        "productCtgry4Nm": None,
        "sysImpactNm": "High",
        "relatedTicketNo": "",
        "slaDueDttm": "20260617080000",
        "closeDate": "",
        "siteNm": "WEST-07",
        "secorgId": "SIEL",
    },
]

MOCK_DETAILS = {
    "TS26501G": {
        "ticket_id": "TS26501G",
        "title": "Observing BFD Session alarm and BGP neighbor fail alarm in 5nos of MH3vGWU",
        "comments": [
            {
                "author": "Rahul Kumar **** (r.kumarsaha, SWHQ)",
                "date": "06/19/2026 20:26:04 GMT 8",
                "body": "Team, please check the latest BFD session logs. Alarms still active on 5 nodes.",
                "attachments": [],
            },
            {
                "author": "Jayesh Jaywant *** TAC-1 (jayesh.m, SIEL)",
                "date": "06/09/2026 16:49:50 GMT 8",
                "body": "HI Team,\n\nPlease find required Logs from WB2 vEPC Nodes.\n\n//JAYESH",
                "attachments": [
                    {
                        "comment_id": "CMT2606090577",
                        "obs_file_id": "OBS0000120238",
                        "obs_no": "1",
                        "filename": "WB2__CMD_stats.zip",
                    }
                ],
            },
            {
                "author": "Shantanu *** (shantanu.m2, SIEL)",
                "date": "06/06/2026 12:14:45 GMT 8",
                "body": "Attached BFD SOCK STATS and alarm history logs for analysis.",
                "attachments": [
                    {
                        "comment_id": "CMT2605080167",
                        "obs_file_id": "OBS0000112159",
                        "obs_no": "3",
                        "filename": "mh3a2hph07vfgwu01sm_BFD_SOCK_STATS.txt",
                    },
                    {
                        "comment_id": "CMT2605080167",
                        "obs_file_id": "OBS0000112159",
                        "obs_no": "4",
                        "filename": "mh3a2hph07vfgwu01sm_Alarm_History.txt",
                    },
                ],
            },
        ],
        "total_comments": 3,
        "total_attachments": 3,
    },
    "TS26100A": {
        "ticket_id": "TS26100A",
        "title": "5G NR gNB handover failure rate increased on Cluster WEST-07",
        "comments": [
            {
                "author": "Rajneesh Rana *** (rana.r, SWHQ)",
                "date": "06/18/2026 14:30:00 GMT 8",
                "body": "Please provide RRC logs and handover trace from the affected gNBs.",
                "attachments": [],
            }
        ],
        "total_comments": 1,
        "total_attachments": 0,
    },
}


def mock_api_response(path, params, data):
    params = params or {}
    data = data or {}
    method = params.get("method", "")

    if method == "getTicketSearchList":
        search_id    = data.get("txtSearchData", "")
        search_field = data.get("txtSearchField", "title")
        if search_id:
            sl = search_id.lower()
            if search_field == "ticketOwner":
                rows = [r for r in MOCK_ROWS
                        if sl in r.get("currentOwner", "").lower()
                        or sl in r.get("ownerUserId", "").lower()]
            elif search_field == "ticketId":
                rows = [r for r in MOCK_ROWS
                        if sl in r["ticketNo"].lower()]
            else:  # title / default
                rows = [r for r in MOCK_ROWS
                        if sl in r["title"].lower()
                        or sl in r["ticketNo"].lower()]
        else:
            rows = MOCK_ROWS
        return {"page": 1, "records": len(rows), "total": len(rows), "rows": rows}

    if method == "downloadInfo":
        obs_id = data.get("obsFileId", "OBS_MOCK")
        obs_no = data.get("obsNo", "1")
        return {"result": {
            "namespaceName": "mock-namespace",
            "regionUri": "ap-seoul-1",
            "parAccessUri": "/p/MOCK_TOKEN/n/mock-namespace/b/btsp_mock_bucket/o/TICKET/mock/%s_%s.bin" % (obs_id, obs_no),
            "parId": "MOCK_PAR_ID",
            "code": "0",
        }}

    if method == "getTicketViewResultCount":
        return {"viewCnt": "10", "viewId": "MOCK_VIEW_ID_12345"}

    if method == "getTicketInfo":
        return {"bizUnitCd": "G3", "ticketStatusCd": "40",
                "isCustomer": "N", "reqTypeCd": "01"}

    if method == "getTicketViewList":
        return {"rows": [
            {"viewId": "FV2605080001", "viewNm": "Clone : Core Platform Pending Issues", "ticketCnt": 12},
            {"viewId": "FV2605080002", "viewNm": "My Open Incidents", "ticketCnt": 5},
        ]}

    if method == "getTicketView":
        view_id = data.get("viewId", "")
        view_nm = data.get("viewNm", "")
        # Return mock tickets for the view
        return {"page": 1, "records": 2, "total": 2, "rows": MOCK_ROWS}

    return {"mock": True, "path": path, "method": method}


def mock_html_response(path, params):
    return "<html><body><p>MOCK HTML</p></body></html>"


def mock_ticket_detail(ticket_id):
    default = {
        "ticket_id": ticket_id,
        "title": "Mock ticket " + ticket_id,
        "comments": [],
        "total_comments": 0,
        "total_attachments": 0,
    }
    return MOCK_DETAILS.get(ticket_id, default)

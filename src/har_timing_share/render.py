"""Self-contained, script-free report; no captured strings are interpolated."""

from html import escape

from .core import PHASES

STYLE = """
:root{color-scheme:light;
--ink:#192d48;
--quiet:#52647d;
--line:#cbd8e6;
--blue:#176c8e}

*{box-sizing:border-box}
body{margin:0;
background:#f2f6fa;
color:var(--ink);
font:16px/1.6 'Segoe UI',Arial,sans-serif}

main{max-width:1200px;
margin:auto;
padding:32px 24px 64px}
h1{font:600 36px/1.2 'Segoe UI',Arial,sans-serif;
letter-spacing:-1px;
margin:0 0 12px}

p{max-width:78ch}
h2{font-size:22px;
margin-top:36px}
.note{border-left:4px solid var(--blue);
padding:10px 16px;
background:#e1edf5}

.stats{display:flex;
flex-wrap:wrap;
gap:16px 48px;
padding:18px 0;
border-block:1px solid var(--line)}
.stats div{min-width:120px}

dt{color:var(--quiet);
font-size:14px}
dd{margin:0;
font-size:24px;
font-weight:600;
font-variant-numeric:tabular-nums}

.scroll{overflow:auto;
background:white;
border:1px solid var(--line)}
:focus-visible{outline:3px solid #087e8b;
outline-offset:3px}

table{border-collapse:collapse;
width:100%;
font-size:14px;
font-variant-numeric:tabular-nums}
caption{text-align:left;
padding:16px;
color:var(--quiet)}

th,td{text-align:left;
padding:10px 12px;
border-bottom:1px solid #e1e8f0;
vertical-align:top;
white-space:nowrap}
thead{background:#e9f0f7}
th{font-weight:600}

.timeline{width:34%;
min-width:260px}
.track{height:20px;
position:relative;
background:repeating-linear-gradient(90deg,#edf2f7 0,#edf2f7 calc(25% - 1px),#cbd8e6 25%)}

.bar{position:absolute;
top:4px;
height:12px;
border-radius:2px;
background:var(--blue);
min-width:2px}
.error{background:#a33442}
.unknown{background:#68778c}

.small{font-size:13px;
color:var(--quiet)}
summary{cursor:pointer;
color:#173f73}
details dl{margin:8px 0;
display:grid;
grid-template-columns:70px 1fr;
gap:0 10px}

details dd{font-size:13px;
font-weight:400}
details dt{font-size:13px}
.empty{padding:24px}
footer{font-size:13px;
color:var(--quiet);
margin-top:30px}

@media(max-width:600px){main{padding:24px 14px}
h1{font-size:29px}
.stats{gap:16px 24px}
.stats div{min-width:100px}
}

@media print{body{background:white}
main{max-width:none;
padding:0}
.scroll{overflow:visible}
table{font-size:10px}
.timeline{min-width:140px}
th,td{padding:5px}
details{display:none}
}

"""


def _ms(value):
    return "unknown" if value is None else f"{value:,.3f} ms"


def render_html(report: dict) -> str:
    """Render a report returned by project_har, with every text value escaped."""
    summary = report["summary"]
    span = max(summary["span_ms"], 0.001)
    rows = []
    for entry in report["entries"]:
        left = min(100.0, max(0.0, entry["start_ms"] / span * 100))
        width = min(100.0 - left, max(0.0, entry["duration_ms"] / span * 100))
        phase_rows = "".join(
            f"<dt>{phase}</dt><dd>{_ms(entry['phases_ms'][phase])}</dd>" for phase in PHASES
        )
        color = "error" if entry["status"] >= 400 else "unknown" if entry["status"] == 0 else ""
        body_size = (
            "unknown"
            if entry["decoded_body_bytes"] is None
            else f"{entry['decoded_body_bytes']:,} B"
        )
        rows.append(
            f"<tr><th scope='row'>{escape(entry['id'])}</th>"
            f"<td>{escape(entry['method'])}</td><td>{entry['status']}</td>"
            f"<td>{escape(entry['resource'])}</td><td>{_ms(entry['start_ms'])}</td>"
            f"<td>{_ms(entry['duration_ms'])}</td><td>{body_size}</td>"
            f"<td class='timeline'><div class='track' aria-hidden='true'>"
            f"<span class='bar {color}' style='left:{left:.5f}%;width:{width:.5f}%'></span></div>"
            f"<details><summary>Phases</summary><dl>{phase_rows}</dl></details></td></tr>"
        )
    stats = [
        ("Requests", f"{summary['request_count']:,}"),
        ("Capture span", _ms(summary["span_ms"])),
        ("Median request", _ms(summary["p50_ms"])),
        ("95th percentile", _ms(summary["p95_ms"])),
    ]
    stat_html = "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in stats)
    table = (
        (
            "<div class='scroll' tabindex='0' role='region' "
            "aria-label='Scrollable request waterfall'>"
            "<table><caption>Time relative to the earliest request. Bars share the capture span. "
            "Body sizes are decoded bytes, not transferred bytes.</caption>"
            "<thead><tr><th>Request</th><th>Method</th><th>Status</th><th>Type</th>"
            "<th>Start</th><th>Duration</th><th>Body size</th>"
            f"<th class='timeline'>Waterfall: 0 to {_ms(summary['span_ms'])}</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
        if rows
        else "<p class='empty'>This capture has no requests.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy"
content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Network timing report</title><style>{STYLE}</style></head>
<body><main><h1>Network timing report</h1>
<p>A timing view of a network capture. Request labels are generated ordinals;
URLs, hosts, headers, cookies, bodies and absolute timestamps are absent.</p>
<p class="note">Performance data can still identify a session. Review this report before sharing.
This derived report cannot be imported as a HAR or used to replay requests.</p>
<dl class="stats">{stat_html}</dl>
<p>{int(summary["http_error_count"])} HTTP errors (status 400–599),
{int(summary["network_error_count"])} requests with status 0.
Known decoded body bytes: {summary["known_decoded_body_bytes"]:,};
unknown body sizes: {summary["unknown_body_sizes"]:,}.</p>
<h2>Request waterfall</h2>{table}
<p class="small">Unknown phases are omitted by the exporter or marked -1. TLS (ssl) is included
in connect time in HAR; phase times should not be added blindly. Status 0 means no HTTP response.
Percentiles use the nearest-rank method.</p>
<footer>Generated locally by har-timing-share 0.1.0.
No scripts, external assets or network requests.</footer>
</main></body></html>"""

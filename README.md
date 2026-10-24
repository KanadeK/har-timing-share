# har-timing-share

Share a network capture's **performance shape without carrying captured text**.
Produce an offline HTML waterfall or versioned JSON containing relative timings,
method/resource categories, status codes and decoded body sizes.
Python 3.10+, no runtime dependencies. [中文说明](README.zh-CN.md).

HAR files can contain private information in URLs, headers, bodies and browser
extensions. This tool builds a new, small report from an allowlist. It discards
all URLs, hosts, paths, headers, cookies, bodies, comments, absolute timestamps,
page data, IP addresses and vendor extensions. Unrecognized method and MIME text
becomes a fixed category. It does not produce a sanitized HAR for replay.

## Install and try

From a source checkout (not published to PyPI):

```console
python -m venv .venv
```

Activate it with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate`
on Linux/macOS, then:

```console
python -m pip install .
har-timing-share examples/demo.har -o performance.html
har-timing-share examples/demo.har --format json -o performance.json
```

Open `performance.html` in a browser. The synthetic example contains three
requests: a 350 ms span, 120 ms median, 250 ms 95th percentile, one HTTP error,
1,800 known decoded body bytes and one unknown size. The example's private marker
strings and URLs do not appear in either output. Existing output files are never
overwritten; choose new filenames when repeating the commands.

If the executable is not on PATH, use `python -m har_timing_share` with the same
arguments. JSON can also go to stdout:

```console
python -m har_timing_share capture.har --format json -o -
python -m har_timing_share capture.har -o share.html --max-bytes 134217728 --max-entries 20000
```

Defaults: **64 MiB input**, **10,000 entries**. Inputs must be regular UTF-8 JSON
files, optionally with a BOM. Links, special files, duplicate JSON keys and
non-finite JSON constants are rejected. The JSON parser loads the bounded file
into memory; this is not a streaming parser.

| Exit | Meaning |
| --- | --- |
| 0 | A report was successfully produced (an empty capture is explicitly shown) |
| 2 | Invalid input/options, exceeded limits, existing output or an I/O error |
| 130 | Interrupted during processing |

## Retained data contract

JSON has `schema_version: 1`, `summary`, and `entries`. Each entry contains:

| Field | Meaning |
| --- | --- |
| id | Generated ordinal from the input entry index, such as request-00001 |
| method | GET/HEAD/POST/PUT/DELETE/CONNECT/OPTIONS/TRACE/PATCH, otherwise OTHER |
| resource | html/css/script/json/image/font/media/other |
| status | Integer 100–599 or 0 for no HTTP response |
| start_ms | Milliseconds after the earliest captured request |
| duration_ms | HAR's reported total request time |
| decoded_body_bytes | `response.content.size`; null when missing or -1 |
| phases_ms | blocked/dns/connect/ssl/send/wait/receive, null for missing or -1 |

Entries are ordered by relative start, then ordinal. Numeric times are rounded
to 0.001 ms. Time values and individual body sizes must be nonnegative and at most
10^12 (except the documented unknown sentinels). Body sizes must be integers.
Each entry requires a timezone-bearing ISO `startedDateTime`, nonnegative `time`,
request/response objects and a valid response status. Optional content and timing
objects can be absent. This validates consumed fields, not the complete HAR schema.

The summary includes counts, total capture span, nearest-rank median/p95 request
duration, known decoded body bytes and unknown size counts. Decoded size is **not
network transfer size**. TLS is included in HAR connect time; summing all phases
would count it twice. Unknown values are not silently converted to zero. The HTML
has no scripts or external resources and includes keyboard-accessible phase details.

## Python API

```python
from har_timing_share import load_har, project_har, render_html

report = project_har(load_har("capture.har"))
page = render_html(report)
assert report["schema_version"] == 1
```

`project_har` creates new objects and leaves the source untouched. `HarError`
diagnostics identify consumed fields and entry ordinals without quoting captured
values. `render_html` expects the projection returned by `project_har`.

## Privacy boundary and limitations

This is data minimization, **not an anonymity guarantee**. Request counts,
ordering, method categories, status codes, timings and sizes may fingerprint a
session or disclose activity. Review even the derived report before sharing it.
Raw captures remain sensitive on disk and in process memory. The tool does not
fetch recorded URLs, send telemetry, create a server, or claim to erase input data.

Removed data cannot be recovered. There are no endpoint labels, domain groupings,
request replay, content inspection, Core Web Vitals, or page-navigation metrics.
The waterfall shows reported durations rather than reconstructing browser behavior.
For rich debugging with controlled redaction, consider
[Google HAR Sanitizer](https://github.com/google/har-sanitizer),
[har-anonymizer](https://github.com/ErikApption/har-anonymizer) or your browser's
DevTools. [Chrome's sanitized export](https://developer.chrome.com/docs/devtools/network/reference/)
filters sensitive headers; this tool instead drops all uncontrolled captured text.
Field semantics follow the [HAR 1.2 specification](https://github.com/ahmadnassri/har-spec/blob/master/versions/1.2.md).
No code or sample captures from those projects are included.

For a HAR-shaped export with pseudonymous endpoint correlation, see
[har-silhouette](https://github.com/KanadeK/har-silhouette). har-timing-share serves
the report-sharing workflow: its script-free HTML opens directly in a browser,
uses generated request ordinals, and carries no endpoint labels or mapping.

## Development and cleanup

```console
python -m pip install -e . build==1.6.1 ruff==0.17.2
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m build
python tools/smoke.py
```

Tests use synthetic captures, including sentinel text in discarded fields and
malformed inputs. The CI matrix targets Linux/macOS/Windows with Python
3.10/3.13/3.14; actual hosted results are visible in GitHub Actions.
See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

Uninstall with `python -m pip uninstall har-timing-share`. Delete the generated
HTML/JSON reports and the virtual environment when no longer needed. Reports
are the only persistent files the CLI creates. Test/smoke temporary directories
are automatically cleaned. Build outputs live in `dist/` and `build/`.

[MIT license](LICENSE). Version **0.1.0**. No bundled third-party runtime code/assets.

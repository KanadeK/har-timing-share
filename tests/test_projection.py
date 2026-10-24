import copy
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from har_timing_share import HarError, load_har, project_har, render_html
from har_timing_share.core import PHASES

MARKER = "SYNTHETIC_PRIVATE_MARKER_94d53"


def entry(**changes):
    result = {
        "startedDateTime": "2026-01-01T12:00:00.000Z",
        "time": 120,
        "request": {"method": "GET", "url": "https://example.test/private/" + MARKER},
        "response": {"status": 200, "content": {"mimeType": "text/html", "size": 1000}},
        "timings": {"dns": 5, "connect": 10, "ssl": 6, "send": 1, "wait": 80, "receive": 24},
    }
    result.update(changes)
    return result


def har(*entries):
    return {"log": {"version": "1.2", "creator": {"name": MARKER}, "entries": list(entries)}}


class ProjectionTests(unittest.TestCase):
    def test_known_summary_and_relative_starts(self):
        first = entry()
        second = entry(startedDateTime="2026-01-01T12:00:00.030Z", time=60)
        second["response"] = {"status": 0, "content": {"size": -1}}
        third = entry(startedDateTime="2026-01-01T12:00:00.100Z", time=250)
        third["response"] = {
            "status": 503,
            "content": {"mimeType": "application/json", "size": 800},
        }
        result = project_har(har(first, second, third))
        self.assertEqual(
            result["summary"],
            {
                "request_count": 3,
                "span_ms": 350.0,
                "p50_ms": 120.0,
                "p95_ms": 250.0,
                "known_decoded_body_bytes": 1800,
                "unknown_body_sizes": 1,
                "http_error_count": 1,
                "network_error_count": 1,
            },
        )
        self.assertEqual([item["start_ms"] for item in result["entries"]], [0, 30, 100])

    def test_all_uncontrolled_text_is_discarded(self):
        item = entry()
        item.update(
            {
                "comment": MARKER,
                "serverIPAddress": MARKER,
                "_webSocketMessages": [MARKER],
                "pageref": MARKER,
            }
        )
        for direction in ("request", "response"):
            item[direction].update(
                {
                    "headers": [{"name": MARKER, "value": MARKER}],
                    "cookies": [{"name": MARKER, "value": MARKER}],
                    "queryString": [{"name": MARKER, "value": MARKER}],
                    "postData": {"text": MARKER, "params": [{"name": MARKER, "value": MARKER}]},
                    "_vendor": MARKER,
                    "statusText": MARKER,
                    "httpVersion": MARKER,
                }
            )
        item["response"]["content"].update({"text": MARKER, "encoding": MARKER, "_custom": MARKER})
        item["cache"] = {MARKER: MARKER}
        source = har(item)
        source["log"].update({"pages": [{"title": MARKER}], "comment": MARKER, "_custom": MARKER})
        before = copy.deepcopy(source)
        report = project_har(source)
        serialized = json.dumps(report)
        html = render_html(report)
        for forbidden in (
            MARKER,
            "example.test",
            "2026-01-01",
            "private/",
            "serverIPAddress",
            "queryString",
        ):
            self.assertNotIn(forbidden, serialized)
            self.assertNotIn(forbidden, html)
        self.assertEqual(source, before)

    def test_output_string_vocabulary_is_closed(self):
        item = entry()
        item["request"]["method"] = MARKER
        item["response"]["content"]["mimeType"] = MARKER
        projected = project_har(har(item))["entries"][0]
        self.assertEqual(projected["method"], "OTHER")
        self.assertEqual(projected["resource"], "other")
        self.assertEqual(
            set(projected),
            {
                "id",
                "method",
                "status",
                "resource",
                "start_ms",
                "duration_ms",
                "decoded_body_bytes",
                "phases_ms",
            },
        )
        self.assertEqual(set(projected["phases_ms"]), set(PHASES))

    def test_changes_to_discarded_fields_cannot_change_output(self):
        rng = random.Random(73)
        expected = project_har(har(entry()))
        for _ in range(100):
            item = entry()
            item["request"]["url"] = str(rng.getrandbits(256))
            item["response"]["content"]["text"] = str(rng.getrandbits(256))
            item["_unknown"] = {str(rng.random()): MARKER}
            self.assertEqual(project_har(har(item)), expected)

    def test_timezone_offsets_reordered_entries_and_ties(self):
        later = entry(startedDateTime="2026-01-01T08:00:00.100-04:00")
        earlier = entry(startedDateTime="2026-01-01T20:00:00.000+08:00")
        result = project_har(har(later, earlier, earlier))
        self.assertEqual(
            [r["id"] for r in result["entries"]],
            ["request-00002", "request-00003", "request-00001"],
        )
        self.assertEqual(result["entries"][2]["start_ms"], 100)

    def test_submillisecond_rounding(self):
        second = entry(startedDateTime="2026-01-01T12:00:00.000123Z", time=0.123456)
        result = project_har(har(entry(time=0), second))
        self.assertEqual(result["entries"][1]["start_ms"], 0.123)
        self.assertEqual(result["entries"][1]["duration_ms"], 0.123)

    def test_empty_capture_is_honest(self):
        result = project_har(har())
        self.assertEqual(result["summary"]["span_ms"], 0)
        self.assertIsNone(result["summary"]["p95_ms"])
        self.assertIn("no requests", render_html(result))

    def test_single_duration_nearest_rank_percentiles(self):
        result = project_har(har(entry(time=12.4)))
        self.assertEqual(result["summary"]["p50_ms"], 12.4)
        self.assertEqual(result["summary"]["p95_ms"], 12.4)

    def test_resource_categories_and_methods_are_canonical(self):
        for mime, expected in [
            ("text/html; charset=utf-8", "html"),
            ("text/css", "css"),
            ("text/javascript", "script"),
            ("application/problem+json", "json"),
            ("image/svg+xml", "image"),
            ("font/woff2", "font"),
            ("video/mp4", "media"),
            ("audio/mpeg", "media"),
            (None, "other"),
        ]:
            with self.subTest(mime=mime):
                item = entry()
                item["response"]["content"]["mimeType"] = mime
                item["request"]["method"] = "post"
                row = project_har(har(item))["entries"][0]
                self.assertEqual(row["resource"], expected)
                self.assertEqual(row["method"], "POST")

    def test_unknown_phases_and_sizes_do_not_become_zero(self):
        item = entry(timings={"wait": -1})
        item["response"]["content"] = {}
        row = project_har(har(item))["entries"][0]
        self.assertTrue(all(value is None for value in row["phases_ms"].values()))
        self.assertIsNone(row["decoded_body_bytes"])

    def test_rejects_bad_shapes(self):
        for document in [
            None,
            [],
            {},
            {"log": []},
            {"log": {}},
            {"log": {"entries": {}}},
            har(None),
            har({}),
        ]:
            with self.subTest(document=document), self.assertRaises(HarError):
                project_har(document)
        for name in ("request", "response", "timings"):
            with self.subTest(name=name), self.assertRaises(HarError):
                project_har(har(entry(**{name: []})))

    def test_bad_timestamps_are_rejected_without_values(self):
        for value in [
            None,
            MARKER,
            "2026-02-30T00:00:00Z",
            "2026-01-01T12:00:00",
            "2026-01-01 12:00:00Z",
            "2026-01-01T12:00:00+99:00",
        ]:
            with self.subTest(value=value), self.assertRaises(HarError) as caught:
                project_har(har(entry(startedDateTime=value)))
            self.assertNotIn(MARKER, str(caught.exception))

    def test_invalid_durations_and_phases(self):
        for value in [-1, True, None, "123", math.nan, math.inf, -math.inf, 10**20]:
            with self.subTest(value=value), self.assertRaises(HarError):
                project_har(har(entry(time=value)))
        for value in [-2, True, "123", math.nan, math.inf]:
            with self.subTest(phase=value), self.assertRaises(HarError):
                project_har(har(entry(timings={"dns": value})))

    def test_invalid_status_and_size(self):
        for status in [True, 200.0, -1, 99, 600, "200", None]:
            item = entry()
            item["response"]["status"] = status
            with self.subTest(status=status), self.assertRaises(HarError):
                project_har(har(item))
        for size in [True, 3.5, -2, "100", 10**20]:
            item = entry()
            item["response"]["content"]["size"] = size
            with self.subTest(size=size), self.assertRaises(HarError):
                project_har(har(item))

    def test_input_limits_and_option_validation(self):
        with self.assertRaises(HarError):
            project_har(har(entry(), entry()), max_entries=1)
        for value in [0, -1, True, 1.5]:
            with self.subTest(value=value), self.assertRaises(HarError):
                project_har(har(), max_entries=value)

    def test_html_is_standalone_script_free_and_accessible(self):
        text = render_html(project_har(har(entry())))
        self.assertNotIn("<script", text.lower())
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)
        self.assertIn("Content-Security-Policy", text)
        self.assertIn("<caption>", text)
        self.assertIn("scope='row'", text)
        self.assertIn("<details>", text)


class FileAndCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="har-timing-share-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "capture.har"
        self.source.write_text(json.dumps(har(entry())), encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "har_timing_share", *map(str, args)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_load_bom_and_strict_json(self):
        self.source.write_bytes(b"\xef\xbb\xbf" + json.dumps(har()).encode())
        self.assertEqual(load_har(self.source)["log"]["entries"], [])
        for content in [
            b"{} trailing",
            b'{"log":{},"log":{}}',
            b'{"x":NaN}',
            b'{"x":Infinity}',
            b"\xff",
        ]:
            self.source.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(HarError):
                load_har(self.source)

    def test_file_limits_and_missing_input(self):
        with self.assertRaises(HarError):
            load_har(self.source, max_bytes=1)
        with self.assertRaises(HarError):
            load_har(self.root / "missing")
        with self.assertRaises(HarError):
            load_har(self.root)
        with self.assertRaises(HarError):
            load_har(self.source, max_bytes=True)

    def test_json_stdout_and_new_html_file(self):
        stdout = self.run_cli(self.source, "--format", "json", "-o", "-")
        self.assertEqual(stdout.returncode, 0, stdout.stderr)
        self.assertEqual(json.loads(stdout.stdout)["summary"]["request_count"], 1)
        self.assertNotIn(MARKER, stdout.stdout + stdout.stderr)
        output = self.root / "waterfall.html"
        result = self.run_cli(self.source, "-o", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Network timing report", output.read_text(encoding="utf-8"))
        self.assertNotIn(MARKER, output.read_text(encoding="utf-8"))

    def test_never_overwrites_existing_file_or_source(self):
        before = self.source.read_bytes()
        result = self.run_cli(self.source, "-o", self.source)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.source.read_bytes(), before)
        output = self.root / "exists.json"
        output.write_text("keep", encoding="utf-8")
        self.assertEqual(self.run_cli(self.source, "--format", "json", "-o", output).returncode, 2)
        self.assertEqual(output.read_text(), "keep")

    def test_invalid_input_leaves_no_output_and_no_sensitive_diagnostic(self):
        self.source.write_text(json.dumps(har(entry(startedDateTime=MARKER))), encoding="utf-8")
        output = self.root / "not-created.html"
        result = self.run_cli(self.source, "-o", output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertNotIn(MARKER, result.stderr + result.stdout)

    def test_cli_usage_and_permissions_errors(self):
        self.assertEqual(self.run_cli("--version").stdout.strip(), "0.1.0")
        self.assertEqual(self.run_cli("--help").returncode, 0)
        self.assertEqual(self.run_cli(self.source, "-o", "-").returncode, 2)
        self.assertEqual(
            self.run_cli(self.source, "-o", self.root / "x", "--max-bytes", "0").returncode, 2
        )
        self.assertEqual(self.run_cli(self.source, "-o", self.root / "missing" / "x").returncode, 2)

    @unittest.skipIf(os.name == "nt", "Windows symlink creation requires elevated privileges")
    def test_links_and_fifos_are_rejected_before_reading(self):
        link = self.root / "link.har"
        link.symlink_to(self.source)
        with self.assertRaises(HarError):
            load_har(link)
        fifo = self.root / "pipe.har"
        os.mkfifo(fifo)
        with self.assertRaises(HarError):
            load_har(fifo)


if __name__ == "__main__":
    unittest.main()

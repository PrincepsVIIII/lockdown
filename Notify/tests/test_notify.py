import contextlib
from http.client import HTTPConnection
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "notify"
LOADER = importlib.machinery.SourceFileLoader("notify_app", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
notify = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(notify)
KEY = bytes.fromhex("ab" * 32)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.popups = []
        self.server = notify.NotifyServer(("127.0.0.1", 0), KEY, self.popups.append)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address
        self.body = json.dumps({"title": "Hello", "message": "Hi there!"}).encode()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, body=None, headers=None, path="/notify"):
        if body is None:
            body = self.body
        if headers is None:
            headers = notify.signed_headers(KEY, body)
        connection = HTTPConnection(self.host, self.port, timeout=3)
        try:
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_authenticated_message_reaches_popup(self):
        status, reply = self.request()
        self.assertEqual(status, 200)
        self.assertTrue(reply["ok"])
        self.assertEqual(self.popups, [{"title": "Hello", "message": "Hi there!", "urgency": "normal", "duration": 8}])

    def test_missing_and_wrong_keys_are_rejected(self):
        for headers in ({"Content-Type": "application/json"}, notify.signed_headers(b"wrong", self.body)):
            with self.subTest(headers=headers):
                self.assertEqual(self.request(headers=headers)[0], 401)
        self.assertEqual(self.popups, [])

    def test_tampered_body_is_rejected(self):
        headers = notify.signed_headers(KEY, self.body)
        self.assertEqual(self.request(body=b'{"message":"changed"}', headers=headers)[0], 401)
        self.assertEqual(self.popups, [])

    def test_replay_is_rejected(self):
        headers = notify.signed_headers(KEY, self.body)
        self.assertEqual(self.request(headers=headers)[0], 200)
        self.assertEqual(self.request(headers=headers)[0], 401)
        self.assertEqual(len(self.popups), 1)

    def test_stale_and_future_messages_are_rejected(self):
        now = time.time()
        for offset in (-120, 120):
            with mock.patch.object(notify.time, "time", return_value=now + offset):
                headers = notify.signed_headers(KEY, self.body)
            self.assertEqual(self.request(headers=headers)[0], 401)
        self.assertEqual(self.popups, [])

    def test_bad_auth_header_is_rejected_without_crashing(self):
        for name, value in (("X-Notify-Timestamp", "not-a-time"),
                            ("X-Notify-Nonce", "x" * 32),
                            ("X-Notify-Signature", "x" * 64)):
            headers = notify.signed_headers(KEY, self.body)
            headers[name] = value
            self.assertEqual(self.request(headers=headers)[0], 401)
        self.assertEqual(self.request()[0], 200)

    def test_invalid_payloads_are_rejected_without_popups(self):
        for body in (b"not json", b"[]", b'{"message":""}',
                     b'{"message":"hi","duration":true}',
                     b'{"message":"hi","duration":301}',
                     b'{"message":"hi","title":null}',
                     b'{"message":"hi","urgency":"unknown"}',
                     b'{"message":"hi","command":"echo unwanted"}',
                     b'{"message":"\\u0000"}', b'{"message":"\\ud800"}',
                     b"[" * 1100 + b"]" * 1100,
                     b'{"message":"' + b"a" * 4001 + b'"}'):
            with self.subTest(body=body[:100]):
                self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.popups, [])
        self.assertEqual(self.request()[0], 200)

    def test_oversized_body_and_wrong_content_type(self):
        self.assertEqual(self.request(body=b"a" * (notify.MAX_BODY + 1))[0], 413)
        headers = notify.signed_headers(KEY, self.body)
        headers["Content-Type"] = "text/plain"
        self.assertEqual(self.request(headers=headers)[0], 415)
        self.assertEqual(self.request(path="/other")[0], 404)
        self.assertEqual(self.popups, [])

    def test_duplicate_length_and_chunked_requests_are_rejected(self):
        for headers in ("Content-Length: 2\r\nContent-Length: 2\r\n",
                        "Content-Length: 2\r\nTransfer-Encoding: chunked\r\n"):
            with socket.create_connection((self.host, self.port), timeout=3) as connection:
                raw = "POST /notify HTTP/1.0\r\nContent-Type: application/json\r\n" + headers + "\r\n{}"
                connection.sendall(raw.encode())
                self.assertIn(b"400", connection.recv(4096).split(b"\r\n")[0])
        self.assertEqual(self.popups, [])

    def test_backend_failure_is_reported_to_sender(self):
        def fail(data):
            raise subprocess.CalledProcessError(1, "notify-send")
        self.server.popup = fail
        status, reply = self.request()
        self.assertEqual(status, 503)
        self.assertFalse(reply["ok"])

    def test_cli_sender_delivers_unicode_and_reports_offline_target(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "key"
            key_file.write_text(KEY.hex(), encoding="ascii")
            # Reserve a TCP port without listening so the failed target is deterministic.
            with socket.socket() as offline:
                offline.bind(("127.0.0.1", 0))
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "send", "127.0.0.1:" + str(offline.getsockname()[1]),
                     "Hello, café ☕ <b>world</b>!", "--also", "{}:{}".format(self.host, self.port),
                     "--key-file", str(key_file), "--title", "Reminder", "--duration", "15"],
                    capture_output=True, text=True, encoding="utf-8", timeout=15,
                )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("sent", result.stdout)
        self.assertTrue(result.stderr)
        self.assertEqual(len(self.popups), 1)
        self.assertEqual(self.popups[0]["message"], "Hello, café ☕ <b>world</b>!")
        self.assertEqual(self.popups[0]["duration"], 15)

    def test_cli_sender_success_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "key"
            key_file.write_text(KEY.hex(), encoding="ascii")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "send", "{}:{}".format(self.host, self.port),
                 "It works", "--key-file", str(key_file)],
                capture_output=True, text=True, timeout=10,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.popups), 1)

    def test_all_without_keys_skips_failure_deduplicates_and_summarizes(self):
        self.server.key = None
        target = "{}:{}".format(self.host, self.port)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "all", "127.0.0.(2,1):{}".format(self.port),
             "Everyone save your work", "--also", target, "--workers", "1"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("127.0.0.2", result.stderr)
        self.assertIn(target + ": sent", result.stdout)
        self.assertIn("Finished: 1/2 targets accepted the notification; 1 failed.", result.stdout)
        self.assertEqual(len(self.popups), 1)

    def test_keyless_receiver_accepts_unsigned_message(self):
        self.server.key = None
        self.assertEqual(self.request(headers={"Content-Type": "application/json"})[0], 200)
        self.assertEqual(len(self.popups), 1)

    def test_send_without_keys_reports_success_count(self):
        self.server.key = None
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "send", "{}:{}".format(self.host, self.port), "Hello"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Finished: 1/1 targets accepted the notification; 0 failed.", result.stdout)
        self.assertEqual(len(self.popups), 1)


class LocalTests(unittest.TestCase):
    def test_popup_is_literal_and_never_runs_a_shell(self):
        data = {"title": "--help", "message": '<b>Hello</b> & $(touch /tmp/nope) "text"',
                "urgency": "normal", "duration": 8}
        with mock.patch.object(notify.subprocess, "run") as run:
            notify.show_popup(data)
        argv = run.call_args.args[0]
        self.assertEqual(argv[-3:], ["--", "--help", '&lt;b&gt;Hello&lt;/b&gt; &amp; $(touch /tmp/nope) "text"'])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_keygen_does_not_overwrite_and_uses_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "key"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(notify.main(["keygen", "--key-file", str(path)]), 0)
                original = path.read_bytes()
                self.assertEqual(len(notify.read_key(path)), 32)
                self.assertEqual(notify.main(["keygen", "--key-file", str(path)]), 1)
            self.assertEqual(path.read_bytes(), original)
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_invalid_and_missing_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "key"
            with self.assertRaisesRegex(ValueError, "not found"):
                notify.read_key(path)
            path.write_text("short", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "64 hexadecimal"):
                notify.read_key(path)

    def test_receiver_requires_linux_desktop_and_dependency(self):
        with mock.patch.object(notify.sys, "platform", "win32"):
            with self.assertRaisesRegex(ValueError, "Linux desktop"):
                notify.desktop_available()
        with mock.patch.object(notify.sys, "platform", "linux"), mock.patch.object(notify.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "notify-send is missing"):
                notify.desktop_available()
        with mock.patch.object(notify.sys, "platform", "linux"), mock.patch.object(notify.shutil, "which", return_value="/usr/bin/notify-send"), mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "No desktop session"):
                notify.desktop_available()

    def test_target_parsing(self):
        for target, expected in (("desktop", "http://desktop:8765/notify"),
                                 ("192.168.1.20:9000", "http://192.168.1.20:9000/notify"),
                                 ("https://example.test:443", "https://example.test:443/notify")):
            self.assertEqual(notify.target_url(target), expected)
        for target in ("", "ftp://host", "http://user:password@host", "host/path", "host?query", "host#fragment", "host:0", "host:65536"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                notify.target_url(target)

    def test_ipv4_ranges_and_lists(self):
        cases = (
            ("10.1-14.1.10", ["10.{}.1.10".format(a) for a in range(1, 15)]),
            ("10.42.1.(10,20,30,40)", ["10.42.1.{}".format(b) for b in (10, 20, 30, 40)]),
            ("10.1-2.1.10-11:9000", ["10.{}.1.{}:9000".format(a, b) for a in (1, 2) for b in (10, 11)]),
            ("https://10.(1,3).1.(10,20):443/", ["https://10.{}.1.{}:443".format(a, b) for a in (1, 3) for b in (10, 20)]),
            ("10.(1, 2-3,2).1.(0,255)", ["10.{}.1.{}".format(a, b) for a in (1, 2, 3) for b in (0, 255)]),
            ("10.(0,255).1.(10,20-21)", ["10.{}.1.{}".format(a, b) for a in (0, 255) for b in (10, 20, 21)]),
            ("office-pc.example.test", ["office-pc.example.test"]),
            ("[::1]:9000", ["[::1]:9000"]),
        )
        for target, expected in cases:
            with self.subTest(target=target):
                self.assertEqual(notify.expand_target(target), expected)

    def test_invalid_ranges_are_rejected_before_delivery(self):
        for target in ("10.13-1.1.10", "10.42.1.10-256", "10.42.1.(-1,2)",
                       "10.42.1.()", "10.42.1.(1,,2)", "10.42.1.1,2",
                       "10.42.1.(1,2", "10.42.1.1-2-3", "10-11.42.1.10",
                       "10.(1,2).1.10:0", "256.1-2.1.10", "10.1-256.1.10",
                       "10.().1.10", "10.1-2.256.10", "10.42.1-2.10",
                       "10.42.(1,2).10", "10.1-2.1-2.10"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                notify.expand_target(target)
        with mock.patch.object(notify, "send_one") as sender, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(notify.main(["all", "10.42.1.10", "Hello", "--also", "10.42.1.10-256"]), 1)
            sender.assert_not_called()

    def test_overlapping_targets_are_deduplicated(self):
        self.assertEqual(notify.expand_targets([
            "10.1-2.1.(10,10,20)", "10.2.1.10", "http://10.1.1.10:8765",
        ]), ["10.1.1.10", "10.1.1.20", "10.2.1.10", "10.2.1.20"])

    def test_second_octet_range_cli_sends_every_combination(self):
        with mock.patch.object(notify, "send_one", return_value=(True, "sent")) as sender, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(notify.main(["all", "10.13-14.1.(10,20)", "Hello"]), 0)
        self.assertCountEqual([call.args[0] for call in sender.call_args_list],
                              ["10.13.1.10", "10.13.1.20", "10.14.1.10", "10.14.1.20"])

    def test_all_uses_concurrent_deliveries_and_counts_failures(self):
        barrier = threading.Barrier(2)
        def deliver(target, key, body):
            self.assertIsNone(key)
            barrier.wait(timeout=3)
            return target.endswith("10"), target
        output = io.StringIO()
        with mock.patch.object(notify, "send_one", side_effect=deliver), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(notify.main(["all", "10.42.1.10-11", "Hello", "--workers", "2"]), 1)
        self.assertIn("Finished: 1/2 targets accepted the notification; 1 failed.", output.getvalue())

    def test_autostart_without_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(notify.sys, "platform", "linux"), mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(notify.main(["autostart"]), 0)
                entry = (Path(directory) / "autostart" / "notify.desktop").read_text()
                self.assertIn('"listen"', entry)
                self.assertNotIn("--key-file", entry)

    def test_autostart_enable_and_disable(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "key with spaces"
            key.write_text(KEY.hex(), encoding="ascii")
            with mock.patch.object(notify.sys, "platform", "linux"), mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(notify.main(["autostart", "--key-file", str(key), "--port", "9000"]), 0)
                entry = Path(directory) / "autostart" / "notify.desktop"
                text = entry.read_text(encoding="utf-8")
                self.assertIn('"listen"', text)
                self.assertIn('"9000"', text)
                self.assertIn("key with spaces", text)
                self.assertIn("Terminal=false", text)
                self.assertEqual(notify.main(["autostart", "--disable"]), 0)
                self.assertFalse(entry.exists())


if __name__ == "__main__":
    unittest.main()

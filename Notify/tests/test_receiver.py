import ast
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


NOTIFY_DIR = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_receiver", NOTIFY_DIR / "build_receiver.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "notify"
        self.source = builder.build_receiver()
        self.path.write_text(self.source, encoding="utf-8")
        loader = importlib.machinery.SourceFileLoader("notify_receiver", str(self.path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.receiver = importlib.util.module_from_spec(spec)
        loader.exec_module(self.receiver)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(self.path), *args],
                              capture_output=True, text=True, timeout=10)

    def test_deployed_executable_has_no_sender_or_key_generation(self):
        for name in ("send", "send_one", "signed_headers", "keygen", "expand_targets", "main"):
            self.assertFalse(hasattr(self.receiver, name), name)
        imports = [node for node in ast.walk(ast.parse(self.source))
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == "urllib.request"
                             for node in imports))
        help_result = self.run_cli("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("{listen,autostart}", help_result.stdout)
        for command in ("send", "all", "keygen"):
            with self.subTest(command=command):
                result = self.run_cli(command)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("invalid choice", result.stderr)

    def test_controller_can_deliver_to_standalone_receiver(self):
        key = Path(self.directory.name) / "key"
        key.write_text("ab" * 32, encoding="ascii")
        for authenticated in (False, True):
            with self.subTest(authenticated=authenticated):
                popups = []
                server = self.receiver.NotifyServer(
                    ("127.0.0.1", 0), self.receiver.read_key(key) if authenticated else None, popups.append)
                thread = threading.Thread(target=server.serve_forever,
                                          kwargs={"poll_interval": 0.01}, daemon=True)
                thread.start()
                try:
                    target = "{}:{}".format(*server.server_address)
                    argv = [sys.executable, str(NOTIFY_DIR / "notify"), "send", target,
                            "Controller message", "--duration", "15", "--urgency", "critical"]
                    if authenticated:
                        rejected = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                        self.assertEqual(rejected.returncode, 1, rejected.stderr)
                        self.assertIn("HTTP 401", rejected.stderr)
                        self.assertEqual(popups, [])
                        argv.extend(["--key-file", str(key)])
                    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(popups, [{"title": "Message", "message": "Controller message",
                                              "duration": 15, "urgency": "critical"}])
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)

    def test_receiver_autostart_uses_deployed_executable(self):
        config = Path(self.directory.name) / "config"
        key = Path(self.directory.name) / "key"
        key.write_text("ab" * 32, encoding="ascii")
        with mock.patch.object(self.receiver.sys, "platform", "linux"), \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(config)}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.receiver.receiver_main(
                ["autostart", "--key-file", str(key), "--port", "9000"]), 0)
            entry = config / "autostart" / "notify.desktop"
            text = entry.read_text(encoding="utf-8")
            self.assertIn(str(self.path), text)
            self.assertIn('"listen"', text)
            self.assertIn('"--key-file"', text)
            self.assertIn('"9000"', text)
            self.assertEqual(self.receiver.receiver_main(["autostart", "--disable"]), 0)
            self.assertFalse(entry.exists())

    def test_background_receiver_survives_launcher_and_delivers(self):
        fake_backend = Path(self.directory.name) / "notify-send"
        fake_backend.write_text('#!/bin/sh\ntouch "$NOTIFY_TEST_POPUP"\n', encoding="utf-8")
        fake_backend.chmod(0o755)
        marker = Path(self.directory.name) / "popup"
        environment = dict(os.environ, DISPLAY=":99", XDG_CONFIG_HOME=str(Path(self.directory.name) / "config"),
                           NOTIFY_TEST_POPUP=str(marker),
                           PATH=self.directory.name + os.pathsep + os.environ.get("PATH", ""))
        key = Path(self.directory.name) / "key"
        key.write_text("ab" * 32, encoding="ascii")
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        result = subprocess.run(
            [sys.executable, str(self.path), "listen", "--background", "--host", "127.0.0.1",
             "--port", str(port), "--key-file", str(key)],
            env=environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"PID (\d+)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        pid = int(match[1])
        try:
            self.assertTrue(self.receiver.listener_reachable("127.0.0.1", port))
            repeated = subprocess.run(
                [sys.executable, str(self.path), "listen", "--background", "--host", "127.0.0.1",
                 "--port", str(port)], env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertIn("already has a listener", repeated.stdout)
            delivery = subprocess.run(
                [sys.executable, str(NOTIFY_DIR / "notify"), "send", "127.0.0.1:{}".format(port),
                 "Background delivery", "--key-file", str(key)],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(delivery.returncode, 0, delivery.stderr)
            self.assertTrue(marker.exists())
        finally:
            os.kill(pid, signal.SIGTERM)

    def test_background_start_waits_for_login_without_spawning(self):
        with mock.patch.object(self.receiver, "desktop_environment", return_value={}), \
                mock.patch.object(self.receiver.subprocess, "Popen") as spawn, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.receiver.receiver_main(["listen", "--background", "--if-desktop"]), 0)
            spawn.assert_not_called()
        self.assertIn("next graphical login", output.getvalue())

    def test_background_start_reports_child_failure(self):
        with mock.patch.object(self.receiver, "desktop_environment", return_value={"DISPLAY": ":0"}), \
                mock.patch.object(self.receiver, "desktop_available"), \
                mock.patch.object(self.receiver, "listener_reachable", return_value=False), \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(Path(self.directory.name) / "config")}), \
                mock.patch.object(self.receiver.subprocess, "Popen") as spawn, \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            spawn.return_value.poll.return_value = 1
            self.assertEqual(self.receiver.receiver_main(["listen", "--background"]), 1)
        self.assertIn("Receiver failed to start", errors.getvalue())
        self.assertIn("receiver.log", errors.getvalue())

    def test_desktop_environment_uses_session_variables_only(self):
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}, clear=True), \
                mock.patch.object(self.receiver.sys, "platform", "linux"), \
                mock.patch.object(self.receiver.shutil, "which", return_value="/bin/systemctl"), \
                mock.patch.object(self.receiver.os, "getuid", return_value=1000), \
                mock.patch.object(self.receiver.Path, "exists", return_value=True), \
                mock.patch.object(self.receiver.subprocess, "run") as run:
            run.return_value.stdout = "DISPLAY=:0\nXAUTHORITY=$'/home/user/my auth'\nUNRELATED=ignored\n"
            environment = self.receiver.desktop_environment()
        self.assertEqual(environment["DISPLAY"], ":0")
        self.assertEqual(environment["XAUTHORITY"], "/home/user/my auth")
        self.assertEqual(environment["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/run/user/1000/bus")
        self.assertEqual(environment["XDG_CONFIG_HOME"], "/custom/config")
        self.assertNotIn("UNRELATED", environment)


if __name__ == "__main__":
    unittest.main()

import ast
import contextlib
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "eebus-bridge-vaillant-preview" / "import-eebus-identity.sh"
ADDON_NAME = "aa6fc4a7_eebus_bridge.tar.gz"


def make_backup(target: Path, *, omit: str | None = None) -> None:
    members = {
        "data/serial": b"0123456789abcdef",
        "data/certs/cert.pem": b"-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n",
        "data/certs/key.pem": b"-----BEGIN EC PRIVATE KEY-----\nFAKE\n-----END EC PRIVATE KEY-----\n",
    }
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as inner:
        for name, data in members.items():
            if name == omit:
                continue
            header = tarfile.TarInfo(name)
            header.size = len(data)
            inner.addfile(header, io.BytesIO(data))
    with tarfile.open(target, mode="w") as outer:
        data = payload.getvalue()
        header = tarfile.TarInfo(ADDON_NAME)
        header.size = len(data)
        outer.addfile(header, io.BytesIO(data))


class EebusIdentityBackupImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.backup = self.root / "backup.tar"
        self.data = self.root / "private"
        self.data.mkdir()

    def run_import(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.backup), str(self.data)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_restores_only_three_files_without_leaking_contents(self) -> None:
        make_backup(self.backup)
        result = self.run_import()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.data / "serial").read_bytes(), b"0123456789abcdef")
        self.assertTrue((self.data / "certs/cert.pem").is_file())
        self.assertTrue((self.data / "certs/key.pem").is_file())
        self.assertNotIn("0123456789abcdef", result.stdout + result.stderr)
        self.assertEqual(
            {str(f.relative_to(self.data)) for f in self.data.rglob("*") if f.is_file()},
            {"serial", "certs/cert.pem", "certs/key.pem"},
        )

    def test_refuses_missing_private_key_without_partial_restore(self) -> None:
        make_backup(self.backup, omit="data/certs/key.pem")
        result = self.run_import()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.data / "serial").exists())
        self.assertFalse((self.data / "certs").exists())

    def test_refuses_existing_identity_without_overwrite(self) -> None:
        make_backup(self.backup)
        (self.data / "serial").write_text("existing")
        result = self.run_import()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.data / "serial").read_text(), "existing")

    def test_refuses_missing_backup(self) -> None:
        result = self.run_import()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

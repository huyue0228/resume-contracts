import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.package import verify_wheel


class PackageTests(unittest.TestCase):
    def test_wheel_is_installed_locally_even_if_parent_has_same_version(self):
        wheel = Path("/tmp/resume-contracts-test.whl")
        with patch("tools.package.subprocess.run") as run, patch.dict(
            "os.environ", {"PYTHONPATH": "/inherited/source"}
        ):
            verify_wheel(wheel)

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 5)
        self.assertIn("--system-site-packages", commands[0])
        self.assertEqual(commands[1][1:], [
            "-m", "pip", "install", "--ignore-installed", "--no-deps",
            "--no-index", str(wheel),
        ])
        self.assertIn("source.relative_to(prefix)", commands[2][-1])
        self.assertEqual(commands[3][1:], ["-m", "resume_contracts.verify"])
        self.assertEqual(Path(commands[4][0]).parent, Path(commands[1][0]).parent)
        self.assertEqual(Path(commands[4][0]).name, "resume-kernel-mock")
        for call in run.call_args_list[1:]:
            self.assertNotIn("PYTHONPATH", call.kwargs["env"])
            self.assertTrue(call.kwargs["check"])

    def test_rejects_wheel_when_import_provenance_check_fails(self):
        failure = subprocess.CalledProcessError(1, ["python", "-c", "check-source"])
        with patch("tools.package.subprocess.run", side_effect=[None, None, failure]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                verify_wheel(Path("/tmp/resume-contracts-test.whl"))
        self.assertEqual(run.call_count, 3)


if __name__ == "__main__":
    unittest.main()

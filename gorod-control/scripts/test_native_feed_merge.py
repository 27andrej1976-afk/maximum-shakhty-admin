"""Compile and run the actual Android-independent native feed policy, without networking."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeFeedPolicyTest(unittest.TestCase):
    def test_native_feed_policy(self):
        java = shutil.which("java")
        self.assertIsNotNone(java, "Java is required for native policy regression checks")
        compiler = [shutil.which("javac")] if shutil.which("javac") else [java, "-m", "jdk.compiler/com.sun.tools.javac.Main"]
        with tempfile.TemporaryDirectory(prefix="native-feed-check-") as output:
            built = subprocess.run(compiler + ["-encoding", "UTF-8", "-Xlint:all", "-d", output,
                str(ROOT / "direct-v09/NativeFeedMerge.java"),
                str(ROOT / "direct-v09/NativeFeedMergeCheck.java")], text=True, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            checked = subprocess.run([java, "-cp", output, "NativeFeedMergeCheck"], text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("NATIVE FEED MERGE CHECKS PASSED", checked.stdout)
            print(checked.stdout.strip())


if __name__ == "__main__":
    unittest.main()

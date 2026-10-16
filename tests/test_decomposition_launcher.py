"""Only tiny inert Python subprocesses; never Julia, kernels or solvers."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("decomposition_launcher", ROOT / "scripts/run_decomposition_campaign.py")
LAUNCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCHER)


class DecompositionLauncherTests(unittest.TestCase):
    def run_python(self, source, **kwargs):
        with tempfile.TemporaryDirectory(prefix="decomposition-launcher-test-") as temporary:
            directory = Path(temporary)
            log = directory / "process.log"
            result = LAUNCHER.run_bounded([sys.executable, "-c", source], cwd=directory,
                environment=os.environ.copy(), log_path=log, execution_seconds=0.25,
                grace=0.1, log_limit=2048, **kwargs)
            return result, log.read_bytes()

    def test_normal_exit_and_eof(self):
        result, log = self.run_python("print('inert child completed')")
        self.assertEqual(result["returncode"],0)
        self.assertIsNone(result["stopped"])
        self.assertIn(b"inert child completed",log)
        self.assertIn(b"Launcher exit=0",log)

    def test_closed_stdout_exit_and_closed_stdout_timeout(self):
        result, _ = self.run_python("import os;os.close(1);os.close(2)")
        self.assertEqual(result["returncode"],0)
        self.assertIsNone(result["stopped"])
        result, log = self.run_python("import os,time;os.close(1);os.close(2);time.sleep(2)")
        self.assertIn("deadline",result["stopped"])
        self.assertNotEqual(result["returncode"],0)
        self.assertIn(b"no retries",log)

    def test_missing_or_unusable_stdout_is_owned_and_terminated(self):
        real_popen = subprocess.Popen
        for missing in (True,False):
            owned=[]
            def malformed_stdout(*args,**kwargs):
                process=real_popen(*args,**kwargs)
                owned.append(process)
                process.stdout.close()
                if missing:
                    process.stdout=None
                return process
            with self.subTest(missing=missing), patch.object(LAUNCHER.subprocess,"Popen",malformed_stdout):
                result, log=self.run_python("import time;time.sleep(2)")
            self.assertIsNotNone(result["stopped"])
            self.assertTrue(all(p.poll() is not None for p in owned))
            self.assertLessEqual(len(log),2048)

    def test_log_limit_stops_only_the_owned_group_and_its_descendant(self):
        with tempfile.TemporaryDirectory(prefix="decomposition-owned-group-") as temporary:
            directory=Path(temporary)
            pidfile=directory/"descendant.pid"
            source="""import os,subprocess,sys,time
p=subprocess.Popen([sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(2)'])
open(sys.argv[1],'w').write(str(p.pid))
print('x'*8192,flush=True)
time.sleep(2)
"""
            result=LAUNCHER.run_bounded([sys.executable,"-c",source,str(pidfile)],cwd=directory,
                environment=os.environ.copy(),log_path=directory/"process.log",
                execution_seconds=0.5,grace=0.1,log_limit=2048)
            self.assertEqual(result["stopped"],"process-log byte limit")
            self.assertLessEqual((directory/"process.log").stat().st_size,2048)
            pid=int(pidfile.read_text())
            status=Path(f"/proc/{pid}/status")
            deadline=time.monotonic()+1
            while status.exists() and "\nState:\tZ" not in status.read_text() and time.monotonic()<deadline:
                time.sleep(0.01)
            # A reaping zombie cannot execute. No process scan or unrelated PID kill.
            self.assertTrue(not status.exists() or "\nState:\tZ" in status.read_text())

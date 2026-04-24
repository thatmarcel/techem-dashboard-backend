from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


@contextmanager
def local_temp_dir():
    TEST_TMP_ROOT.mkdir(exist_ok=True)
    directory = TEST_TMP_ROOT / uuid.uuid4().hex
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)

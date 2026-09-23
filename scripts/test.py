import unittest
from pathlib import Path


def load_tests(loader, _tests, _pattern):
    scripts = Path(__file__).resolve().parent
    return loader.discover(start_dir=str(scripts / "tests"), top_level_dir=str(scripts.parent))


if __name__ == "__main__":
    unittest.main()

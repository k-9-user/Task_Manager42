import unittest

from scripts.tests.test_commands import CommandTests
from scripts.tests.test_config import ConfigTests
from scripts.tests.test_docker import DockerSafetyTests


__all__ = ["CommandTests", "ConfigTests", "DockerSafetyTests"]


if __name__ == "__main__":
    unittest.main()

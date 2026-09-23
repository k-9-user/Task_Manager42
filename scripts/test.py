import unittest

from scripts.tests.test_commands import CommandTests
from scripts.tests.test_config import ConfigTests
from scripts.tests.test_docker import DockerSafetyTests, RestoreTests


__all__ = ["CommandTests", "ConfigTests", "DockerSafetyTests", "RestoreTests"]


if __name__ == "__main__":
    unittest.main()

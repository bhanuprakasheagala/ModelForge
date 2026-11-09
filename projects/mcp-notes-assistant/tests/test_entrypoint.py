import importlib
import unittest
from unittest.mock import patch

package = importlib.reload(importlib.import_module("modelforge"))
package_entrypoint = package.main
server_module = importlib.import_module("modelforge.main")


class EntrypointTests(unittest.TestCase):
    def test_package_entrypoint_starts_mcp_server(self) -> None:
        with patch.object(server_module.mcp, "run") as run:
            package_entrypoint()

        run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

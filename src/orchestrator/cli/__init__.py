"""CLI package for orchestrator."""

from orchestrator.cli.mascot import MascotPose, SealMascot
from orchestrator.cli.seal_facts import get_random_seal_fact, SEAL_FACTS
from orchestrator.cli.welcome import WelcomeScreen

# Re-export main function from parent cli module for entry point compatibility
# The entry point script expects: orchestrator.cli:main
# We need to import from the parent module level, not from this package
import sys
import importlib.util

# Load the cli.py module from the parent directory
cli_module_path = __file__.replace("/__init__.py", ".py").replace("\\__init__.py", ".py")
spec = importlib.util.spec_from_file_location("orchestrator.cli_module", cli_module_path)
if spec and spec.loader:
    cli_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_module)
    main = cli_module.main
else:
    # Fallback: try importing from relative path
    from .. import cli as cli_module
    main = cli_module.main

__all__ = ["MascotPose", "SealMascot", "WelcomeScreen", "get_random_seal_fact", "SEAL_FACTS", "main"]

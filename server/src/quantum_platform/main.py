"""Entry point: ``uvicorn quantum_platform.main:app``."""

from quantum_platform.app import create_app
from quantum_platform.logging_config import configure_logging
from quantum_platform.settings import Settings

configure_logging()
app = create_app(Settings.from_env())

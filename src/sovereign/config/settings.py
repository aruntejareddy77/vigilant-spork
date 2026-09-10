"""
src/sovereign/config/settings.py
Application and security configuration settings using Pydantic Settings.
"""
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


DEFAULT_POLICY_PATH = Path(__file__).parent / "network_policy.yaml"


class WorkbenchSettings(BaseSettings):
    """Global configuration settings for Sovereign AI Workbench."""
    model_config = SettingsConfigDict(env_prefix="SOVEREIGN_", extra="ignore")

    app_name: str = "Sovereign AI Workbench"
    environment: str = "air-gap"
    dev_mode: bool = False
    mock_models: bool = False

    # Path to cryptographic audit ledger and index
    ledger_path: Path = Field(default=Path("audit_ledger.jsonl"))
    db_path: Path = Field(default=Path("audit_index.sqlite"))

    # Network policy path
    network_policy_path: Path = Field(default=DEFAULT_POLICY_PATH)

    # Telemetry streaming
    telemetry_host: str = "127.0.0.1"
    telemetry_port: int = 8765
    ring_buffer_capacity: int = 10000

    def load_network_policy_dict(self) -> dict:
        """Loads and parses the configured network policy YAML file."""
        p_path = Path(self.network_policy_path)
        if not p_path.exists():
            p_path = DEFAULT_POLICY_PATH
        with open(p_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

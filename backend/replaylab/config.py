import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("REPLAYLAB_DATA_DIR", ".replaylab")).resolve())
    public_demo: bool = field(default_factory=lambda: os.getenv("REPLAYLAB_PUBLIC_DEMO", "false").lower() == "true")
    secure_cookie: bool = field(default_factory=lambda: os.getenv("REPLAYLAB_SECURE_COOKIE", "false").lower() == "true")
    run_timeout: int = field(default_factory=lambda: int(os.getenv("REPLAYLAB_RUN_TIMEOUT", "480")))
    token_budget: int = field(default_factory=lambda: int(os.getenv("REPLAYLAB_TOKEN_BUDGET", "40000")))
    max_queued: int = field(default_factory=lambda: int(os.getenv("REPLAYLAB_MAX_QUEUED", "8")))
    api_key: str = field(default_factory=lambda: os.getenv("NEBIUS_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("NEBIUS_MODEL", ""))
    inference_url: str = field(default_factory=lambda: os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").rstrip("/"))
    sandbox_key: str = field(default_factory=lambda: os.getenv("CONTREE_API_KEY", ""))
    sandbox_url: str = field(default_factory=lambda: os.getenv("CONTREE_BASE_URL", ""))
    sandbox_image: str = field(default_factory=lambda: os.getenv("CONTREE_IMAGE", ""))
    project_id: str = field(default_factory=lambda: os.getenv("NEBIUS_PROJECT_ID", ""))

    @property
    def live_ready(self):
        return bool(self.api_key and self.model and self.sandbox_key and self.sandbox_url and self.sandbox_image)

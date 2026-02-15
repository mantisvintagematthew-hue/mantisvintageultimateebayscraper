from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    ebay_client_id: str
    ebay_client_secret: str
    ebay_marketplace: str
    database_url: str
    data_dir: Path



def get_settings() -> Settings:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    data_dir = Path(os.getenv("VTC_DATA_DIR", root / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        ebay_client_id=os.getenv("EBAY_CLIENT_ID", ""),
        ebay_client_secret=os.getenv("EBAY_CLIENT_SECRET", ""),
        ebay_marketplace=os.getenv("EBAY_MARKETPLACE", "EBAY_US"),
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{root / 'data' / 'vtc.db'}"),
        data_dir=data_dir,
    )

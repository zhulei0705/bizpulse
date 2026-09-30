from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.core.config import BASE_DIR, settings
from app.db.session import SessionLocal
from app.models.system import SystemConfig


def main() -> None:
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)

    config = Config(str(BASE_DIR / "alembic.ini"))
    command.upgrade(config, "head")

    with SessionLocal() as db:
        defaults = {
            "NO_FAKE_DATA": ("true" if settings.no_fake_data else "false", "禁止用虚假企业/商机数据填充正式业务库"),
            "PRODUCT_NAME": (settings.app_display_name, "产品名称"),
            "APP_ENV": (settings.app_env, "运行环境"),
        }
        for key, (value, description) in defaults.items():
            row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
            if row is None:
                db.add(SystemConfig(key=key, value=value, description=description))
            else:
                row.value = value
                row.description = description
        db.commit()

    print("BizPulse database initialized.")
    print(f"Environment: {settings.app_env}")
    print("NO_FAKE_DATA:", settings.no_fake_data)


if __name__ == "__main__":
    main()

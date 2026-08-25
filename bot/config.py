from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str
    ADMIN_IDS: str  # "111,222" -> parse qilinadi

    CHANNEL_ID: str
    CHANNEL_URL: str
    # 🧪 VAQTINCHALIK: bot hali kanalda admin qilinmagan bosqichda ro'yxatdan
    # o'tishni sinash uchun. Kanalga admin qilib qo'shilgach .env'da False qiling —
    # productionda albatta majburiy tekshiruv yoqilgan bo'lishi shart.
    SKIP_CHANNEL_CHECK: bool = False

    CARD_NUMBER: str
    CARD_OWNER: str

    TIMEZONE: str = "Asia/Tashkent"

    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.ADMIN_IDS.split(",") if x.strip()}

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()

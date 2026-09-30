from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    service: str
    environment: str


class SystemInfo(BaseModel):
    name: str
    version: str
    environment: str
    database: str
    no_fake_data: bool

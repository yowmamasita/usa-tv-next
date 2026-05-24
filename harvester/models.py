from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB = "github"
    WEBSITE = "website"
    TELEGRAM = "telegram"
    PASTE = "paste"
    DIRECT = "direct"


class SourceConfig(BaseModel):
    type: SourceType
    name: str = ""
    repo: str = ""
    paths: list[str] = Field(default_factory=lambda: ["*.m3u", "*.m3u8"])
    branch: str = "main"
    url: str = ""
    strategy: str = "link_scrape"
    channel: str = ""

    def source_id(self) -> str:
        match self.type:
            case SourceType.GITHUB:
                return f"github:{self.repo}"
            case SourceType.TELEGRAM:
                return f"telegram:{self.channel}"
            case _:
                return f"{self.type.value}:{self.name or self.url}"


class ParsedStream(BaseModel):
    url: str
    channel_name: str = ""
    group: str = ""
    tvg_id: str = ""
    tvg_logo: str = ""
    source_id: str = ""


class StreamStatus(str, Enum):
    WORKING = "working"
    DEAD = "dead"
    TIMEOUT = "timeout"


class CodecInfo(BaseModel):
    video: str = ""
    audio: str = ""
    resolution: str = ""
    bitrate: str = ""


class StreamTestResult(BaseModel):
    url: str
    status: StreamStatus
    channel_name: str = ""
    group: str = ""
    response_time_ms: int = 0
    codecs: CodecInfo = Field(default_factory=CodecInfo)
    sources: list[str] = Field(default_factory=list)
    tested_at: str = ""
    error: str = ""


class HarvestState(BaseModel):
    run_id: str = ""
    sources_completed: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    streams_collected: int = 0
    last_updated: str = ""


class TestState(BaseModel):
    run_id: str = ""
    tested_urls: dict[str, str] = Field(default_factory=dict)
    last_updated: str = ""


class Report(BaseModel):
    generated_at: str = ""
    summary: dict = Field(default_factory=dict)
    streams: list[StreamTestResult] = Field(default_factory=list)

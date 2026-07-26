import json
from enum import Enum
from loguru import logger


class SourceStatus(Enum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"


class HealthMonitor:
    def __init__(self):
        self._sources = {}

    def register(self, name):
        self._sources[name] = {
            "status": SourceStatus.PENDING,
            "articles": 0,
            "error": None,
            "attempts": 0,
        }

    def report(self, name, status, article_count=0, error=None, attempts=0):
        if name not in self._sources:
            self.register(name)
        self._sources[name] = {
            "status": status,
            "articles": article_count,
            "error": error,
            "attempts": attempts,
        }
        if status == SourceStatus.FAILED:
            logger.error(f"Source '{name}' marked FAILED: {error}")
        elif status == SourceStatus.OK:
            logger.success(f"Source '{name}' OK — {article_count} articles ({attempts} attempt(s)).")

    def is_healthy(self):
        return all(
            s["status"] == SourceStatus.OK for s in self._sources.values()
        )

    def failed_sources(self):
        return [n for n, s in self._sources.items() if s["status"] == SourceStatus.FAILED]

    def to_dict(self):
        return {
            name: {
                "status": s["status"].value,
                "articles": s["articles"],
                "error": s["error"],
                "attempts": s["attempts"],
            }
            for name, s in self._sources.items()
        }

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)
        logger.info(f"Health monitor saved to {path}")

    @staticmethod
    def load(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        monitor = HealthMonitor()
        for name, info in data.items():
            monitor.report(
                name,
                SourceStatus(info["status"]),
                info.get("articles", 0),
                info.get("error"),
                info.get("attempts", 0),
            )
        return monitor
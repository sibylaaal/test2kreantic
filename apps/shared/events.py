from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class DomainEvent:
    event_id: str
    schema_version: int
    event_name: str
    source: str
    occurred_at: str
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        event_name: str,
        source: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> "DomainEvent":
        return cls(
            event_id=str(uuid4()),
            schema_version=1,
            event_name=event_name,
            source=source,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            payload=payload,
            correlation_id=correlation_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

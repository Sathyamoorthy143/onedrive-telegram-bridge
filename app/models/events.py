
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid


@dataclass
class NormalizedEvent:
    channel: str
    sender_id: str
    chat_id: str
    text: str
    message_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to_message_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandRequest:
    name: str
    args: str
    raw_text: str
    event: NormalizedEvent


@dataclass
class CommandResponse:
    ok: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    should_mirror: bool = True
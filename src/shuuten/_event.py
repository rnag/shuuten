from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any
from uuid import uuid4


@dataclass
class Event:
    level: str              # 'ERROR' | 'WARNING' | 'INFO'
    title: str              # short human summary
    workflow: str           # 'slack-photo-sync'
    action: str             # 'upload_photo'
    env: str                # 'prod'
    run_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=time)

    # 'safe' identifiers (prefer IDs, not emails)
    subject_id: str | None = None

    # free-form structured context
    context: dict[str, Any] = field(default_factory=dict)

    # links / metadata
    source: str | None = None       # 'lambda:funcname' or 'ecs:cluster/service'
    log_url: str | None = None      # deep link to CW (optional)

"""Consent purposes.

Named, independently revocable, and denied by default without exception.
An enum rather than strings: a typo becomes an import error instead of a
silently ungated endpoint.
"""

from enum import StrEnum


class Purpose(StrEnum):
    ESSENTIAL = "essential"
    PERSONALIZATION = "personalization"
    AI_PROCESSING = "ai_processing"
    PINTEREST_SYNC = "pinterest_sync"
    CAMERA_PHOTOS = "camera_photos"
    LOCATION_WEATHER = "location_weather"
    AGENT_PROACTIVE = "agent_proactive"
    MARKETING_COMMS = "marketing_comms"
    ANALYTICS = "analytics"


#: Granted at registration. Covers only what the service cannot function without.
DEFAULT_GRANTED: frozenset[Purpose] = frozenset({Purpose.ESSENTIAL})

#: Sensitive category — requires explicit, separate consent (GDPR Art. 9 posture).
EXPLICIT_CONSENT_REQUIRED: frozenset[Purpose] = frozenset({Purpose.PERSONALIZATION})

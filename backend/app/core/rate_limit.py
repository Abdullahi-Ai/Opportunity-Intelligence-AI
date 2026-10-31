import time
import math
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from app.config import settings

class InMemoryRateLimiter:
    def __init__(self):
        self._records: Dict[str, List[float]] = {}

    def reset(self):
        self._records.clear()

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int = 60):
        if not settings.RATE_LIMITING_ENABLED:
            return

        now = time.time()
        cutoff = now - window_seconds

        timestamps = self._records.get(key, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= max_requests:
            retry_after = max(1, math.ceil(valid_timestamps[0] + window_seconds - now))
            self._records[key] = valid_timestamps
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                headers={"Retry-After": str(retry_after)}
            )

        valid_timestamps.append(now)
        self._records[key] = valid_timestamps

rate_limiter = InMemoryRateLimiter()

def get_client_identifier(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return f"token_{token[:20]}"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"

class RateLimitDependency:
    def __init__(self, max_requests: int, window_seconds: int = 60, prefix: str = "general"):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.prefix = prefix

    def __call__(self, request: Request):
        if not settings.RATE_LIMITING_ENABLED:
            return
        effective_max = self.max_requests if settings.APP_ENV in ["production", "prod"] else self.max_requests * 20
        ident = get_client_identifier(request)
        key = f"{self.prefix}:{ident}"
        rate_limiter.check_rate_limit(
            key=key,
            max_requests=effective_max,
            window_seconds=self.window_seconds
        )

limiter_auth = RateLimitDependency(max_requests=5, window_seconds=60, prefix="auth")
limiter_chat = RateLimitDependency(max_requests=20, window_seconds=60, prefix="chat")
limiter_discovery = RateLimitDependency(max_requests=60, window_seconds=60, prefix="discovery")

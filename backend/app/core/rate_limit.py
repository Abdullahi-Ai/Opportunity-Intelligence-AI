import time
import math
import logging
from typing import Dict, List, Optional
from fastapi import Request, HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

class InMemoryRateLimiter:
    """Local in-memory sliding-window rate limiter."""
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


class DistributedRateLimiter:
    """
    Hybrid Serverless Rate Limiter.
    If UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are set, uses HTTP-based
    distributed atomic pipeline across all serverless function instances.
    If not set (or if Upstash is temporarily unreachable), falls back transparently
    to local InMemoryRateLimiter.
    """
    def __init__(self, memory_fallback: Optional[InMemoryRateLimiter] = None):
        self.memory = memory_fallback or InMemoryRateLimiter()

    def is_distributed(self) -> bool:
        return bool(settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN)

    def reset(self):
        self.memory.reset()

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int = 60):
        if not settings.RATE_LIMITING_ENABLED:
            return

        if self.is_distributed():
            try:
                import httpx
                pipeline_url = f"{settings.UPSTASH_REDIS_REST_URL.rstrip('/')}/pipeline"
                headers = {"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"}
                commands = [
                    ["INCR", f"rl:{key}"],
                    ["EXPIRE", f"rl:{key}", window_seconds]
                ]
                with httpx.Client(timeout=1.5) as client:
                    resp = client.post(pipeline_url, json=commands, headers=headers)
                    if resp.status_code == 200:
                        results = resp.json()
                        count = results[0].get("result", 1)
                        if count > max_requests:
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail=f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds} seconds.",
                                headers={"Retry-After": str(window_seconds)}
                            )
                        return
                    else:
                        logger.warning(f"Upstash rate limit returned {resp.status_code}; falling back to memory.")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Upstash distributed rate limit check failed ({e}); falling back to in-memory.")

        self.memory.check_rate_limit(key=key, max_requests=max_requests, window_seconds=window_seconds)


rate_limiter = DistributedRateLimiter()

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

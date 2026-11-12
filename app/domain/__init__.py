"""Shared vocabulary and ports without an external service behind them (ADR-0002)."""

from app.domain._clock import Clock, FakeClock

__all__ = ["Clock", "FakeClock"]

"""Spending controls, usage limits, rate limiting, and automated budget safeguards.

Enforces:
- Hard spending ceiling at $20.00 tracked monthly spend (leaving a $5.00 buffer on the $25 budget)
- Per-business daily AI request limits (25 requests / day)
- Per-business monthly AI request limits (250 requests / month)
- Sliding-window rate limiting (5 requests / minute per business)
- Token and estimated compute cost accounting
- Fail-safe suspension if budget tracking state cannot be determined
- Billing cycle auto-reset preserving permanent historical records
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Official Pricing Constants
GEMINI_38_FLASH_INPUT_RATE = 0.75 / 1_000_000   # $0.75 per 1M input tokens
GEMINI_38_FLASH_OUTPUT_RATE = 3.75 / 1_000_000  # $3.75 per 1M output tokens
AGENT_RUNTIME_COMPUTE_RATE = 0.000035           # ~$0.000035 / sec compute estimate

# Budget Safeguards
MONTHLY_TARGET_BUDGET_USD = 25.00
AUTOMATIC_SUSPENSION_USD = 20.00  # $5.00 buffer for delayed infrastructure charges
DAILY_REQUEST_LIMIT_PER_BIZ = 25
MONTHLY_REQUEST_LIMIT_PER_BIZ = 250
RATE_LIMIT_PER_MINUTE = 5         # max requests in a 60-second sliding window


class BusinessUsageRecord(BaseModel):
    """Tracks consumption and request metrics for an individual business."""
    business_id: str
    current_day: str
    daily_request_count: int = 0
    current_month: str
    monthly_request_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    last_request_timestamp: float = 0.0


class SystemBudgetSummary(BaseModel):
    """Current state of system spending and budget safeguards."""
    current_month: str
    monthly_target_budget_usd: float = MONTHLY_TARGET_BUDGET_USD
    suspension_threshold_usd: float = AUTOMATIC_SUSPENSION_USD
    tracked_spending_usd: float = 0.0
    remaining_budget_before_suspension_usd: float = AUTOMATIC_SUSPENSION_USD
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_ai_requests: int = 0
    is_suspended: bool = False
    fail_safe_active: bool = False
    active_businesses_count: int = 0


class SpendingGuard:
    """Thread-safe spending guard protecting Google Cloud budget with hard limits."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_month = self._get_current_month_key()
        self._current_day = self._get_current_day_key()
        self._tracked_spending_usd = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_ai_requests = 0
        self._is_suspended = False
        self._fail_safe_forced = False
        
        # Per-business records: business_id -> BusinessUsageRecord
        self._business_records: dict[str, BusinessUsageRecord] = {}
        # Sliding rate limit timestamps: business_id -> list of float timestamps
        self._rate_limit_windows: dict[str, list[float]] = {}
        # Historical archives: month_key -> dict of archived summaries
        self._historical_archives: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _get_current_month_key() -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"

    @staticmethod
    def _get_current_day_key() -> str:
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}-{now.day:02d}"

    def check_and_reset_billing_cycle(self) -> None:
        """Automatically reset allowances on monthly rollover while archiving history."""
        current_m = self._get_current_month_key()
        if current_m != self._current_month:
            logger.info("New billing month detected (%s -> %s). Archiving previous month.", self._current_month, current_m)
            # Archive previous month
            self._historical_archives[self._current_month] = {
                "month": self._current_month,
                "final_spend_usd": self._tracked_spending_usd,
                "total_input_tokens": self._total_input_tokens,
                "total_output_tokens": self._total_output_tokens,
                "total_requests": self._total_ai_requests,
                "business_records": {bid: rec.model_dump() for bid, rec in self._business_records.items()},
                "archived_at": datetime.now(timezone.utc).isoformat(),
            }
            # Reset counters for the new billing cycle
            self._current_month = current_m
            self._tracked_spending_usd = 0.0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._total_ai_requests = 0
            self._is_suspended = False
            for rec in self._business_records.values():
                rec.current_month = current_m
                rec.monthly_request_count = 0

    def can_proceed(self, business_id: str) -> tuple[bool, str | None]:
        """Check if request is permitted under rate, daily, monthly, and spending limits."""
        with self._lock:
            # 1. Billing cycle reset check
            self.check_and_reset_billing_cycle()

            # 2. Fail-safe behavior check
            if self._fail_safe_forced:
                return False, "⚠️ **Fail-Safe Active**: Spending guard cannot verify budget availability. Billable AI generation is temporarily disabled to prevent unexpected cloud charges."

            # 3. Automatic system suspension check ($20.00 hard limit)
            if self._is_suspended or self._tracked_spending_usd >= AUTOMATIC_SUSPENSION_USD:
                self._is_suspended = True
                return False, (
                    f"⚠️ **Monthly Budget Safeguard Triggered**: Tracked AI spending has reached ${self._tracked_spending_usd:.2f}, "
                    f"hitting the ${AUTOMATIC_SUSPENSION_USD:.2f} safety threshold (with $5.00 buffer reserved for delayed cloud infrastructure charges). "
                    f"Billable AI generation is automatically suspended until the next billing cycle."
                )

            # 4. Sliding rate limit check (max 5 requests per 60 seconds)
            now = time.time()
            window = self._rate_limit_windows.setdefault(business_id, [])
            # Prune timestamps older than 60 seconds
            self._rate_limit_windows[business_id] = [t for t in window if now - t < 60.0]
            if len(self._rate_limit_windows[business_id]) >= RATE_LIMIT_PER_MINUTE:
                return False, f"⚠️ **Rate Limit Exceeded**: Maximum {RATE_LIMIT_PER_MINUTE} AI requests per minute. Please wait a moment before sending another message."

            # 5. Resolve business usage record
            current_day = self._get_current_day_key()
            record = self._business_records.get(business_id)
            if not record:
                record = BusinessUsageRecord(
                    business_id=business_id,
                    current_day=current_day,
                    current_month=self._current_month,
                )
                self._business_records[business_id] = record
            else:
                # Reset daily counter if a new day
                if record.current_day != current_day:
                    record.current_day = current_day
                    record.daily_request_count = 0
                # Reset monthly counter if new month
                if record.current_month != self._current_month:
                    record.current_month = self._current_month
                    record.monthly_request_count = 0

            # 6. Per-business daily limit check
            if record.daily_request_count >= DAILY_REQUEST_LIMIT_PER_BIZ:
                return False, f"⚠️ **Daily Limit Reached**: Beta allowance of {DAILY_REQUEST_LIMIT_PER_BIZ} AI requests for today has been reached. Daily usage resets at midnight UTC."

            # 7. Per-business monthly limit check
            if record.monthly_request_count >= MONTHLY_REQUEST_LIMIT_PER_BIZ:
                return False, f"⚠️ **Monthly Limit Reached**: Beta allowance of {MONTHLY_REQUEST_LIMIT_PER_BIZ} AI requests for this billing cycle has been reached."

            # Record timestamp for rate limit window
            self._rate_limit_windows[business_id].append(now)
            return True, None

    def record_usage(
        self,
        business_id: str,
        input_tokens: int,
        output_tokens: int,
        compute_duration_sec: float = 1.0,
    ) -> float:
        """Account for token usage and compute cost, updating limits and triggering suspension if necessary."""
        with self._lock:
            # Calculate cost
            token_cost = (input_tokens * GEMINI_38_FLASH_INPUT_RATE) + (output_tokens * GEMINI_38_FLASH_OUTPUT_RATE)
            compute_cost = compute_duration_sec * AGENT_RUNTIME_COMPUTE_RATE
            total_call_cost = token_cost + compute_cost

            # Update system aggregates
            self._tracked_spending_usd += total_call_cost
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens
            self._total_ai_requests += 1

            # Update business record
            current_day = self._get_current_day_key()
            record = self._business_records.setdefault(
                business_id,
                BusinessUsageRecord(
                    business_id=business_id,
                    current_day=current_day,
                    current_month=self._current_month,
                ),
            )
            if record.current_day != current_day:
                record.current_day = current_day
                record.daily_request_count = 0
            if record.current_month != self._current_month:
                record.current_month = self._current_month
                record.monthly_request_count = 0

            record.daily_request_count += 1
            record.monthly_request_count += 1
            record.total_input_tokens += input_tokens
            record.total_output_tokens += output_tokens
            record.estimated_cost_usd += total_call_cost
            record.last_request_timestamp = time.time()

            # Check if threshold reached
            if self._tracked_spending_usd >= AUTOMATIC_SUSPENSION_USD:
                self._is_suspended = True
                logger.warning(
                    "AUTOMATIC SPENDING SUSPENSION TRIGGERED: Tracked spend reached $%.4f (threshold $%.2f)",
                    self._tracked_spending_usd,
                    AUTOMATIC_SUSPENSION_USD,
                )

            return total_call_cost

    def get_system_summary(self) -> SystemBudgetSummary:
        """Return system-wide budget status and safeguard metrics."""
        with self._lock:
            remaining = max(0.0, AUTOMATIC_SUSPENSION_USD - self._tracked_spending_usd)
            return SystemBudgetSummary(
                current_month=self._current_month,
                tracked_spending_usd=round(self._tracked_spending_usd, 4),
                remaining_budget_before_suspension_usd=round(remaining, 4),
                total_input_tokens=self._total_input_tokens,
                total_output_tokens=self._total_output_tokens,
                total_ai_requests=self._total_ai_requests,
                is_suspended=self._is_suspended,
                fail_safe_active=self._fail_safe_forced,
                active_businesses_count=len(self._business_records),
            )

    def get_business_usage(self, business_id: str) -> dict[str, Any]:
        """Return business-specific quota usage and limits."""
        with self._lock:
            current_day = self._get_current_day_key()
            record = self._business_records.get(business_id)
            daily_used = record.daily_request_count if record and record.current_day == current_day else 0
            monthly_used = record.monthly_request_count if record and record.current_month == self._current_month else 0
            est_cost = record.estimated_cost_usd if record else 0.0

            return {
                "business_id": business_id,
                "daily_requests_used": daily_used,
                "daily_requests_limit": DAILY_REQUEST_LIMIT_PER_BIZ,
                "daily_requests_remaining": max(0, DAILY_REQUEST_LIMIT_PER_BIZ - daily_used),
                "monthly_requests_used": monthly_used,
                "monthly_requests_limit": MONTHLY_REQUEST_LIMIT_PER_BIZ,
                "monthly_requests_remaining": max(0, MONTHLY_REQUEST_LIMIT_PER_BIZ - monthly_used),
                "total_input_tokens": record.total_input_tokens if record else 0,
                "total_output_tokens": record.total_output_tokens if record else 0,
                "estimated_cost_usd": round(est_cost, 4),
                "system_is_suspended": self._is_suspended,
            }

    def set_fail_safe_mode(self, enabled: bool) -> None:
        """Simulate or enforce fail-safe mode when spending cannot be reliably verified."""
        with self._lock:
            self._fail_safe_forced = enabled

    def simulate_spending_increase(self, additional_usd: float) -> None:
        """Simulate spending increase to test automatic suspension safeguards."""
        with self._lock:
            self._tracked_spending_usd += additional_usd
            if self._tracked_spending_usd >= AUTOMATIC_SUSPENSION_USD:
                self._is_suspended = True

    def reset_for_testing(self) -> None:
        """Reset state for unit and integration tests."""
        with self._lock:
            self._tracked_spending_usd = 0.0
            self._total_input_tokens = 0
            self._total_output_tokens = 0
            self._total_ai_requests = 0
            self._is_suspended = False
            self._fail_safe_forced = False
            self._business_records.clear()
            self._rate_limit_windows.clear()
            self._historical_archives.clear()


# Global singleton instance
_SPENDING_GUARD: SpendingGuard | None = None


def get_spending_guard() -> SpendingGuard:
    """Return default thread-safe SpendingGuard singleton."""
    global _SPENDING_GUARD
    if _SPENDING_GUARD is None:
        _SPENDING_GUARD = SpendingGuard()
    return _SPENDING_GUARD

from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from ..schemas.contracts import IndexCashTone
from ..schemas.inputs import (
    AttachedVisuals,
    ChallengeState,
    EventCalendarEntry,
    OpeningType,
)


class CompilerStrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class HistoricalBar(CompilerStrictModel):
    timestamp: AwareDatetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @model_validator(mode="after")
    def validate_ohlcv(self) -> "HistoricalBar":
        if self.high < self.low:
            raise ValueError("Historical bars require high >= low.")
        if not self.low <= self.open <= self.high:
            raise ValueError("Historical bars require open to be inside the high/low range.")
        if not self.low <= self.close <= self.high:
            raise ValueError("Historical bars require close to be inside the high/low range.")
        if self.volume <= 0:
            raise ValueError("Historical bars require volume > 0.")
        return self


class ESHistoricalDataInput(CompilerStrictModel):
    contract: Literal["ES"] = "ES"
    prior_rth_bars: list[HistoricalBar]
    overnight_bars: list[HistoricalBar]
    current_rth_bars: list[HistoricalBar]
    weekly_open_bar: HistoricalBar

    @staticmethod
    def _validate_strictly_ascending(field_name: str, bars: list[HistoricalBar]) -> None:
        if not bars:
            raise ValueError(f"{field_name} must contain at least one bar.")
        timestamps = [bar.timestamp for bar in bars]
        if len(set(timestamps)) != len(timestamps):
            raise ValueError(f"{field_name} must not contain duplicate timestamps.")
        if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
            raise ValueError(f"{field_name} must be strictly timestamp-ascending.")

    @model_validator(mode="after")
    def validate_bar_sets(self) -> "ESHistoricalDataInput":
        for field_name in ("prior_rth_bars", "overnight_bars", "current_rth_bars"):
            self._validate_strictly_ascending(field_name, getattr(self, field_name))

        current_session_dates = {bar.timestamp.date() for bar in self.current_rth_bars}
        if len(current_session_dates) != 1:
            raise ValueError("current_rth_bars must all fall on one session date.")
        current_session_date = next(iter(current_session_dates))

        prior_session_dates = {bar.timestamp.date() for bar in self.prior_rth_bars}
        if len(prior_session_dates) != 1:
            raise ValueError("prior_rth_bars must all represent one prior session date.")
        prior_session_date = next(iter(prior_session_dates))
        if prior_session_date >= current_session_date:
            raise ValueError("prior_rth_bars must represent a date before current_rth_bars.")

        prior_session_end = self.prior_rth_bars[-1].timestamp
        current_session_start = self.current_rth_bars[0].timestamp
        if self.weekly_open_bar.timestamp > current_session_start:
            raise ValueError("weekly_open_bar timestamp must not be after the first current_rth_bar.")
        if prior_session_end >= current_session_start:
            raise ValueError("prior_rth_bars must end before current_rth_bars begin.")
        if self.overnight_bars[0].timestamp <= prior_session_end:
            raise ValueError("overnight_bars must start after prior_rth_bars end.")
        if self.overnight_bars[-1].timestamp >= current_session_start:
            raise ValueError("overnight_bars must end before current_rth_bars begin.")
        if any(bar.timestamp <= prior_session_end for bar in self.overnight_bars):
            raise ValueError(
                "overnight_bars must fall strictly after prior_rth_bars and before current_rth_bars."
            )
        if any(bar.timestamp >= current_session_start for bar in self.overnight_bars):
            raise ValueError(
                "overnight_bars must fall strictly after prior_rth_bars and before current_rth_bars."
            )
        return self


class ESManualOverlayInput(CompilerStrictModel):
    contract: Literal["ES"] = "ES"
    challenge_state: ChallengeState
    attached_visuals: AttachedVisuals = Field(default_factory=AttachedVisuals)
    current_session_vah: float
    current_session_val: float
    current_session_poc: float
    previous_session_vah: float
    previous_session_val: float
    previous_session_poc: float
    avg_20d_session_range: float
    cumulative_delta: float
    current_volume_vs_average: float
    opening_type: OpeningType
    major_higher_timeframe_levels: list[float] | None = Field(default=None, max_length=5)
    key_hvns: list[float] | None = Field(default=None, max_length=3)
    key_lvns: list[float] | None = Field(default=None, max_length=3)
    singles_excess_poor_high_low_notes: str | None = None
    event_calendar_remainder: list[EventCalendarEntry]
    cross_market_context: dict[str, Any] | None = None
    data_quality_flags: list[str] = Field(default_factory=list)
    breadth: str
    index_cash_tone: IndexCashTone

"""Validated, immutable domain records shared by the engine and SQLite."""
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

DENVER = ZoneInfo("America/Denver")
Rating = Annotated[int, Field(ge=0, le=10)]
Miles = Annotated[float, Field(ge=0, le=50, allow_inf_nan=False)]
Minutes = Annotated[int, Field(ge=0, le=600)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1


class Athlete(Record):
    athlete_id: Identifier = "synthetic-athlete"
    timezone: Literal["America/Denver"] = "America/Denver"
    email_time: time = time(6)
    clearance: Literal["unknown", "no", "yes"] = "unknown"


class Cycle(Record):
    cycle_id: Identifier
    athlete_id: Identifier
    start: date
    status: Literal["draft", "pilot", "active", "paused", "completed"] = "pilot"
    template_version: Literal["1.0.0"] = "1.0.0"

    @property
    def end(self) -> date:
        return self.start + timedelta(days=83)

    def day(self, when: date) -> int:
        day = (when - self.start).days + 1
        if not 1 <= day <= 84:
            raise ValueError("Date is outside this 84-day cycle.")
        return day


class Kind(StrEnum):
    REST = "Rest"
    EASY_RUN = "Easy run"
    INTERVALS = "Controlled intervals"
    BOULDER = "Bouldering strength"
    TECHNIQUE = "Climbing technique"
    ROUTES = "Route training"
    PAIRS = "Power endurance"
    PROJECT = "Projecting"
    ASSESS = "Taper assessment"


HARD_FINGER = frozenset({Kind.BOULDER, Kind.ROUTES, Kind.PAIRS, Kind.PROJECT, Kind.ASSESS})
CLIMBING = HARD_FINGER | {Kind.TECHNIQUE}


class Session(Record):
    kind: Kind
    minutes: Minutes
    miles: Miles = 0
    strength_sets: Literal[0, 2, 3] = 0
    effort_minutes: Literal[0, 1, 2, 3] = 0
    attempts: int = Field(default=0, ge=0, le=20)
    continuous_minutes: int = Field(default=0, ge=0, le=20)


class CheckinData(Record):
    completion: Literal["full", "partial", "missed", "rest_done"]
    energy: Literal["good", "okay", "poor"]
    discomfort: Literal["none", "mild", "significant_or_worsening"]
    area: Literal["finger", "shoulder", "tendon", "other"] | None = None
    symptom: Literal["none", "illness", "chest_or_breathing", "unsafe_movement"] = "none"
    sleep: Literal["good", "okay", "poor"] | None = None
    duration: Minutes | None = None
    miles: Miles | None = None
    rpe: Annotated[int, Field(ge=1, le=10)] | None = None
    pump: Rating | None = None
    late_technique: Literal["steady", "faded"] | None = None
    nutrition: Literal["well_fueled", "under_fueled", "unknown"] = "unknown"
    strength_done: bool | None = None
    low_load_hang_minutes: Annotated[int, Field(ge=0, le=30)] | None = None
    reduce_next: bool = False

    @model_validator(mode="after")
    def consistent(self):
        if self.area and self.discomfort == "none":
            raise ValueError("Choose a discomfort level before recording an area.")
        if self.completion in {"missed", "rest_done"} and (
            self.rpe is not None or self.pump is not None or self.duration or self.miles
            or self.late_technique or self.strength_done or self.low_load_hang_minutes
        ):
            raise ValueError("Workout metrics require a full or partial session.")
        return self


class Checkin(Record):
    checkin_id: str
    prescription_id: str
    local_date: date
    submitted_at: AwareDatetime
    revision: int = Field(ge=1)
    data: CheckinData


class Nutrition(Record):
    day_class: Literal["rest", "moderate", "hard"]
    protein_g: int
    carbs_g: int
    fat_g: int
    status: Literal["provisional"] = "provisional"
    confidence: Literal["low"] = "low"

    @property
    def kcal(self) -> int:
        return 4 * (self.protein_g + self.carbs_g) + 9 * self.fat_g


class Decision(Record):
    readiness: Literal["green", "yellow", "red"]
    reason_codes: tuple[str, ...]
    inputs: tuple[tuple[str, datetime], ...]
    previous_missing: bool
    review_required: bool
    manual_override: bool
    confidence: Literal["low", "moderate"]
    rule_version: Literal["1.0.0"] = "1.0.0"


class Prescription(Record):
    prescription_id: str
    cycle_id: Identifier
    local_date: date
    created_at: AwareDatetime
    week: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=84)
    template_version: str
    baseline: Session
    session: Session
    decision: Decision
    nutrition: Nutrition
    lesson_id: str
    lesson: str

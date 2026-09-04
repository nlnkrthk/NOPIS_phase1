from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, date
from typing import List, Optional

# 132. Use a Pydantic response model.
class NetworkSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_activity: float
    active_grids: int
    peak_hour: int
    top_grid: int
    from_dt: datetime
    to_dt: datetime

# 137. Return the activity time series and the derived measures.
class GridActivityPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    timestamp: datetime
    date: date
    hour: int
    sms_in: float
    sms_out: float
    call_in: float
    call_out: float
    internet_activity: float
    total_sms: float
    total_calls: float
    total_activity: float
    internet_share: float

# 143. Design the response shape so ML risk fields can be added later without breaking the React client.
# 144. Include grid_id, hourly timestamp, the relevant activity measures, status or severity, and a human-readable reason.
class HotspotItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    timestamp: datetime
    total_activity: float
    sms_activity: float
    call_activity: float
    internet_activity: float
    severity: str
    reason: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    model_version: Optional[str] = None

class AlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    timestamp: datetime
    alert_type: str
    severity: str
    total_activity: float
    sms_activity: float
    call_activity: float
    internet_activity: float
    reason: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    model_version: Optional[str] = None

# 146. Return the exact ML2 feature set: avg_activity, activity_growth, active_hours, peak_ratio, variability, internet_share, plus feature_timestamp.
# 147. Define a stable Pydantic schema — this contract is consumed by ML5, RE5 and the Claude tools, and changing it later breaks three consumers.
# 148. Return data-quality status and feature freshness alongside the values.
class GridFeaturesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    feature_timestamp: datetime
    avg_activity: float
    activity_growth: float
    active_hours: int
    peak_ratio: float
    variability: float
    internet_share: float
    data_quality_status: str
    freshness_hours: float
    is_fresh: bool

# 150. Create POST /network/predict-risk with a Pydantic request model.
# 154. Keep the endpoint contract unchanged when replacing stub with ML model.
class PredictRiskRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int = Field(..., ge=1, le=10000, description="Grid identifier (valid range: 1–10000)")
    model_version: Optional[str] = Field(None, description="Optional model version from the model catalog")
    as_of: Optional[datetime] = Field(None, description="Optional reporting reference timestamp")
    avg_activity: Optional[float] = Field(None, ge=0.0, description="Optional feature: average activity")
    activity_growth: Optional[float] = Field(None, description="Optional feature: activity growth rate")
    active_hours: Optional[int] = Field(None, ge=0, le=24, description="Optional feature: active hours count")
    peak_ratio: Optional[float] = Field(None, ge=0.0, description="Optional feature: peak activity ratio")
    variability: Optional[float] = Field(None, ge=0.0, description="Optional feature: activity variability")
    internet_share: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optional feature: internet traffic share")

# 151. Return a stub risk_score, risk_level, model_version and explanation_note stating that the implementation is currently a stub.
class PredictRiskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Predicted operational risk probability score (0.0 - 1.0)")
    risk_level: str = Field(..., description="Categorical risk classification (LOW, MEDIUM, HIGH, CRITICAL)")
    model_version: str = Field(..., description="Identifier of the serving model version (stub marked clearly)")
    prediction_timestamp: datetime = Field(..., description="Timestamp when prediction was evaluated")
    explanation_note: str = Field(..., description="Human-readable explanation of risk assessment and anomaly context")
    is_stub: bool = Field(False, description="Boolean flag indicating whether response is from a stub implementation")

class AvailableModelResponse(BaseModel):
    model_version: str
    model_type: str
    features: List[str]



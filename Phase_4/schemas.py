from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import List, Optional

# 132. Use a Pydantic response model.
class NetworkSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_activity: float
    active_grids: int
    peak_hour: int
    top_grid: int
    as_of: datetime

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


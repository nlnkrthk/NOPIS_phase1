import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Path
from sqlalchemy.exc import SQLAlchemyError

try:
    from Phase_4.database import SessionLocal
    from Phase_4.schemas import NetworkSummaryResponse, GridActivityPoint, HotspotItem, AlertItem, GridFeaturesResponse
    from Phase_4.services import get_network_summary, get_grid_activity, get_hotspots, get_alerts, get_grid_features
except ModuleNotFoundError:
    from database import SessionLocal
    from schemas import NetworkSummaryResponse, GridActivityPoint, HotspotItem, AlertItem, GridFeaturesResponse
    from services import get_network_summary, get_grid_activity, get_hotspots, get_alerts, get_grid_features

router = APIRouter(prefix="/network", tags=["Network"])

# 129. Create GET /network/summary.
@router.get("/summary", response_model=NetworkSummaryResponse)
def network_summary(as_of: Optional[datetime] = Query(None, description="Optional ISO datetime reporting timestamp (e.g. YYYY-MM-DDTHH:MM:SS). If omitted, defaults to MAX(timestamp) in analytics.")):
    db = SessionLocal()
    try:
        summary = get_network_summary(db, as_of=as_of)
        if summary is None:
            raise HTTPException(
                status_code=404, 
                detail="No analytics data found for the requested as_of timestamp"
            )
        # 134. Return clear 500 errors when the data source is unavailable, and include the effective as_of in every successful response.
        return summary
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()

# 135. Create GET /network/grid/{grid_id}.
@router.get("/grid/{grid_id}", response_model=List[GridActivityPoint])
def grid_activity(
    grid_id: int = Path(..., description="Grid identifier (valid range: 1–10000)"),
    date: Optional[date] = Query(None, description="Optional date filter (YYYY-MM-DD)"),
    hour: Optional[int] = Query(None, ge=0, le=23, description="Optional hour filter (0-23)"),
    as_of: Optional[datetime] = Query(None, description="Optional reference as_of timestamp")
):
    # 138. Return 404 for an unknown grid — and treat any grid_id outside 1–10000 as unknown.
    if grid_id < 1 or grid_id > 10000:
        raise HTTPException(
            status_code=404, 
            detail=f"Grid {grid_id} not found. Valid grid IDs are in the range 1–10000."
        )

    db = SessionLocal()
    try:
        activity = get_grid_activity(
            db=db, 
            grid_id=grid_id, 
            filter_date=date, 
            filter_hour=hour, 
            as_of=as_of
        )
        if activity is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Grid {grid_id} not found in the reference grid registry."
            )
        return activity
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()

# 140. Create GET /network/hotspots and GET /network/alerts.
# 141.Allow limit, severity and as_of query parameters.
@router.get("/hotspots", response_model=List[HotspotItem])
def network_hotspots(
    limit: int = Query(10, ge=1, le=500, description="Maximum number of hotspot entries to return"),
    as_of: Optional[datetime] = Query(None, description="Optional reporting timestamp (e.g. YYYY-MM-DDTHH:MM:SS)")
):
    db = SessionLocal()
    try:
        hotspots = get_hotspots(db=db, limit=limit, as_of=as_of)
        return hotspots
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()

@router.get("/alerts", response_model=List[AlertItem])
def network_alerts(
    limit: int = Query(20, ge=1, le=500, description="Maximum number of alerts to return"),
    severity: Optional[str] = Query(None, description="Optional filter by severity level (e.g. CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    as_of: Optional[datetime] = Query(None, description="Optional reporting timestamp (e.g. YYYY-MM-DDTHH:MM:SS)")
):
    db = SessionLocal()
    try:
        alerts = get_alerts(db=db, limit=limit, severity=severity, as_of=as_of)
        return alerts
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()

# 145. Create GET /network/grid/{grid_id}/features.
@router.get("/grid/{grid_id}/features", response_model=GridFeaturesResponse)
def grid_features(
    grid_id: int = Path(..., description="Grid identifier to fetch ML-ready feature vector")
):
    if grid_id < 1 or grid_id > 10000:
        raise HTTPException(
            status_code=404,
            detail=f"Grid {grid_id} not found. Valid grid IDs are in the range 1–10000."
        )

    db = SessionLocal()
    try:
        features = get_grid_features(db=db, grid_id=grid_id)
        if features is None:
            raise HTTPException(
                status_code=404,
                detail=f"No stored ML features found for grid {grid_id}"
            )
        return features
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database unavailable"
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
    finally:
        db.close()


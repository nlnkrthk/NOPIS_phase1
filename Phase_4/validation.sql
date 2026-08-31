-- =============================================================================
-- NOPIS Phase 4: API1 Network Summary Validation Queries
-- Run these SQL statements in MySQL to validate the /network/summary API response.
-- =============================================================================

USE nopis;

-- 1. Discover the default as_of timestamp (maximum timestamp in analytics layer)
SELECT MAX(t.timestamp) AS default_as_of
FROM dim_time t
JOIN fact_network_activity f ON f.time_key = t.time_key;

-- Set a variable for the effective as_of timestamp (replace with result from query 1 or your test timestamp)
-- Example: SET @as_of = (SELECT MAX(t.timestamp) FROM dim_time t JOIN fact_network_activity f ON f.time_key = t.time_key);
SET @as_of = (SELECT MAX(t.timestamp) FROM dim_time t JOIN fact_network_activity f ON f.time_key = t.time_key);

-- 2. Validate total_activity for the effective as_of
SELECT SUM(f.total_activity) AS total_activity
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.timestamp = @as_of;

-- 3. Validate active_grids for the effective as_of
SELECT COUNT(DISTINCT f.grid_id) AS active_grids
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.timestamp = @as_of;

-- 4. Validate peak_hour across the reporting analytics dataset
SELECT t.hour, SUM(f.total_activity) AS activity
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
GROUP BY t.hour
ORDER BY activity DESC
LIMIT 1;

-- 5. Validate top_grid for the effective as_of
SELECT f.grid_id AS top_grid, SUM(f.total_activity) AS activity
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.timestamp = (SELECT MAX(t.timestamp) FROM dim_time t JOIN fact_network_activity f ON f.time_key = t.time_key)
GROUP BY f.grid_id
ORDER BY activity DESC
LIMIT 1;

-- =============================================================================
-- API2 — Grid Activity Drill-Down Validation Queries
-- =============================================================================

-- 139. Validate the results against SQL.
-- 6. Validate Grid 4821 default window (trailing 24 hourly intervals ending at AS_OF)
SELECT * FROM (
    SELECT 
        f.grid_id,
        t.timestamp,
        t.date,
        t.hour,
        f.sms_in,
        f.sms_out,
        f.call_in,
        f.call_out,
        f.internet_activity,
        f.total_sms,
        f.total_calls,
        f.total_activity,
        f.internet_share
    FROM fact_network_activity f
    JOIN dim_time t ON f.time_key = t.time_key
    WHERE f.grid_id = 4821
      AND t.timestamp <= (SELECT MAX(timestamp) FROM dim_time)
    ORDER BY t.timestamp DESC
    LIMIT 24
) sub
ORDER BY sub.timestamp ASC;

-- 7. Spot check one specific hour for Grid 4821
SELECT 
    f.grid_id,
    t.timestamp,
    f.sms_in,
    f.sms_out,
    f.call_in,
    f.call_out,
    f.internet_activity,
    f.total_activity
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE f.grid_id = 4821
  AND t.timestamp = (SELECT MAX(timestamp) FROM dim_time);

-- =============================================================================
-- API3 — Hotspot & Alert Validation Queries
-- =============================================================================

-- 8. Top 10 hotspots at latest as_of
SELECT 
    f.grid_id,
    t.timestamp,
    f.total_activity,
    f.total_sms AS sms_activity,
    f.total_calls AS call_activity,
    f.internet_activity
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.timestamp = (SELECT MAX(timestamp) FROM dim_time)
ORDER BY f.total_activity DESC, f.grid_id ASC
LIMIT 10;

-- 9. Top rule-based alerts at latest as_of
SELECT 
    f.grid_id,
    t.timestamp,
    f.total_activity,
    f.internet_activity,
    f.internet_share
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
WHERE t.timestamp = (SELECT MAX(timestamp) FROM dim_time)
  AND f.total_activity >= 300
ORDER BY f.total_activity DESC, f.grid_id ASC
LIMIT 20;

-- =============================================================================
-- API4 — Grid Feature Validation Queries
-- =============================================================================

-- 10. Fetch stored ML2 feature vector for Grid 4821
SELECT 
    grid_id,
    feature_timestamp,
    avg_activity,
    activity_growth,
    active_hours,
    peak_ratio,
    variability,
    internet_share,
    data_quality_status
FROM grid_features
WHERE grid_id = 4821;

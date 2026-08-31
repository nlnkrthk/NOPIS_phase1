-- 110. Run queries for top grids, hourly trends
-- and internet-heavy windows.


-- ============================================================
-- 1. Top grids by total network activity
-- ============================================================

SELECT
    g.grid_id,
    g.centroid_lon,
    g.centroid_lat,
    SUM(f.total_activity) AS total_grid_activity
FROM fact_network_activity AS f
JOIN dim_grid AS g
    ON f.grid_id = g.grid_id
GROUP BY
    g.grid_id,
    g.centroid_lon,
    g.centroid_lat
ORDER BY total_grid_activity DESC
LIMIT 10;


-- ============================================================
-- 2. Hourly network activity trends
-- ============================================================

SELECT
    t.hour,
    SUM(f.total_activity) AS hourly_total_activity
FROM fact_network_activity AS f
JOIN dim_time AS t
    ON f.time_key = t.time_key
GROUP BY t.hour
ORDER BY t.hour;


-- ============================================================
-- 3. Internet-heavy time windows
-- ============================================================

SELECT
    t.time_key,
    t.date,
    t.hour,
    SUM(f.internet_activity) AS total_internet,
    AVG(f.internet_share) AS avg_internet_share
FROM fact_network_activity AS f
JOIN dim_time AS t
    ON f.time_key = t.time_key
GROUP BY
    t.time_key,
    t.date,
    t.hour
ORDER BY total_internet DESC
LIMIT 10;
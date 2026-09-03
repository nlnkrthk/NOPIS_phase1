-- 106. Design fact_network_activity with grid and time keys
-- and the activity measures.

-- 107. Design dim_time and dim_grid.
-- dim_grid holds grid_id, centroid coordinates and geometry reference.
-- Do not repeat geometry in fact_network_activity.

-- 108. Create the SQL tables in MySQL.

CREATE TABLE IF NOT EXISTS dim_grid (
    grid_id INT PRIMARY KEY,
    centroid_lon DOUBLE,
    centroid_lat DOUBLE,
    geometry TEXT
);


CREATE TABLE IF NOT EXISTS dim_time (
    time_key VARCHAR(10) PRIMARY KEY,
    timestamp DATETIME,
    date DATE,
    hour INT,
    day INT,
    month INT,
    year INT
);


CREATE TABLE IF NOT EXISTS fact_network_activity (
    grid_id INT NOT NULL,
    time_key VARCHAR(10) NOT NULL,

    sms_in DOUBLE,
    sms_out DOUBLE,
    call_in DOUBLE,
    call_out DOUBLE,
    internet_activity DOUBLE,

    total_sms DOUBLE,
    total_calls DOUBLE,
    total_activity DOUBLE,
    internet_share DOUBLE,

    PRIMARY KEY (grid_id, time_key),

    FOREIGN KEY (grid_id)
        REFERENCES dim_grid(grid_id),

    FOREIGN KEY (time_key)
        REFERENCES dim_time(time_key)
);


-- 111. Add simple indexing on the common filter
-- and join columns.

CREATE INDEX idx_fact_grid
    ON fact_network_activity(grid_id);

CREATE INDEX idx_fact_time
    ON fact_network_activity(time_key);

CREATE INDEX idx_fact_time_grid_activity
    ON fact_network_activity(time_key, grid_id, total_activity);

CREATE INDEX idx_dim_time_date
    ON dim_time(date);
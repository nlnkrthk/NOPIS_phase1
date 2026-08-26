import pandas as pd
import logging

class UsageProcessor:
    # 1. Create a UsageProcessor class that accepts a file path or a DataFrame.

    def __init__(self, source):
        self.source = source
        self.df = None
        self.logger = logging.getLogger(__name__) #np2-4-logging
    # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

    def load_data(self):
        """Load data from a CSV path or accept an existing DataFrame."""

        if isinstance(self.source, pd.DataFrame):
            self.df = self.source.copy()

        elif isinstance(self.source, str):
            self.df = pd.read_csv(self.source)

        else:
            raise TypeError("Source must be a file path or pandas DataFrame.")

        self.logger.info(        #np2-4-logging
            "Input rows: %d",
            len(self.df)
        )

        return self.df

    def clean_data(self):
    # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary.
        
        input_rows = len(self.df)

        if self.df is None:
            raise ValueError("Data must be loaded before cleaning.")

        activity_columns = [
            "smsin",
            "smsout",
            "callin",
            "callout",
            "internet"
        ]

        required_columns = [
            "datetime",
            "CellID",
            "countrycode",
            "smsin",
            "smsout",
            "callin",
            "callout",
            "internet"
        ]

        missing_columns = [
            column for column in required_columns
            if column not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        if self.df["CellID"].isnull().any():
            raise ValueError("Missing CellID values found.")

        if self.df["datetime"].isnull().any():
            raise ValueError("Missing datetime values found.")

        if (self.df[activity_columns] < 0).any().any():
            raise ValueError("Negative activity values found.")

        self.logger.info(
            "Rows rejected: %d",
            input_rows - len(self.df)
        )

        return self.df

    def derive_time_features(self):
    # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

        if self.df is None:
            raise ValueError("Data must be loaded before deriving time features.")

        self.df["datetime"] = pd.to_datetime(self.df["datetime"])

        self.df["date"] = self.df["datetime"].dt.date
        self.df["hour"] = self.df["datetime"].dt.hour
        self.df["day_of_week"] = self.df["datetime"].dt.day_name()

        return self.df

    def aggregate_to_grid_time(self):
        # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

        if self.df is None:
            raise ValueError("Data must be loaded before aggregation.")

        activity_columns = [
            "smsin",
            "smsout",
            "callin",
            "callout",
            "internet"
        ]

        self.df = (
            self.df
            .groupby(
                [
                    "datetime",
                    "date",
                    "hour",
                    "day_of_week",
                    "CellID"
                ],
                as_index=False
            )[activity_columns]
            .sum()
        )

        return self.df

    def derive_activity_features(self):
        # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

        if self.df is None:
            raise ValueError(
                "Data must be aggregated before deriving activity features."
            )

        self.df["total_sms"] = (
            self.df["smsin"] + self.df["smsout"]
        )

        self.df["total_calls"] = (
            self.df["callin"] + self.df["callout"]
        )

        self.df["total_activity"] = (
            self.df["total_sms"]
            + self.df["total_calls"]
            + self.df["internet"]
        )

        return self.df

    def compute_kpis(self):
        # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

        if self.df is None:
            raise ValueError(
                "Activity features must be derived before computing KPIs."
            )

        if "total_activity" not in self.df.columns:
            raise ValueError(
                "total_activity is required before computing KPIs."
            )

        hourly_activity = (
            self.df.groupby("hour")["total_activity"]
            .sum()
        )

        busiest_hour = hourly_activity.idxmax()
        busiest_hour_activity = hourly_activity.max()

        grid_activity = (
            self.df.groupby("CellID")["total_activity"]
            .sum()
        )

        busiest_grid = grid_activity.idxmax()
        busiest_grid_activity = grid_activity.max()

        self.kpis = {
            "total_activity": self.df["total_activity"].sum(),
            "average_hourly_activity": hourly_activity.mean(),
            "busiest_hour": busiest_hour,
            "busiest_hour_activity": busiest_hour_activity,
            "busiest_grid": busiest_grid,
            "busiest_grid_activity": busiest_grid_activity
        }

        return self.kpis


    def export_summary(self, output_dir="../outputs"):
        # 2. Implement load_data(), clean_data(), derive_time_features(), aggregate_to_grid_time(), derive_activity_features(), compute_kpis() and export_summary().

        if self.df is None:
            raise ValueError("Data must be processed before exporting summaries.")

        import os

        os.makedirs(output_dir, exist_ok=True)

        activity_columns = [
            "total_sms",
            "total_calls",
            "total_activity"
        ]

        daily_summary = (
            self.df
            .groupby("date", as_index=False)[activity_columns]
            .sum()
        )

        grid_summary = (
            self.df
            .groupby("CellID", as_index=False)[activity_columns]
            .sum()
        )

        daily_path = os.path.join(
            output_dir,
            "daily_summary.csv"
        )

        grid_path = os.path.join(
            output_dir,
            "grid_summary.csv"
        )

        daily_summary.to_csv(
            daily_path,
            index=False
        )

        grid_summary.to_csv(
            grid_path,
            index=False
        )
        
        self.logger.info(
            "Output rows: %d",
            len(self.df)
        )

        self.logger.info(
            "Daily summary output: %s",
            daily_path
        )

        self.logger.info(
            "Grid summary output: %s",
            grid_path
        )
        return daily_summary, grid_summary
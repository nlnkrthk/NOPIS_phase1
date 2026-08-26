# NP3 — Rule-Based Network Activity Alert Limitations

## False Positives

The rule-based alerts are operational attention signals, not proof of a network problem.

HIGH_ACTIVITY can be triggered by a legitimate increase in activity, such as a normal busy period or a special event.

ACTIVITY_SPIKE can be triggered by a temporary but legitimate increase in activity.

ACTIVITY_DROP can be triggered by a naturally quiet period or normal user behavior.

Therefore, every alert should be investigated rather than treated as a confirmed network fault.

## Baseline Limitations

This lab uses a within-day median baseline because only one day of data is available.

The baseline cannot distinguish between a grid that is normally quiet at a particular hour and a grid experiencing an unexpected activity drop at that hour.

For example, the baseline cannot determine whether low activity at 03:00 is normal for that grid because it has no historical data from previous days.

The baseline also cannot determine the actual cause of an activity change.

Activity-only data cannot distinguish network congestion, equipment failure, outage, special events, or changes in user behavior.

The alert layer therefore identifies unusual activity patterns for investigation. It does not diagnose network congestion or network faults.

## Data Required to Improve the Baseline

More historical daily data is required to understand normal activity patterns for each grid and hour of day.

Additional network-health metrics would also be required to determine whether unusual activity is associated with actual network congestion or another network condition.
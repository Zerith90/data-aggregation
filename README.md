# data-aggregation

###Synopsis

Objective : Streamline the reporting for GAP to just a few reports that are required.

Types of reports:

Last touch campaigns - done on databricks (rolling 2 years)
First touch campaigns (rolling 2 years)
Features:

1. Job is executed every day from 37 days before (start date) to 30 days before (end date)
2. Job is scheduled to run at 2300hrs EST
  * Data will replaced existing data if it already exists in the Darkplace database
  * Rows are matched based on date and strategy_id (the lowest denomination)
  * If data is different from that on T1, simply re-run for the period of the discrepancy (ad hoc) to update the data

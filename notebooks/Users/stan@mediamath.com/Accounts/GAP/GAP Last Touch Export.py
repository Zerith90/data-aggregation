# Databricks notebook source
# MAGIC %md
# MAGIC #### Import necessary files

# COMMAND ----------

import psycopg2 as pg
from sqlalchemy import create_engine
from datetime import datetime,timedelta
import uuid
import pandas as pd

# COMMAND ----------

# MAGIC %md
# MAGIC #### Run local def

# COMMAND ----------

# MAGIC %run /Users/stan@mediamath.com/utils/essentials

# COMMAND ----------

# MAGIC %md
# MAGIC #### Setting up connection

# COMMAND ----------

# conn_string =  "host='darkplace.cn3mythbkvex.us-east-1.rds.amazonaws.com' dbname='Dag' user='mm_analytics' password='Gar1h_m3ren6h1'"
# print(conn_string)
# conn = pg.connect(conn_string)
# cursor = conn.cursor()
# print "Connected!\n"
db_engine = create_engine('postgresql://mm_analytics:Gar1h_m3ren6h1@darkplace.cn3mythbkvex.us-east-1.rds.amazonaws.com:5432/Dag')

# COMMAND ----------

# MAGIC %md
# MAGIC #### Query to get data on a daily basis

# COMMAND ----------

# MAGIC %sql
# MAGIC 
# MAGIC MSCK REPAIR TABLE mm_attributed_events;

# COMMAND ----------

today=datetime.now()
start_date = (today - timedelta(days=37)).strftime('%Y-%m-%d')
end_date=(today - timedelta(days=30)).strftime('%Y-%m-%d')
unique_id =uuid.uuid4().int
# uuid.uuid4().int
create = '''
create table tmp_query_generator_gap_{{uuid}} stored as ORC as
select
    mm_date,
    campaign_id,
    campaign_name,
    strategy_id,
    strategy_name,
    sum(case when type = 'retail' then 1 else 0 end) as offline_conversion,
    sum(case when type = 'retail' then cast(revenue as double) else 0 end) as offline_revenue,
    sum(case when type <> 'retail' then 1 else 0 end) as online_conversion,
    sum(case when type <> 'retail' then cast(revenue as double) else 0 end) as online_revenue,
    count(*) as total_conversion
FROM
    (
        select
            to_date(
                from_unixtime(
                    unix_timestamp(impression_timestamp_gmt) + unix_timestamp(event_report_timestamp) - unix_timestamp(event_timestamp_gmt)
                )
            ) as mm_date,
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name,
            lower(mm_s2) as type,
            cast(mm_v1 as double) as revenue,
            ROW_NUMBER() OVER(
                PARTITION BY mm_uuid,
                advertiser_id,
                event_report_timestamp,
                mm_s1
                ORDER BY
                    batch_id DESC,
                    RAND()
            ) as rank
        from
            mm_attributed_events
        where
            organization_id = 100174
            and event_type = 'conversion'
            and event_date between date_sub('{{start_date}}', 1)
            and date_add('{{end_date}}', 7)
            and (unix_timestamp(event_timestamp_gmt) - unix_timestamp(event_timestamp_gmt) ) between 0 and 60*24*7 * 60
            and to_date(
                from_unixtime(
                   unix_timestamp(event_timestamp_gmt) + unix_timestamp(event_report_timestamp) - unix_timestamp(event_timestamp_gmt)
                )
            ) between '{{start_date}}'
            and '{{end_date}}'
    ) a
where
    rank = 1
group by
    mm_date,
    campaign_id,
    campaign_name,
	strategy_id,
    strategy_name'''
    
select = '''SELECT
    a.mm_date,
    a.advertiser_id,
    a.advertiser_name,
    a.campaign_id,
    a.campaign_name,
    a.strategy_id,
    a.strategy_name ,
	total_spend,
    impressions,
    clicks,
    online_conversion,
    online_revenue,
    offline_conversion,
    offline_revenue
from
    (
        select
            to_date(report_timestamp) as mm_date,
            advertiser_id,
            advertiser_name,
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name,
            sum(total_spend_cpm / 1000) as total_spend,
            count(*) as impressions
        from
            mm_impressions
        where
            organization_id = 100174
            and impression_date between date_sub('{{start_date}}', 1)
            and date_add('{{end_date}}', 1)
            and to_date(report_timestamp) between '{{start_date}}'
            and '{{end_date}}'
        group by
            to_date(report_timestamp),
              advertiser_id,
            advertiser_name,
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name
    ) a
    join (
        select
            to_date(event_report_timestamp) as mm_date,
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name,
            count(*) as clicks
        from
            mm_attributed_events
        where
            organization_id = 100174
            and event_type = 'click'
            and event_date between date_sub('{{start_date}}', 7)
            and date_add('{{end_date}}', 7)
            and to_date(event_report_timestamp) between '{{start_date}}'
            and '{{end_date}}'
        group by
            to_date(event_report_timestamp),
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name
    ) b on a.strategy_id = b.strategy_id
    and a.mm_date = b.mm_date
    join (
        select
            mm_date,
            campaign_id,
            campaign_name,
            strategy_id,
            strategy_name,
            online_conversion,
            online_revenue,
            offline_conversion,
            offline_revenue
        from
            tmp_query_generator_gap_{{uuid}}
    ) c on a.strategy_id = c.strategy_id
    and a.mm_date = c.mm_date
'''
params={
  "{{organization_id}}":100174,
  "{{start_date}}":start_date,
  "{{end_date}}":end_date,
  "{{uuid}}":unique_id
}

create_query = format_query(create,params)
select_query = format_query(select,params)
print(start_date)

# COMMAND ----------

# MAGIC %sql
# MAGIC drop table if exists tmp_query_generator_gap_29125

# COMMAND ----------

# MAGIC %md
# MAGIC #### Create a df for the above query

# COMMAND ----------


create_execute = sqlContext.sql(create_query)
select_execute_df = sqlContext.sql(select_query).toPandas()
# clear = sqlContext.sql("drop table if exists tmp_query_generator_gap_"+str(unique_id))

# COMMAND ----------

select_execute_df.head()

# COMMAND ----------


select_execute_df.to_sql('gap_last_touch_agg',if_exists="replace",con=db_engine)
clear = sqlContext.sql("drop table if exists tmp_query_generator_gap_"+str(unique_id))

# COMMAND ----------


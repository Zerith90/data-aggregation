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

# MAGIC %run /Users/admin/Credentials

# COMMAND ----------

db = credentials['dag_psycopg2_connection_string']

# COMMAND ----------

# MAGIC %md
# MAGIC #### Setting up connection

# COMMAND ----------

a=db.split(' ')
dbname = a[0].split('=')[1][1:-1]
user = a[1].split('=')[1][1:-1]
host = a[2].split('=')[1][1:-1]
pw=a[3].split('=')[1][1:-1]


# COMMAND ----------

conn_string =  db
# print(conn_string)
conn = pg.connect(conn_string)
cursor = conn.cursor()
# print "Connected!\n"
db_engine = create_engine('postgresql://'+user+':'+pw+'@'+host+':5432/'+dbname)

# COMMAND ----------

# MAGIC %md
# MAGIC #### Query to get data on a daily basis

# COMMAND ----------

# MAGIC %sql
# MAGIC desc mm_attributed_events

# COMMAND ----------

today=datetime.now()
start_date = (today - timedelta(days=44)).strftime('%Y-%m-%d')
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
    sum(case when type <> 'retail' and pv_pc_flag='C' then 1 else 0 end) as pc_online_conversion,
    sum(case when type <> 'retail' and pv_pc_flag='C' then cast(revenue as double) else 0 end) as pc_online_revenue,
    sum(case when type <> 'retail' and pv_pc_flag='V' then 1 else 0 end) as pv_online_conversion,
    sum(case when type <> 'retail' and pv_pc_flag='V' then cast(revenue as double) else 0 end) as pv_online_revenue,
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
            pv_pc_flag,
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
    media_cost,
    impressions,
    clicks,
      online_conversion,
            online_revenue,
            offline_conversion,
            offline_revenue,
            pv_online_conversion,
            pv_online_revenue,
            pc_online_conversion,
            pc_online_revenue
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
            sum(media_cost_cpm / 1000) as media_cost,
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
            offline_revenue,
            pv_online_conversion,
            pv_online_revenue,
            pc_online_conversion,
            pc_online_revenue
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


# COMMAND ----------

print(format_query(select,params))

# COMMAND ----------

# MAGIC %md
# MAGIC #### Create a df for the above query
# MAGIC 1. Use the "toPandas()" function to convert the spark dataframe into a pandas dataframe
# MAGIC 2. Clear the temp table 

# COMMAND ----------


create_execute = sqlContext.sql(create_query)
select_execute_df = sqlContext.sql(select_query).toPandas()
clear = sqlContext.sql("drop table if exists tmp_query_generator_gap_"+str(unique_id))

# COMMAND ----------

select_execute_df=select_execute_df.sort_values(by='mm_date').fillna(0)
select_execute_df.head(200)

# COMMAND ----------

# MAGIC %md
# MAGIC 1. Add an additional column "batch" to know when it was last updated

# COMMAND ----------

import datetime

now = datetime.datetime.now()
select_execute_df["batch"] = now

# COMMAND ----------

select_execute_df.head()

# COMMAND ----------


select_execute_df.to_sql('gap_last_touch_agg',if_exists="append",con=db_engine,index=False)
clear = sqlContext.sql("drop table if exists tmp_query_generator_gap_"+str(unique_id))

# COMMAND ----------

# MAGIC %md
# MAGIC #### Removing duplicates
# MAGIC 
# MAGIC 1. Assign a row number based on the mm_date, campaign_id, strategy_id and sort  them in a descending order by the auto increment column "ID"
# MAGIC 2. Delete all rows that are more than 1 (only keep the latest)

# COMMAND ----------


dups = '''
delete from gap_last_touch_agg where id in (SELECT id
              FROM (SELECT id, mm_date,advertiser_id,campaign_id,strategy_id,
                             ROW_NUMBER() OVER (partition BY mm_date,advertiser_id,campaign_id,strategy_id ORDER BY id desc) AS rnum
                     FROM gap_last_touch_agg) t
              WHERE t.rnum > 1)
'''
rows_affected = cursor.execute(dups)
conn.commit()
cursor.close()
conn.close()
# print(rows_affected)


# COMMAND ----------

# MAGIC %md
# MAGIC 1. Create the file in s3 for clients to download.  Prevent errors in future if the file is too big by providing a link instead of attaching the file together with the Email
# MAGIC 2. Expire the file within 1 day so that they only have access to the latest 1 

# COMMAND ----------

def upload_to_client_s3(filename,s3path):
  s3 = boto3.client(
    's3',
    aws_access_key_id=credentials['aws_reporting_keys']['access_key'],
    aws_secret_access_key=credentials['aws_reporting_keys']['secret_key']
  )
  s3.upload_file(filename,'mm-analytics-client-distribution', s3path + filename)
  url = s3.generate_presigned_url(
    ClientMethod='get_object',
    Params={
        'Bucket': 'mm-analytics-client-distribution',
        'Key': s3path + filename
    },
    ExpiresIn=259200
  )
  return url

# COMMAND ----------

# MAGIC %md
# MAGIC #####Give the DAG db some time to clear the duplicates before sending them out 
# MAGIC 
# MAGIC **this queries are executed sequentially, so the duplicates should have been removed by the time of execution of the next cell

# COMMAND ----------

import time
time.sleep(5)


# COMMAND ----------

file_name = 'GAP_performance_report_last_touch_{}.csv'.format(datetime.datetime.now().strftime('%Y-%m-%d'))


# COMMAND ----------

df = pd.read_sql_query('''
select
  mm_date
  ,advertiser_id
  ,advertiser_name
  ,campaign_id
  ,campaign_name
  ,strategy_id
  ,strategy_name
  ,total_spend
  ,media_cost
  ,impressions
  ,clicks
  ,online_conversion
  ,online_revenue
  ,offline_conversion
  ,offline_revenue
  ,pv_online_conversion	
  ,pc_online_conversion
  ,pv_online_revenue
  ,pc_online_revenue
	


from gap_last_touch_agg order by mm_date''',con=db_engine)
final_df = df.to_csv(file_name,index=False)

# COMMAND ----------

# MAGIC %run "/Users/acandela@mediamath.com/reporting_utils/email_tools"

# COMMAND ----------

EMAIL_BODY = ''' 
Hi GAP!

GAP Performance report - last touch has been updated. You can download the file from the following link.

{}

*** The link will expire in 1 day***


We are still in the midst of testing this new process out. If you find anything amiss or would want any changes, feel free to reach out to me at stan@mediamath.com

Thank you
MediaMath Analytics
'''

SUBJECT = 'GAP Performance Report (Last Touch)'

# COMMAND ----------

# MAGIC %run "/Users/acandela@mediamath.com/reporting_utils/email_tools"

# COMMAND ----------

e = EMAIL()
e.send_email(SUBJECT,EMAIL_BODY.format(upload_to_client_s3(file_name,'tmp/')),["Mark_chong@gap.com","Kelli_Hashimoto@gap.com"],cc=["Matthew_Seabrook@gap.com"],bcc=['mm_gap@mediamath.com','nhuang@mediamath.com','stan@mediamath.com'])
# e.send_email(SUBJECT,EMAIL_BODY.format(upload_to_client_s3(file_name,'tmp/')),['stan@mediamath.com'])

# COMMAND ----------

import os
os.remove(file_name)
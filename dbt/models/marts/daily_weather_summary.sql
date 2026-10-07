select
    city,
    observed_date,
    round(min(temperature_c)::numeric, 1) as min_temp_c,
    round(max(temperature_c)::numeric, 1) as max_temp_c,
    round(avg(temperature_c)::numeric, 1) as avg_temp_c,
    round((max(temperature_c) - min(temperature_c))::numeric, 1)  as temp_range_c,
    count(*) as hours_observed
from {{ ref('stg_hourly_weather') }}
group by city, observed_date

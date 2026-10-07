select
    city,
    observed_at,
    observed_at::date as observed_date,
    temperature_c
from {{ source('raw', 'hourly_weather') }}
where temperature_c is not null

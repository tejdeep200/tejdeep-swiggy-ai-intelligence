select
    city_id,
    nullif(trim(city_name), '') as city_name
from {{ source('raw_swiggy', 'cities') }}

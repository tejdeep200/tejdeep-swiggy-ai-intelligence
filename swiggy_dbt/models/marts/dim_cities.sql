select
    city_id,
    city_name
from {{ ref('stg_cities') }}

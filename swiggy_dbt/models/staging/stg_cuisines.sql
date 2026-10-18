select
    cuisine_id,
    nullif(trim(cuisine_name), '') as cuisine_name
from {{ source('raw_swiggy', 'cuisines') }}

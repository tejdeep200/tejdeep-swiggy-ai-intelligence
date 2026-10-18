select
    cuisine_id,
    cuisine_name
from {{ ref('stg_cuisines') }}

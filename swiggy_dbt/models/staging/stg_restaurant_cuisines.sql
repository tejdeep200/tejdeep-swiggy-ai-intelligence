select
    listing_id as restaurant_id,
    cuisine_id
from {{ source('raw_swiggy', 'restaurant_cuisines') }}

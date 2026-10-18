select
    listing_id as restaurant_id,
    source_row_number,
    nullif(trim(restaurant_name), '') as restaurant_name,
    city_id,
    nullif(trim(area), '') as area,
    try_to_decimal(nullif(regexp_replace(rating_raw, '[^0-9.]', ''), ''), 3, 1) as rating,
    try_to_number(nullif(regexp_replace(number_of_ratings_raw, '[^0-9]', ''), '')) as rating_count,
    try_to_number(nullif(regexp_replace(average_price_raw, '[^0-9]', ''), '')) as average_price,
    try_to_number(nullif(regexp_replace(number_of_offers_raw, '[^0-9]', ''), '')) as offer_count,
    nullif(trim(offer_name_raw), '') as offer_name,
    case
        when lower(trim(pure_veg_raw)) in ('true', 'yes', 'y', '1') then true
        when lower(trim(pure_veg_raw)) in ('false', 'no', 'n', '0') then false
    end as is_pure_veg
from {{ source('raw_swiggy', 'restaurants') }}

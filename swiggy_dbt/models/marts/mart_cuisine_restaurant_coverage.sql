select
    c.cuisine_id,
    c.cuisine_name,
    count(distinct rc.restaurant_id) as restaurant_count,
    round(avg(r.rating), 2) as average_restaurant_rating
from {{ ref('stg_restaurant_cuisines') }} as rc
inner join {{ ref('dim_cuisines') }} as c
    on rc.cuisine_id = c.cuisine_id
inner join {{ ref('dim_restaurants') }} as r
    on rc.restaurant_id = r.restaurant_id
group by 1, 2

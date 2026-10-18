with restaurant_cuisines as (
    select
        rc.restaurant_id,
        listagg(c.cuisine_name, ', ') within group (order by c.cuisine_name) as cuisines
    from {{ ref('stg_restaurant_cuisines') }} as rc
    inner join {{ ref('stg_cuisines') }} as c
        on rc.cuisine_id = c.cuisine_id
    group by rc.restaurant_id
)

select
    r.restaurant_id,
    r.restaurant_name,
    r.city_id,
    city.city_name,
    r.area,
    r.rating,
    r.rating_count,
    r.average_price,
    r.offer_count,
    r.offer_name,
    r.is_pure_veg,
    rc.cuisines
from {{ ref('stg_restaurants') }} as r
left join {{ ref('stg_cities') }} as city
    on r.city_id = city.city_id
left join restaurant_cuisines as rc
    on r.restaurant_id = rc.restaurant_id

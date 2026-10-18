select
    city_id,
    city_name,
    count(*) as restaurant_count,
    round(avg(rating), 2) as average_rating,
    round(avg(average_price), 0) as average_price,
    count_if(is_pure_veg) as pure_veg_restaurant_count,
    round(div0(count_if(is_pure_veg), count(*)), 4) as pure_veg_restaurant_rate
from {{ ref('dim_restaurants') }}
group by 1, 2

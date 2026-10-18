{% snapshot snap_restaurants %}

{{
    config(
        unique_key='restaurant_id',
        strategy='check',
        check_cols=['restaurant_name', 'city_id', 'area', 'rating', 'rating_count', 'average_price', 'offer_count', 'offer_name', 'is_pure_veg']
    )
}}

select *
from {{ ref('stg_restaurants') }}

{% endsnapshot %}

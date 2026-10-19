import test from 'node:test';
import assert from 'node:assert/strict';
import {chartExplanation} from '../lib/chart-explanation.ts';
test('explains the selected chart values, filters, and displayed scope',()=>{
 const text=chartExplanation({metric:'average_rating',dimension:'city',filters:{cuisine:'Chinese'},dataset:[{dimension:'Delhi',value:3.2},{dimension:'Mumbai',value:4.5}]});
 assert.match(text,/Average rating by city/);assert.match(text,/Mumbai: 4.5, highest shown/);assert.match(text,/Delhi: 3.2, lowest shown/);assert.match(text,/cuisine: Chinese/);
});
test('formats vegetarian fractions as percentages and handles missing values',()=>{
 assert.match(chartExplanation({metric:'pure_veg_rate',dimension:'city',dataset:[{dimension:'Delhi',value:0.25}]}),/25.0 percent/);
 assert.match(chartExplanation({metric:'average_price',dimension:'city',dataset:[{dimension:'Delhi',value:null}]}),/no numeric values/);
});

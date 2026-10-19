type Chart = {metric:string;dimension:string;dataset:{dimension:string|null;value:number|string|null}[];filters?:Record<string,string|null>};
export function chartExplanation(chart:Chart):string {
  const labels:Record<string,string>={average_rating:'Average rating',average_price:'Average listing price',restaurant_count:'Restaurant count',pure_veg_rate:'Vegetarian share'};
  const label=labels[chart.metric]||chart.metric.replaceAll('_',' ');
  const rows=chart.dataset.filter(r=>r.value!==null && r.value!=='' && Number.isFinite(Number(r.value)));
  if(!rows.length)return `${label} by ${chart.dimension}: no numeric values are available for the selected filters.`;
  const sorted=[...rows].sort((a,b)=>Number(b.value)-Number(a.value));
  const format=(value:number|string|null)=>chart.metric==='pure_veg_rate'?`${(Number(value)*100).toFixed(1)} percent`:Number(value).toLocaleString('en-US',{maximumFractionDigits:2});
  const high=sorted[0],low=sorted[sorted.length-1];
  let summary=`${label} by ${chart.dimension}. ${high.dimension||'Unknown'}: ${format(high.value)}, highest shown.`;
  if(sorted.length>1)summary+=` ${low.dimension||'Unknown'}: ${format(low.value)}, lowest shown.`;
  const filters=Object.entries(chart.filters||{}).filter(([,value])=>value).map(([key,value])=>`${key}: ${value}`).join(', ');
  return summary+` Across ${rows.length} displayed groups.`+(filters?` Filters: ${filters}.`:'')+' These are published listing data.';
}

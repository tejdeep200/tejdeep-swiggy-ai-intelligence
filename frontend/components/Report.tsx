'use client';
import { useState } from 'react';
import { PowerBIEmbed } from 'powerbi-client-react';
import { models, Report as PBIReport } from 'powerbi-client';

export default function Report({reportKey, city}: {reportKey:string;city?:string}) {
  const [config,setConfig] = useState<any>(null);
  const [error,setError] = useState('');
  const [report,setReport] = useState<PBIReport>();
  const [loaded,setLoaded] = useState(false);
  const [visualName,setVisualName] = useState('');
  async function open() {
    setError(''); setLoaded(false);
    try { const r=await fetch(`/api/reports/${encodeURIComponent(reportKey)}/embed`); const data=await r.json(); if(!r.ok) throw new Error(data.detail); setConfig(data); }
    catch(e:any) { setError(e.message); }
  }
  async function filter() {
    const target=config?.filter_targets?.city;
    if(!target || !report) return;
    try { const filters: models.IBasicFilter[] = city ? [{$schema:'http://powerbi.com/product/schema#basic', target, operator:'In', values:[city], filterType:models.FilterType.Basic}] : []; await report.setFilters(filters); }
    catch { setError('This report could not apply the selected city filter.'); }
  }
  return <section className="report"><button onClick={open}>{config?'Renew token / reload report':'Open authorized Power BI report'}</button>{error&&<p role="alert">{error}</p>}
    {config&&<><div className="report-tools"><label>Page <select defaultValue="" onChange={e=>report?.setPage(e.target.value).catch(()=>setError('Page unavailable'))}><option value="" disabled>Select page</option>{config.pages.map((p:any)=><option key={p.name} value={p.name}>{p.title||p.name}</option>)}</select></label>
    <label>Visual <select value={visualName} onChange={e=>{setVisualName(e.target.value);setLoaded(false)}}><option value="">Report view</option>{config.visuals.map((v:any)=><option key={v.name} value={v.name}>{v.title||v.name}</option>)}</select></label>
    <button onClick={filter} disabled={!loaded||!config.filter_targets?.city}>Apply city filter</button></div>
    {!loaded&&<p>Loading Power BI report…</p>}
    <PowerBIEmbed key={visualName} embedConfig={{
      type:visualName?'visual':'report', id:config.id, embedUrl:config.embedUrl,
      accessToken:config.accessToken, tokenType:models.TokenType.Embed,
      permissions:models.Permissions.Read,
      ...(visualName?{visualName,pageName:config.visuals.find((v:any)=>v.name===visualName)?.page}:{}),
      settings:{panes:{filters:{visible:true},pageNavigation:{visible:true}}}
    }} cssClassName="powerbi-frame" getEmbeddedComponent={component=>setReport(component as PBIReport)} eventHandlers={new Map([['loaded',()=>setLoaded(true)],['error',()=>setError('Power BI could not load this report. Verify capacity and workspace permissions.')]])}/>
    <small>Embed token expires {new Date(config.expiration).toLocaleTimeString()}. Renew above when needed. Use the report’s slicers for configured dates, categories and drill-down.</small></>}
  </section>;
}

from __future__ import annotations
import math
import pandas as pd

def _tax_schedule(equipment, years, dep_years, rate):
    out=[]
    for year in range(1, years+1):
        begin=max(equipment*(1-(year-1)/dep_years),0)
        end=max(equipment*(1-year/dep_years),0)
        out.append(rate*(begin+end)/2)
    return out

def calculate_strategy(config, strategy, discount_rate=None, cloud_multiplier=1.0):
    years=config['horizon_years']; r=config['discount_rate'] if discount_rate is None else discount_rate
    data=config[strategy]; rows=[]
    one_time=data['one_time']; year0=sum(one_time.values())
    rows.append({'year':0,'capex':one_time.get('equipment',0),'setup':sum(v for k,v in one_time.items() if k not in ('equipment',)),'training':one_time.get('training',0),'recurring':0,'modernization':0,'property_tax':0,'nominal_cost':year0,'discount_factor':1.0,'discounted_cost':year0})
    tax=[]
    equipment=one_time.get('equipment',0)
    if equipment:
        tax=_tax_schedule(equipment,years,data.get('equipment_depreciation_years',years),data.get('property_tax_rate',0))
    for year in range(1,years+1):
        annual=data['annual']; recurring=0
        if strategy=='cloud': recurring=annual['cloud_services']*((1+data['cloud_growth_rate'])**(year-1))*cloud_multiplier+annual['personnel']+annual['provider_support']
        else: recurring=sum(annual.values())
        modern=data.get('modernization',{}).get('amount',0) if year==data.get('modernization',{}).get('year') else 0
        prop=tax[year-1] if tax else 0
        nominal=recurring+modern+prop
        df=1/(1+r)**year
        rows.append({'year':year,'capex':0,'setup':0,'training':0,'recurring':recurring,'modernization':modern,'property_tax':prop,'nominal_cost':nominal,'discount_factor':df,'discounted_cost':nominal*df})
    frame=pd.DataFrame(rows); frame['cumulative_discounted_cost']=frame['discounted_cost'].cumsum(); frame['strategy']=data['name']
    return frame

def summarize(frame):
    return {'strategy':frame['strategy'].iloc[0],'nominal_tco':frame['nominal_cost'].sum(),'discounted_tco':frame['discounted_cost'].sum(),'initial_cost':frame.loc[frame['year']==0,'nominal_cost'].iloc[0]}

def calculate_all(config, discount_rate=None, cloud_multiplier=1.0):
    frames={s:calculate_strategy(config,s,discount_rate,cloud_multiplier if s=='cloud' else 1.0) for s in ('on_premise','cloud','hybrid')}
    summaries=pd.DataFrame([summarize(f) for f in frames.values()]).sort_values('discounted_tco').reset_index(drop=True)
    return frames,summaries

def cloud_break_even(config):
    on,_=calculate_all(config)
    target=summarize(on['on_premise'])['discounted_tco']; c=config['cloud']; r=config['discount_rate']; years=config['horizon_years']
    fixed=sum(c['one_time'].values())+sum((c['annual']['personnel']+c['annual']['provider_support'])/(1+r)**y for y in range(1,years+1))
    coeff=sum((1+c['cloud_growth_rate'])**(y-1)/(1+r)**y for y in range(1,years+1))
    return {'cloud_base_annual_break_even':(target-fixed)/coeff,'on_pv_target':target,'fixed_cloud_pv':fixed,'cloud_service_pv_coefficient':coeff}

def fmt(value, decimals=2): return f'{value:,.{decimals}f}'.replace(',',' ').replace('.',',')

import yfinance as yf
import pandas as pd
import numpy as np
import json
import warnings
from datetime import datetime
warnings.filterwarnings('ignore')

print("📥 데이터 수집 중...")
raw = yf.download(
    ['SPY','GLD','TLT','SHY','TIP','HYG','LQD','DX-Y.NYB','^VIX'],
    start='2022-01-01', end=datetime.today().strftime('%Y-%m-%d'),
    progress=False
)['Close']
raw.columns = ['DXY','GLD','HYG','LQD','SHY','SPY','TIP','TLT','VIX']
raw = raw.ffill().dropna()

def compute_signals(df, w_mom=10, w_smooth=3):
    s = pd.DataFrame(index=df.index)
    s['real_rate'] = -df['TIP'].pct_change(w_mom).rolling(w_smooth).mean()
    s['credit']    = -(df['HYG']/df['LQD']).pct_change(w_mom).rolling(w_smooth).mean()
    s['dxy']       = -df['DXY'].pct_change(w_mom).rolling(w_smooth).mean()
    s['vix']       = -(df['VIX'] - df['VIX'].rolling(30).mean()) / (df['VIX'].rolling(30).std() + 1e-9)
    s['mom_SPY']   = df['SPY'].pct_change(w_mom).rolling(w_smooth).mean()
    s['mom_GLD']   = df['GLD'].pct_change(w_mom).rolling(w_smooth).mean()
    s['mom_TLT']   = df['TLT'].pct_change(w_mom).rolling(w_smooth).mean()
    return s.dropna()

sig = compute_signals(raw)

def decide_weights(row):
    params = {'rr_gld':1.5,'rr_tlt':1.0,'rr_spy':0.5,'cs_shy':2.0,'cs_spy':1.5,
              'dx_gld':1.0,'dx_spy':0.5,'vx_spy':1.0,'vx_shy':1.5,'mom':10}
    s = {'SPY':0.,'GLD':0.,'TLT':0.,'SHY':0.}
    rr=row['real_rate']; cs=row['credit']; dx=row['dxy']; vx=row['vix']
    s['GLD']+=rr*params['rr_gld']; s['TLT']+=rr*params['rr_tlt']; s['SPY']-=rr*params['rr_spy']
    s['SHY']-=cs*params['cs_shy']; s['SPY']-=cs*params['cs_spy']
    s['GLD']+=dx*params['dx_gld']; s['SPY']+=dx*params['dx_spy']
    s['SPY']+=vx*params['vx_spy']; s['SHY']-=min(vx,0)*params['vx_shy']
    s['SPY']+=row['mom_SPY']*params['mom']*10
    s['GLD']+=row['mom_GLD']*params['mom']*10
    s['TLT']+=row['mom_TLT']*params['mom']*10
    mn=min(s.values())
    if mn<0:
        for k in s: s[k]-=mn
    s['SHY']=max(s['SHY'],0.05*(sum(s.values())+1e-9))
    total=sum(s.values())
    if total<1e-9: return {k:0.25 for k in s}
    w={k:v/total for k,v in s.items()}
    for k in w: w[k]=min(w[k],0.65)
    t2=sum(w.values())
    return {k:round(v/t2,4) for k,v in w.items()}

latest = sig.iloc[-1]
weights = decide_weights(latest)

# 신호 정규화
def normalize(val, series):
    mn, mx = series.quantile(0.05), series.quantile(0.95)
    return max(-1, min(1, float((val - (mn+mx)/2) / ((mx-mn)/2 + 1e-9))))

# 최근 52주 SPY 주간 수익률
spy_weekly = raw['SPY'].resample('W-FRI').last().pct_change().tail(52)

# 최근 2년 주간 비중 히스토리
weekly_sig = sig.resample('W-FRI').last().tail(104)
weight_history = []
for date, row in weekly_sig.iterrows():
    w = decide_weights(row)
    weight_history.append({'date': date.strftime('%Y-%m-%d'), **w})

# 최근 2년 포트폴리오 수익률 시뮬레이션
prices_2y = raw[['SPY','GLD','TLT','SHY']].tail(504)
cap = 100000
cur_w = {'SPY':0.25,'GLD':0.25,'TLT':0.25,'SHY':0.25}
rebal_dates = set(prices_2y.resample('W-FRI').last().index)
port_vals = []
prev = None
for date in prices_2y.index:
    if date in rebal_dates and date in sig.index:
        cur_w = decide_weights(sig.loc[date])
    if prev is not None:
        r = sum(cur_w[k]*(prices_2y.loc[date,k]/prices_2y.loc[prev,k]-1) for k in cur_w)
        cap *= (1+r)
    port_vals.append({'date': date.strftime('%Y-%m-%d'), 'value': round((cap/100000-1)*100, 2)})
    prev = date

spy_vals = [{'date': d.strftime('%Y-%m-%d'),
             'value': round((prices_2y.loc[d,'SPY']/prices_2y['SPY'].iloc[0]-1)*100, 2)}
            for d in prices_2y.index]

output = {
    'updated': raw.index[-1].strftime('%Y-%m-%d'),
    'prices': {
        'SPY': round(float(raw['SPY'].iloc[-1]), 2),
        'GLD': round(float(raw['GLD'].iloc[-1]), 2),
        'TLT': round(float(raw['TLT'].iloc[-1]), 2),
        'SHY': round(float(raw['SHY'].iloc[-1]), 2),
    },
    'weights': weights,
    'signals': {
        'real_rate': round(normalize(latest['real_rate'], sig['real_rate']), 3),
        'credit':    round(normalize(latest['credit'],    sig['credit']),    3),
        'dxy':       round(normalize(latest['dxy'],       sig['dxy']),       3),
        'vix':       round(normalize(latest['vix'],       sig['vix']),       3),
    },
    'weight_history': weight_history,
    'portfolio_history': port_vals[-104:],
    'spy_history': spy_vals[-104:],
    'spy_weekly': [round(float(v), 2) for v in spy_weekly.dropna().tolist()],
}

with open('docs/data.json', 'w') as f:
    json.dump(output, f, separators=(',',':'))

print(f"✅ 완료: {output['updated']}")
print(f"   비중: {weights}")

#!/usr/bin/env python3
"""Rolling Beta Analysis v4 - clean layout, tight y-axis, clear labels."""
import sys, os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

def break_gaps(sub, small_gap=60, big_gap=365):
    """Handle gaps: >1yr drops old data, >60d inserts NaN to break lines."""
    sub = sub.sort_values('as_of_date').copy()
    diffs = sub['as_of_date'].diff()
    # If any gap > 1 year, keep only data after the last such gap
    big = diffs > pd.Timedelta(days=big_gap)
    if big.any():
        last_big = sub[big].index[-1]
        sub = sub.loc[last_big:].copy()
    # For remaining smaller gaps > 60 days, insert NaN to break line
    diffs = sub['as_of_date'].diff()
    small = diffs > pd.Timedelta(days=small_gap)
    if not small.any():
        return sub
    rows = []
    for idx in sub[small].index:
        loc = sub.index.get_loc(idx)
        if loc == 0: continue
        prev_idx = sub.index[loc - 1]
        nan_row = sub.loc[prev_idx:prev_idx].copy()
        nan_row['as_of_date'] = sub.loc[prev_idx, 'as_of_date'] + pd.Timedelta(days=1)
        for col in nan_row.columns:
            if col not in ('as_of_date','asset_id','fund_type','fund_cat'):
                nan_row[col] = float('nan')
        rows.append(nan_row)
    if rows:
        sub = pd.concat([sub] + rows).sort_values('as_of_date').reset_index(drop=True)
    return sub



OUTPUT_ROOT = os.path.expanduser("~/Desktop/beta_analysis_output")
C = dict(blue="#003580", red="#C62828", grid="#DDDDDD", bg="#F7F8FA",
         title="#1A1A1A", sub="#555555", light="#999999")
FT_ORDER = ['Private Equity','Private Credit','Private Real Assets','Private Real Estate']

plt.rcParams.update({
    'font.family':'sans-serif','font.sans-serif':['DejaVu Sans','Helvetica'],
    'font.size':7,'figure.facecolor':'white','axes.facecolor':C['bg'],
    'axes.grid':True,'grid.color':C['grid'],'grid.linewidth':0.3,
    'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':0.5,
    'lines.linewidth':1.3,'lines.antialiased':True,
})

def load_params(p):
    df=pd.read_csv(p)
    rn={'as_of':'as_of_date','ticker':'asset_id','fund_cat':'fund_type','calib_nav_cnt':'calib_nav_count'}
    df=df.rename(columns={k:v for k,v in rn.items() if k in df.columns})
    df['as_of_date']=pd.to_datetime(df['as_of_date'])
    df=df[(df['beta_ols'].abs()>0.01)&df['beta_ols'].notna()].copy()
    if 'chowlin_mkt_coeff' in df.columns and 'chowlin_prx_coeff' in df.columns:
        df['chowlin_sum']=df['chowlin_mkt_coeff']+df['chowlin_prx_coeff']
    if 'beta_ols_clamped' in df.columns:
        df=df[~df['beta_ols_clamped']].copy()
    df=df.sort_values(['asset_id','as_of_date']).reset_index(drop=True)
    for c in ['calib_nav_count','calib_days']:
        if c not in df.columns: df[c]=0
    return df

def load_mapping(p):
    m=pd.read_csv(p); out={}
    for _,r in m.iterrows():
        out[r['asset_label']]=dict(etp=r['etp_ticker'],broad=r['broad_index_ticker'],
            etp_desc=str(r.get('etp_description','')).split('.')[0].split(' UUID')[0].strip(),
            broad_desc=str(r.get('broad_index_description','')).split('.')[0].split(' UUID')[0].strip(),
            sub_type=r.get('sub_type',''),region=r.get('region',''))
    return out

def sort_assets(assets,df,mapping):
    def key(a):
        ft=df[df['asset_id']==a].iloc[0].get('fund_type','')
        fi=FT_ORDER.index(ft) if ft in FT_ORDER else 99
        m=mapping.get(a,{}); return(fi,m.get('sub_type',''),a)
    return sorted(assets,key=key)

def parse_fund(a):
    parts=a.split(' | ',1)
    ccy=parts[0].strip() if len(parts)==2 else ''
    rest=parts[1].strip() if len(parts)==2 else a
    tokens=rest.rsplit(' - ',1)
    if len(tokens)==2 and len(tokens[1])==3 and tokens[1]==ccy: name=tokens[0]
    else: name=rest
    return ccy,name

def setup_ax(ax,dates,vals):
    # X axis
    n_yr=(dates.max()-dates.min()).days/365.25
    if n_yr>12: ax.xaxis.set_major_locator(mdates.YearLocator(3))
    elif n_yr>6: ax.xaxis.set_major_locator(mdates.YearLocator(2))
    else: ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(which='minor',length=1.5,width=0.3)
    ax.tick_params(axis='x',labelsize=6)
    ax.tick_params(axis='y',labelsize=6)
    # Tight Y axis
    vmin,vmax=vals.min(),vals.max()
    pad=(vmax-vmin)*0.15 if vmax>vmin else 0.05
    ax.set_ylim(vmin-pad, vmax+pad)
    ax.margins(x=0.01)

def make_cover(pdf,title,subtitle,n,dr,extra=None):
    fig=plt.figure(figsize=(11.69,8.27))
    ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off')
    ax.plot([0.08,0.92],[0.91,0.91],color=C['blue'],lw=3,solid_capstyle='round')
    ax.text(0.5,0.76,title,fontsize=24,fontweight='bold',color=C['title'],ha='center')
    ax.text(0.5,0.65,subtitle,fontsize=11,color=C['sub'],ha='center',linespacing=1.8)
    lines=[f"{n} Burgiss MSCI private asset indices  |  {dr}",
           "Expanding calibration window (up to 1,428 weeks), monthly step",
           "Alpha/beta fixed from proxy-on-market regression",
           "Remaining 6 SSM parameters estimated via Nelder-Mead MLE",
           f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    if extra: lines=extra+[""]+lines
    for i,l in enumerate(lines):
        ax.text(0.5,0.48-i*0.042,l,fontsize=9,color=C['sub'],ha='center')
    ax.text(0.5,0.05,"EdgeLab / Evooq  |  CONFIDENTIAL",fontsize=8,color=C['light'],ha='center')
    pdf.savefig(fig,dpi=150);plt.close(fig)

def plot_single(ax,sub,col,color,asset,mapping):
    ccy,name=parse_fund(asset)
    m=mapping.get(asset,{})
    etp=m.get('etp','?'); broad=m.get('broad','?')
    ft=sub.iloc[0].get('fund_type','')
    last=sub.iloc[-1]

    vals=sub[col].dropna()
    ax.plot(sub['as_of_date'],sub[col],color=color,lw=1.3,zorder=3)
    # Reference line at mean
    if len(vals)>0:
        ax.axhline(y=vals.mean(),color=color,lw=0.4,ls='--',alpha=0.4,zorder=1)

    setup_ax(ax,sub['as_of_date'],vals)

    # Title line 1: fund name
    ax.set_title(f"{name}  [{ccy}]",fontsize=8.5,fontweight='bold',color=C['title'],loc='left',pad=12)
    # Title line 2: regression info with tickers
    if col=='beta_ols':
        reg_text=f"r({etp}) = alpha + beta * r({broad}) + eps"
    elif col=='chowlin_mkt_coeff':
        reg_text=f"Chow-Lin market coeff:  r*_daily ~ r({broad}) + r({etp})"
    elif col=='chowlin_sum':
        reg_text=f"Chow-Lin total:  coeff_mkt({broad}) + coeff_prx({etp})"
    elif col=='chowlin_prx_coeff':
        reg_text=f"Chow-Lin proxy coeff:  r*_daily ~ r({broad}) + r({etp})"
    else:
        reg_text=f"MLE:  r({etp}) = beta_c * eta_fund + psi + noise"
    ax.text(0.0,1.015,reg_text,transform=ax.transAxes,fontsize=6,
            color=C['sub'],va='bottom',family='monospace')

    # Bottom stats
    if len(vals)>0:
        st=(f"mean={vals.mean():.4f}  std={vals.std():.4f}  "
            f"[{vals.min():.4f}, {vals.max():.4f}]  last={vals.iloc[-1]:.4f}  "
            f"NAV={int(last.get('calib_nav_count',0))}")
        ax.set_xlabel(st,fontsize=5,color=C['light'],labelpad=2)

def plot_combined(ax,sub,asset,mapping):
    ccy,name=parse_fund(asset)
    m=mapping.get(asset,{})
    etp=m.get('etp','?'); broad=m.get('broad','?')

    v_ols=sub['beta_ols'].dropna()
    v_c=sub['beta_c'].dropna()
    all_vals=pd.concat([v_ols,v_c])

    ax.plot(sub['as_of_date'],sub['beta_ols'],color=C['blue'],lw=1.3,
            label=f'beta_ols ({etp}~{broad})',zorder=3)
    ax.plot(sub['as_of_date'],sub['beta_c'],color=C['red'],lw=1.3,
            label=f'beta_c ({etp}~fund)',zorder=3)

    setup_ax(ax,sub['as_of_date'],all_vals)

    ax.set_title(f"{name}  [{ccy}]",fontsize=8.5,fontweight='bold',color=C['title'],loc='left',pad=12)
    ax.text(0.0,1.015,f"Proxy: {etp}  |  Market: {broad}",
            transform=ax.transAxes,fontsize=6,color=C['sub'],va='bottom')
    ax.legend(fontsize=5.5,loc='best',framealpha=0.95,edgecolor=C['grid'],fancybox=False)

    if len(v_ols)>0 and len(v_c)>0:
        st=(f"ols: {v_ols.mean():.3f}+/-{v_ols.std():.3f} last={v_ols.iloc[-1]:.3f}  |  "
            f"c: {v_c.mean():.3f}+/-{v_c.std():.3f} last={v_c.iloc[-1]:.3f}")
        ax.set_xlabel(st,fontsize=5,color=C['light'],labelpad=2)

def gen_pdf(df,mapping,assets,plot_fn,path,title,subtitle,extra=None):
    dr=f"{df['as_of_date'].min().strftime('%b %Y')} to {df['as_of_date'].max().strftime('%b %Y')}"
    n_pg=(len(assets)+3)//4
    cur_ft=None
    with PdfPages(path) as pdf:
        make_cover(pdf,title,subtitle,len(assets),dr,extra)
        for pg in range(n_pg):
            batch=assets[pg*4:(pg+1)*4]
            fig,axes=plt.subplots(2,2,figsize=(11.69,8.27))
            fig.subplots_adjust(left=0.06,right=0.97,top=0.92,bottom=0.05,hspace=0.45,wspace=0.18)
            # Section header
            ft=df[df['asset_id']==batch[0]].iloc[0].get('fund_type','')
            fig.text(0.5,0.965,ft,fontsize=10,color=C['blue'],ha='center',fontweight='bold')
            for idx,ax in enumerate(axes.flat):
                if idx<len(batch):
                    s=df[df['asset_id']==batch[idx]].sort_values('as_of_date')
                    if len(s)>=3: plot_fn(ax,break_gaps(s),batch[idx],mapping)
                    else: ax.axis('off')
                else: ax.axis('off')
            fig.text(0.98,0.005,f"{pg+2}/{n_pg+1}",fontsize=6,color=C['light'],ha='right')
            pdf.savefig(fig,dpi=150);plt.close(fig)
    print(f"  PDF: {path} ({n_pg} pages, {len(assets)} funds)")

def plot_chowlin(ax,sub,asset,mapping):
    ccy,name=parse_fund(asset)
    m=mapping.get(asset,{})
    etp=m.get('etp','?'); broad=m.get('broad','?')
    v_m=sub['chowlin_mkt_coeff'].dropna()
    v_p=sub['chowlin_prx_coeff'].dropna()
    all_v=pd.concat([v_m,v_p])
    ax.plot(sub['as_of_date'],sub['chowlin_mkt_coeff'],color='#2E7D32',lw=1.3,
            label=f'market ({broad})',zorder=3)
    ax.plot(sub['as_of_date'],sub['chowlin_prx_coeff'],color='#E65100',lw=1.3,
            label=f'proxy ({etp})',zorder=3)
    setup_ax(ax,sub['as_of_date'],all_v)
    ax.set_title(f"{name}  [{ccy}]",fontsize=8.5,fontweight='bold',color=C['title'],loc='left',pad=12)
    ax.text(0.0,1.015,f"Chow-Lin: weekly r* -> daily via r({broad}) + r({etp})",
            transform=ax.transAxes,fontsize=6,color=C['sub'],va='bottom',family='monospace')
    ax.legend(fontsize=5.5,loc='best',framealpha=0.95,edgecolor=C['grid'],fancybox=False)
    if len(v_m)>0 and len(v_p)>0:
        st=(f"mkt: {v_m.mean():.3f}+/-{v_m.std():.3f} last={v_m.iloc[-1]:.3f}  |  "
            f"prx: {v_p.mean():.3f}+/-{v_p.std():.3f} last={v_p.iloc[-1]:.3f}")
        ax.set_xlabel(st,fontsize=5,color=C['light'],labelpad=2)


def main():
    if len(sys.argv)<3:
        print(f"Usage: python3 {sys.argv[0]} <rolling_params.csv> <etp_mapping.csv>");sys.exit(1)
    print("="*60);print("Rolling Beta Analysis v4");print("="*60)
    df=load_params(sys.argv[1]);mapping=load_mapping(sys.argv[2])
    print(f"Data: {len(df)} rows, {df['asset_id'].nunique()} assets, {df['as_of_date'].nunique()} dates")
    assets=sort_assets(df['asset_id'].unique(),df,mapping)
    dirs={k:os.path.join(OUTPUT_ROOT,v) for k,v in
          [('ols','1_beta_ols'),('c','2_beta_c'),('cmb','3_combined'),('raw','raw_data')]}
    for d in dirs.values(): os.makedirs(d,exist_ok=True)
    # Raw
    print("\n[0] Raw data")
    df.to_csv(os.path.join(dirs['raw'],'rolling_params_full.csv'),index=False)
    for c in ['beta_ols','beta_c']:
        w=df.pivot_table(index='as_of_date',columns='asset_id',values=c,aggfunc='first')
        w.index.name='Date';w.to_csv(os.path.join(dirs['raw'],f'{c}_wide.csv'),float_format='%.10f')
    # PDFs
    print("\n[1/3] beta_ols")
    w=df.pivot_table(index='as_of_date',columns='asset_id',values='beta_ols',aggfunc='first')
    w.index.name='Date';w.to_csv(os.path.join(dirs['ols'],'beta_ols_wide.csv'),float_format='%.10f')
    gen_pdf(df,mapping,assets,
            lambda ax,s,a,m: plot_single(ax,s,'beta_ols',C['blue'],a,m),
            os.path.join(dirs['ols'],'beta_ols_rolling.pdf'),
            'Rolling Dimson Beta (SSM)',
            'De-smoothed market sensitivity from State-Space Model\non broad market index weekly returns',
            extra=['r(ETP_proxy) = alpha + beta_ols * r(Market_index) + epsilon'])
    print("\n[2/3] beta_c")
    w=df.pivot_table(index='as_of_date',columns='asset_id',values='beta_c',aggfunc='first')
    w.index.name='Date';w.to_csv(os.path.join(dirs['c'],'beta_c_wide.csv'),float_format='%.10f')
    gen_pdf(df,mapping,assets,
            lambda ax,s,a,m: plot_single(ax,s,'beta_c',C['red'],a,m),
            os.path.join(dirs['c'],'beta_c_rolling.pdf'),
            'Rolling Proxy Sensitivity (MLE)',
            'MLE-estimated loading of proxy return on fund latent\nidiosyncratic return (SSM observation equation)',
            extra=['r(ETP_proxy) = beta_c * eta_fund + psi + d + F_c * sqrt(h) * eps'])
    print("\n[3/3] combined")
    comb=df.pivot_table(index='as_of_date',columns='asset_id',values=['beta_ols','beta_c'],aggfunc='first')
    comb.index.name='Date';comb.to_csv(os.path.join(dirs['cmb'],'beta_ols_and_beta_c_wide.csv'),float_format='%.10f')
    gen_pdf(df,mapping,assets,plot_combined,
            os.path.join(dirs['cmb'],'beta_ols_and_beta_c_rolling.pdf'),
            'Rolling Betas: OLS + MLE',
            'Blue: beta_ols (ETP proxy ~ market index, OLS)\nRed: beta_c (ETP proxy ~ fund idiosyncratic, MLE)')
    has_cl = 'chowlin_mkt_coeff' in df.columns
    if has_cl:
        # 4. Chow-Lin market coeff only
        print("\n[4/6] chowlin market")
        d4=os.path.join(OUTPUT_ROOT,'4_chowlin_market');os.makedirs(d4,exist_ok=True)
        w=df.pivot_table(index='as_of_date',columns='asset_id',values='chowlin_mkt_coeff',aggfunc='first')
        w.index.name='Date';w.to_csv(os.path.join(d4,'chowlin_mkt_coeff_wide.csv'),float_format='%.10f')
        gen_pdf(df,mapping,assets,
                lambda ax,s,a,m: plot_single(ax,s,'chowlin_mkt_coeff','#2E7D32',a,m),
                os.path.join(d4,'chowlin_market_rolling.pdf'),
                'Rolling Chow-Lin Market Coefficient',
                'Broad market index loading in weekly-to-daily disaggregation\nr*_daily = intercept + coeff_mkt * r(market) + coeff_prx * r(proxy)',
                extra=['Coefficient on market index daily returns in Chow-Lin regression'])
        # 5. Chow-Lin proxy coeff only
        print("\n[5/6] chowlin proxy")
        d5=os.path.join(OUTPUT_ROOT,'5_chowlin_proxy');os.makedirs(d5,exist_ok=True)
        w=df.pivot_table(index='as_of_date',columns='asset_id',values='chowlin_prx_coeff',aggfunc='first')
        w.index.name='Date';w.to_csv(os.path.join(d5,'chowlin_prx_coeff_wide.csv'),float_format='%.10f')
        gen_pdf(df,mapping,assets,
                lambda ax,s,a,m: plot_single(ax,s,'chowlin_prx_coeff','#E65100',a,m),
                os.path.join(d5,'chowlin_proxy_rolling.pdf'),
                'Rolling Chow-Lin Proxy Coefficient',
                'ETP proxy loading in weekly-to-daily disaggregation\nr*_daily = intercept + coeff_mkt * r(market) + coeff_prx * r(proxy)',
                extra=['Coefficient on ETP proxy daily returns in Chow-Lin regression'])
        # 6. Chow-Lin both together
        print("\n[6/6] chowlin combined")
        d6=os.path.join(OUTPUT_ROOT,'6_chowlin_combined');os.makedirs(d6,exist_ok=True)
        for c in ['chowlin_mkt_coeff','chowlin_prx_coeff']:
            w=df.pivot_table(index='as_of_date',columns='asset_id',values=c,aggfunc='first')
            w.index.name='Date';w.to_csv(os.path.join(d6,f'{c}_wide.csv'),float_format='%.10f')
        gen_pdf(df,mapping,assets,plot_chowlin,
                os.path.join(d6,'chowlin_combined_rolling.pdf'),
                'Rolling Chow-Lin Coefficients (Market + Proxy)',
                'Regression coefficients from weekly-to-daily temporal disaggregation\nGreen: market index loading    Orange: ETP proxy loading',
                extra=['r*_daily = intercept + coeff_mkt * r(market) + coeff_prx * r(proxy) + uniform_residual'])
    if has_cl:
        print("\n[7/7] chowlin sum")
        d7=os.path.join(OUTPUT_ROOT,'7_chowlin_sum');os.makedirs(d7,exist_ok=True)
        w=df.pivot_table(index='as_of_date',columns='asset_id',values='chowlin_sum',aggfunc='first')
        w.index.name='Date';w.to_csv(os.path.join(d7,'chowlin_sum_wide.csv'),float_format='%.10f')
        gen_pdf(df,mapping,assets,
                lambda ax,s,a,m: plot_single(ax,s,'chowlin_sum','#4527A0',a,m),
                os.path.join(d7,'chowlin_sum_rolling.pdf'),
                'Rolling Chow-Lin Total Beta (Market + Proxy)',
                'Sum of market and proxy Chow-Lin disaggregation coefficients\nCross-check: should approximate Dimson Beta (SSM)',
                extra=['chowlin_sum = coeff_mkt + coeff_prx'])
    print(f"\nOutput: {OUTPUT_ROOT}")

if __name__=='__main__': main()

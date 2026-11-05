import tkinter as tk
from tkinter import ttk
import gsav_core as G
TITLE='Money & people'
def build(app,fr):
    rows={}
    for c,h in enumerate(['','Now','New','']): tk.Label(fr,text=h,font=('Segoe UI',13,'bold'),bg='white',fg='#555').grid(row=0,column=c,sticky='w',padx=8)
    for r,f in enumerate(G.FIELDS):
        R=1+r*2
        tk.Label(fr,text=f.label,font=('Segoe UI',18,'bold'),bg='white').grid(row=R,column=0,sticky='w',padx=8,pady=(12,0))
        now=tk.Label(fr,text='-',font=('Segoe UI',16),bg='white',width=14,anchor='w'); now.grid(row=R,column=1,sticky='w',padx=8)
        var=tk.StringVar(); ttk.Entry(fr,textvariable=var,font=('Segoe UI',16),width=12).grid(row=R,column=2,padx=8)
        ttk.Button(fr,text='Max',command=lambda v=var,f=f:v.set(f'{f.maxv:g}')).grid(row=R,column=3,padx=8)
        tk.Label(fr,text=f.note,font=('Segoe UI',12),bg='white',fg='#444').grid(row=R+1,column=0,columnspan=4,sticky='w',padx=8)
        rows[f.id]=(f,now,var)
    def loaded(s):
        for f,now,var in rows.values():
            v=f.get(s); txt=format(v,',.6g'); now.config(text=txt); var.set(f'{v:g}' if abs(v)<1e15 else str(v))
    def collect(vals,eq):
        s=app.save
        for fid,(f,now,var) in rows.items():
            t=var.get().replace(',','').strip()
            if t=='' : continue
            v=G.check_value(f,t)
            if abs(v-f.get(s))>1e-9 and f'{f.get(s):g}'!=t: vals[fid]=v
    app.on_loaded(loaded); app.collectors=getattr(app,'collectors',[])+[collect]

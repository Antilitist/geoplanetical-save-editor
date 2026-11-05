import tkinter as tk
from tkinter import ttk
import gsav_core as G
TITLE='Parliament'
def build(app,fr):
    tk.Label(fr,text='Seats in parliament (all chambers)',font=('Segoe UI',18,'bold'),bg='white').pack(anchor='w')
    box=tk.Label(fr,text='-',font=('Segoe UI',15),bg='white',justify='left',anchor='w'); box.pack(anchor='w',pady=8)
    var=tk.BooleanVar(value=False)
    cb=ttk.Checkbutton(fr,text='Fill parliament with my ruling party (every seat, every chamber)',variable=var); cb.pack(anchor='w',pady=8)
    tk.Label(fr,text=('Seats are reset at the next election from party support.\n'
                      'A snap election (dissolving parliament) also resets them.\n'
                      'Your government becomes a majority, so laws pass.'),font=('Segoe UI',12),bg='white',fg='#444',justify='left').pack(anchor='w')
    ttk.Separator(fr).pack(fill='x',pady=14)
    tk.Label(fr,text='Party support (popularity) - this is what wins elections',font=('Segoe UI',18,'bold'),bg='white').pack(anchor='w')
    sbox=tk.Label(fr,text='-',font=('Segoe UI',15),bg='white',justify='left',anchor='w'); sbox.pack(anchor='w',pady=6)
    svar=tk.BooleanVar(value=False); pct=tk.IntVar(value=70)
    row=tk.Frame(fr,bg='white'); row.pack(anchor='w',fill='x')
    ttk.Checkbutton(row,text='Set my party support to',variable=svar).pack(side='left')
    tk.Scale(row,from_=1,to=99,orient='horizontal',variable=pct,length=360,font=('Segoe UI',12),bg='white',highlightthickness=0,command=lambda _ :svar.set(True)).pack(side='left',padx=8)
    tk.Label(row,text='%',font=('Segoe UI',15),bg='white').pack(side='left')
    tk.Label(fr,text=('Other parties shrink in proportion so everything still adds up to 100%.\n'
                      'The next election uses this number to hand out seats, so 70% usually means a big majority.\n'
                      'It slowly moves with how happy voters are (good economy and approval keep it up).'),font=('Segoe UI',12),bg='white',fg='#444',justify='left').pack(anchor='w')
    def loaded(s):
        var.set(False); lines=[]
        for cid,tot,mine,comp in G.chambers_summary(s.country,s.party_id):
            top=', '.join(f'{k} {v}' for k,v in sorted(comp.items(),key=lambda x:-x[1]))
            lines.append(f'{cid}:  {s.party_id} has {mine} of {tot}     ({top})')
        box.config(text='\n'.join(lines) or 'No chambers in this country')
        svar.set(False); pct.set(70)
        sbox.config(text='   '.join(f"{k} {v*100:.1f}%{'  (you)' if k==s.party_id else ''}" for k,v in sorted(G.support_summary(s.country),key=lambda x:-x[1])))
        cb.config(state='normal' if lines else 'disabled')
    def collect(vals,eq):
        if var.get(): vals[G.LEG_KEY]=True
        if svar.get(): vals[G.SUP_KEY]=int(pct.get())
    app.on_loaded(loaded); app.collectors=getattr(app,'collectors',[])+[collect]

import tkinter as tk
from tkinter import ttk
import gsav_core as G
TITLE='Arsenal'
def build(app,fr):
    top=tk.Frame(fr,bg='white'); top.pack(fill='x')
    tk.Label(top,text='Military equipment',font=('Segoe UI',18,'bold'),bg='white').pack(side='left')
    rows={}
    ttk.Button(top,text='Fill all',command=lambda:[r[2].set(str(r[3]+r[4])) for r in rows.values() if r[5]]).pack(side='right')
    tk.Label(fr,text="The game has no limit on equipment.\nMax adds the size of the world's biggest army for that type.\nYou can type any number.  Upkeep cost updates in game later.",justify='left',wraplength=900,font=('Segoe UI',13),bg='white',fg='#444').pack(anchor='w')
    cv=tk.Canvas(fr,bg='white',highlightthickness=0); sb=ttk.Scrollbar(fr,orient='vertical',command=cv.yview)
    inner=tk.Frame(cv,bg='white'); inner.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all')))
    cv.create_window((0,0),window=inner,anchor='nw'); cv.configure(yscrollcommand=sb.set)
    cv.pack(side='left',fill='both',expand=True,pady=6); sb.pack(side='right',fill='y')
    cv.bind_all('<MouseWheel>',lambda e:cv.yview_scroll(int(-e.delta/120),'units'))
    for c,h in enumerate(['Type','Now','New','']): tk.Label(inner,text=h,font=('Segoe UI',13,'bold'),bg='white',fg='#555').grid(row=0,column=c,sticky='w',padx=8)
    for r,(cid,info) in enumerate(G.EQUIP.items()):
        tk.Label(inner,text=info['name'],font=('Segoe UI',15),bg='white').grid(row=r+1,column=0,sticky='w',padx=8,pady=3)
        now=tk.Label(inner,text='-',font=('Segoe UI',15),bg='white',width=10,anchor='e'); now.grid(row=r+1,column=1,padx=8)
        var=tk.StringVar(); ent=ttk.Entry(inner,textvariable=var,font=('Segoe UI',15),width=10); ent.grid(row=r+1,column=2,padx=8)
        btn=ttk.Button(inner,text='Max'); btn.grid(row=r+1,column=3,padx=8)
        rows[cid]=[now,ent,var,0,int(info.get('worldMax',0)),False,btn]
        btn.config(command=lambda c=cid:rows[c][2].set(str(rows[c][3]+rows[c][4])))
    def loaded(s):
        for cid,name,tot,ok,wm in G.arsenal(s):
            R=rows[cid]; R[3]=round(tot); R[5]=ok; R[0].config(text=f'{R[3]:,}')
            R[2].set(str(R[3]) if ok else 'no navy'); st='normal' if ok else 'disabled'; R[1].config(state=st); R[6].config(state=st)
    def collect(vals,eq):
        for cid,R in rows.items():
            if not R[5]: continue
            t=R[2].get().replace(',','').strip(); v=G.check_equip(cid,t)
            if v!=R[3]: eq[cid]=v
    app.on_loaded(loaded); app.collectors=getattr(app,'collectors',[])+[collect]

import tkinter as tk
from tkinter import ttk,messagebox
import gsav_core as G
TITLE='Wars (test)'
def build(app,fr):
    tk.Label(fr,text='EXPERIMENTAL - not tested in game',font=('Segoe UI',16,'bold'),bg='#fff3c4',fg='#7a4b00',padx=10,pady=4).pack(anchor='w')
    tv=ttk.Treeview(fr,columns=('enemy','me','A','B'),show='headings',height=3)
    for c,t,w in (('enemy','Enemy',200),('me','My side',110),('A','Side A',250),('B','Side B',250)): tv.heading(c,text=t); tv.column(c,width=w,anchor='w')
    tv.pack(fill='x',pady=8)
    none=tk.Label(fr,text='',font=('Segoe UI',18,'bold'),bg='white'); none.pack(anchor='w')
    row=tk.Frame(fr,bg='white'); row.pack(fill='x',pady=6)
    tk.Label(row,text='Country',font=('Segoe UI',15,'bold'),bg='white').pack(side='left')
    names=sorted(((v,k) for k,v in G.COUNTRY_NAMES.items() if k.isdigit()),key=lambda x:x[0])
    cvar=tk.StringVar(); cb=ttk.Combobox(row,textvariable=cvar,values=[n for n,k in names],font=('Segoe UI',15),width=24); cb.pack(side='left',padx=8)
    def filt(e=None):
        t=cvar.get().lower(); cb['values']=[n for n,k in names if t in n.lower()] or [n for n,k in names]
    cb.bind('<KeyRelease>',filt)
    tk.Label(row,text='Side',font=('Segoe UI',15,'bold'),bg='white').pack(side='left',padx=(16,4))
    svar=tk.StringVar(value='A'); ttk.Combobox(row,textvariable=svar,values=['A','B'],state='readonly',width=3,font=('Segoe UI',15)).pack(side='left')
    tk.Label(fr,text='Changes to save:',font=('Segoe UI',15,'bold'),bg='white').pack(anchor='w',pady=(12,0))
    lb=tk.Listbox(fr,font=('Segoe UI',14),height=3); lb.pack(fill='x')
    def add():
        sel=tv.selection()
        if not sel: messagebox.showinfo('Pick a war','Click a war in the list first.'); return
        key=next((k for n,k in names if n==cvar.get()),None)
        if not key: messagebox.showinfo('Pick a country','Choose a country from the list.'); return
        wid=sel[0]; w=next(x for x in app.wars if x['id']==wid)
        if key==app.save.pk: messagebox.showerror('No','That is your own country.'); return
        if key in w['participants'] or key in w['A'] or key in w['B'] or any(a[0]==wid and a[1]==key for a in app.war_adds):
            messagebox.showerror('No',f'{cvar.get()} is already in this war.'); return
        if not app.save.has_country(key): messagebox.showerror('No','That country is not in this save.'); return
        app.war_adds.append((wid,key,svar.get())); lb.insert('end',f'Add {cvar.get()} to side {svar.get()}  ({w["aName"]} vs {w["bName"]})')
    bb=tk.Frame(fr,bg='white'); bb.pack(fill='x',pady=6)
    ttk.Button(bb,text='Add to war',command=add).pack(side='left')
    ttk.Button(bb,text='Undo last',command=lambda:(app.war_adds.pop(),lb.delete('end')) if app.war_adds else None).pack(side='left',padx=10)
    def loaded(s):
        tv.delete(*tv.get_children()); lb.delete(0,'end'); app.wars=G.player_wars(s)
        nm=lambda ks:', '.join(G.country_name(k) for k in ks[:4])+(f' +{len(ks)-4}' if len(ks)>4 else '')
        for w in app.wars: tv.insert('','end',iid=w['id'],values=(w['enemy'],w['my_side'],nm(w['A']),nm(w['B'])))
        if app.wars: tv.selection_set(app.wars[0]['id'])
        none.config(text='' if app.wars else 'No wars')
    app.on_loaded(loaded)

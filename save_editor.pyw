"""Geoplanetical Save Editor (tkinter). Double-click 'Geoplanetical Save Editor.bat'.
Never overwrites: always writes a new Mira_edit_00N.gsav next to the save.
Add a tab: put a module in tabs\\ with  TITLE='...'  and  build(app, frame) ; it is picked up automatically."""
import os,sys,threading,traceback,importlib,glob,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import gsav_core as G
F_BIG=('Segoe UI',15); F_H=('Segoe UI',18,'bold'); F_NOTE=('Segoe UI',12); F_BTN=('Segoe UI',15,'bold')
BG='#ffffff'; FG='#111111'
class App:
    def __init__(self,root,saves_dir):
        self.root=root; self.saves_dir=saves_dir; self.save=None; self.war_adds=[]; self.tab_hooks=[]
        root.title('Geoplanetical Save Editor'); root.geometry('1000x820'); root.configure(bg=BG)
        st=ttk.Style(); st.theme_use('clam')
        st.configure('.',font=F_BIG,background=BG,foreground=FG); st.configure('TNotebook.Tab',font=F_BTN,padding=(18,8))
        st.configure('TButton',font=F_BIG,padding=(10,4)); st.configure('Big.TButton',font=F_BTN,padding=(16,10),background='#1f8b3a',foreground='white')
        st.map('Big.TButton',background=[('active','#25a245'),('disabled','#9fbfa7')])
        st.configure('TCheckbutton',font=F_BIG); st.configure('Treeview',font=F_BIG,rowheight=34); st.configure('Treeview.Heading',font=F_BTN)
        top=tk.Frame(root,bg=BG,padx=16,pady=10); top.pack(fill='x')
        tk.Label(top,text='Save file',font=F_H,bg=BG).grid(row=0,column=0,sticky='w')
        self.pick=tk.StringVar(); self.cb=ttk.Combobox(top,textvariable=self.pick,state='readonly',font=F_BIG,width=48)
        self.cb.grid(row=0,column=1,padx=10,sticky='we'); self.cb.bind('<<ComboboxSelected>>',lambda e:self.load(self.files[self.cb.current()]))
        ttk.Button(top,text='Browse...',command=self.browse).grid(row=0,column=2)
        top.columnconfigure(1,weight=1)
        self.info=tk.Label(top,text='',font=F_H,bg=BG,fg='#0b3d91',anchor='w',justify='left'); self.info.grid(row=1,column=0,columnspan=3,sticky='w',pady=(10,0))
        self.status=tk.Label(root,text='',font=F_BIG,bg='#eeeeee',anchor='w',padx=16,pady=6); self.status.pack(fill='x',side='bottom')
        bot=tk.Frame(root,bg=BG,padx=16,pady=10); bot.pack(fill='x',side='bottom')
        self.clear=tk.BooleanVar(value=True); self.reset=tk.BooleanVar(value=False)
        ttk.Checkbutton(bot,text='Clear cheat flag',variable=self.clear).pack(side='left')
        ttk.Checkbutton(bot,text='Reset cheat switches',variable=self.reset).pack(side='left',padx=20)
        self.save_btn=ttk.Button(bot,text='Save as new file',style='Big.TButton',command=self.do_save); self.save_btn.pack(side='right')
        
        self.nb=ttk.Notebook(root); self.nb.pack(fill='both',expand=True,padx=16)
        for mod in self.tab_modules():
            fr=tk.Frame(self.nb,bg=BG,padx=14,pady=12); self.nb.add(fr,text=mod.TITLE); mod.build(self,fr)
        self.refresh_files()
    def tab_modules(self):
        d=os.path.join(os.path.dirname(os.path.abspath(__file__)),'tabs'); mods=[]
        for f in sorted(glob.glob(os.path.join(d,'*.py'))):
            n=os.path.splitext(os.path.basename(f))[0]
            if n.startswith('_'): continue
            mods.append(importlib.import_module('tabs.'+n))
        return mods
    def on_loaded(self,fn): self.tab_hooks.append(fn)
    def busy(self,on,msg=''):
        self.status.config(text=msg); self.save_btn.config(state='disabled' if on else 'normal')
        self.root.config(cursor='watch' if on else '')
    def refresh_files(self,select=None):
        self.files=G.list_saves(self.saves_dir)
        self.cb['values']=[f'{os.path.basename(f)}   ({time.strftime("%b %d %H:%M",time.localtime(os.path.getmtime(f)))})' for f in self.files]
        if self.files:
            i=self.files.index(select) if select in self.files else 0; self.cb.current(i); self.load(self.files[i])
        else: self.status.config(text='No saves found. Use Browse.')
    def browse(self):
        f=filedialog.askopenfilename(initialdir=self.saves_dir,filetypes=[('Geoplanetical save','*.gsav')])
        if f:
            if f not in self.files: self.files.insert(0,f); self.cb['values']=[os.path.basename(f)]+list(self.cb['values'])
            self.cb.current(self.files.index(f)); self.load(f)
    def run_bg(self,work,done,msg):
        self.busy(True,msg)
        def t():
            try: r=work(); self.root.after(0,lambda:(self.busy(False),done(r)))
            except Exception as e:
                tb=traceback.format_exc(); self.root.after(0,lambda:(self.busy(False,'Error'),messagebox.showerror('Problem',f'{e}'),print(tb)))
        threading.Thread(target=t,daemon=True).start()
    def load(self,path):
        self.info.config(text='Loading...')
        def done(s):
            self.save=s; self.war_adds=[]
            self.info.config(text=f'Country: {s.country_label}     Party: {s.party_name}     Day {s.day}')
            for h in self.tab_hooks: h(s)
            self.status.config(text=f'Loaded {os.path.basename(path)}')
        self.run_bg(lambda:G.Save(path),done,'Loading save... (a few seconds)')
    def collect(self):
        vals={}; eq={}
        for h in getattr(self,'collectors',[]): h(vals,eq)
        return vals,eq
    def do_save(self):
        if not self.save: return
        try: vals,eq=self.collect()
        except G.GsavError as e: messagebox.showerror('Check the numbers',str(e)); return
        s=self.save; adds=list(self.war_adds)
        def done(r):
            out,log=r; messagebox.showinfo('Saved',f'Saved:\n{os.path.basename(out)}\n\n'+'\n'.join(l for l in log if 'recompressed' not in l))
            self.status.config(text=f'Saved {os.path.basename(out)}'); self.refresh_files(select=out)
        self.run_bg(lambda:G.save_as_new(s,vals,eq,adds,self.clear.get(),self.reset.get(),folder=self.out_folder),done,'Saving and checking... (about 30 seconds)')
    out_folder=None
def main():
    a=sys.argv[1:]; saves=G.SAVES_DIR; shot=None
    if '--saves' in a: saves=a[a.index('--saves')+1]
    if '--screenshot' in a: shot=a[a.index('--screenshot')+1]
    root=tk.Tk(); app=App(root,saves)
    if '--out' in a: app.out_folder=a[a.index('--out')+1]
    if shot:
        tabs=[int(x) for x in a[a.index('--tab')+1].split(',')] if '--tab' in a else [0]
        def snap(k=0,tries=0):
            if app.save is None and tries<240: return root.after(500,lambda:snap(k,tries+1))
            app.nb.select(tabs[k]); root.update()
            if '--scroll' in sys.argv:
                for cv in [w for w in app.nb.nametowidget(app.nb.select()).winfo_children() if w.winfo_class()=='Canvas']: cv.yview_moveto(float(sys.argv[sys.argv.index('--scroll')+1]))
            root.update(); root.lift(); root.attributes('-topmost',True); root.update()
            def grab():
                from PIL import ImageGrab
                x,y,w,h=root.winfo_rootx(),root.winfo_rooty(),root.winfo_width(),root.winfo_height()
                fn=shot if k==0 else shot.replace('.png',f'_{k}.png'); ImageGrab.grab(bbox=(x,y,x+w,y+h),all_screens=True).save(fn); print('saved',fn)
                if k+1<len(tabs): snap(k+1,tries)
                else: root.destroy()
            root.after(1200,grab)
        root.after(500,snap)
    root.mainloop()
if __name__=='__main__': main()

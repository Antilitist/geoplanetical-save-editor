"""gsav_core - shared Geoplanetical .gsav code (parse, verify, repack, safe text edits)
and the save-editor engine (fields registry, arsenal, wars).
Used by: save_editor.pyw, ../clear_cheat_flag.py, ../edit_save.py.
Rule: every edit is a targeted text substitution in the raw JSON, then re-parsed and
compared with the expected object, so only the intended value can change."""
import os,re,json,glob,copy,struct,zlib,hashlib
import zstandard
HERE=os.path.dirname(os.path.abspath(__file__))
SAVES_DIR=os.path.join(os.environ.get('APPDATA') or os.path.join(os.path.expanduser('~'),'AppData','Roaming'),'Geoplanetical','saves')
NUM=rb'-?[0-9][0-9.eE+-]*'
CLEAN_CI={"schema":1,"achievementsEligible":True,"firstCheatId":None,"firstCheatDay":None,"usedCheatIds":[]}
CLEAN_CHEATS={"schema":1,"autoAdopt":False,"fastBuild":False,"fastSpace":False,"instantSpace":False,"fastResearch":False,"fullIntel":False,"yesman":False,"lockLove":False,"sanctionImmunity":False}
MIRROR_KEYS=[b'achievementsEligible',b'usedCheatIds',b'firstCheatId',b'firstCheatDay',b'campaignIntegrity']
PARTY_CAP=10000.0
class GsavError(Exception): pass
# ---------------- low level (shared with legacy scripts) ----------------
def ser(o): return json.dumps(o,separators=(',',':'),ensure_ascii=False).encode()
def parse(d):
    if d[:6]!=b'GEOSAV': raise SystemExit('not a GEOSAV file')
    ml,cnt,mo=struct.unpack('<IHH',d[0x10:0x18]); t=mo+ml; secs=[]
    for i in range(cnt):
        o=t+i*80; c,off,cs,rs=struct.unpack('<4Q',d[o+16:o+48]); secs.append([d[o:o+16],c,off,cs,rs,d[o+48:o+80]])
    return ml,mo,t,secs
def name(s): return s[0].rstrip(b'\0').decode()
def dec(c,b,rs): return zlib.decompress(b) if c==2 else zstandard.ZstdDecompressor().decompress(b,max_output_size=rs)
def enc(c,raw,orig_raw,orig_comp):
    """returns (blob, how). zlib: level that reproduces the original bytes; zstd: level 3."""
    if c==2:
        lvl=next((l for l in range(10) if zlib.compress(orig_raw,l)==orig_comp),6); return zlib.compress(raw,lvl),('zlib',lvl)
    if c==3: return zstandard.ZstdCompressor(level=3).compress(raw),('zstd',3)
    raise SystemExit(f'unknown codec {c}')
def verify(d):
    ml,mo,t,secs=parse(d); r={'header_sha256':hashlib.sha256(d[mo:t+80*len(secs)]).digest()==d[0x30:0x50],
      'file_size':struct.unpack('<Q',d[0x20:0x28])[0]==len(d),'raw_total':struct.unpack('<Q',d[0x28:0x30])[0]==sum(s[4] for s in secs)}
    for s in secs:
        b=d[s[2]:s[2]+s[3]]; r[name(s)+'_sha256']=hashlib.sha256(b).digest()==s[5]; r[name(s)+'_rawsize']=len(dec(s[1],b,s[4]))==s[4]
    return r
def repack(d,raws,origs=None):
    """raws: {section_index: new_raw_bytes}. Returns (new_file_bytes, log)."""
    ml,mo,t,secs=parse(d); tbl=t+80*len(secs); first=min(s[2] for s in secs); nd=bytearray(d[:first]); pos=first; log=[]
    for i,s in sorted(enumerate(secs),key=lambda x:x[1][2]):
        ob=d[s[2]:s[2]+s[3]]
        if i in raws:
            orig=(origs or {}).get(i) or dec(s[1],ob,s[4]); blob,how=enc(s[1],raws[i],orig,ob); rs=len(raws[i]); log.append(f'{name(s)} recompressed {how}')
        else: blob=ob; rs=s[4]
        o=t+i*80; nd[o:o+80]=s[0]+struct.pack('<4Q',s[1],pos,len(blob),rs)+hashlib.sha256(blob).digest(); nd+=blob; pos+=len(blob)
    nd[0x20:0x28]=struct.pack('<Q',len(nd)); nd[0x28:0x30]=struct.pack('<Q',sum(x[4] for x in parse(nd)[3]))
    nd[0x30:0x50]=hashlib.sha256(nd[mo:tbl]).digest(); return bytes(nd),log
def apply(raw,path,value):
    """edit_save-style number substitution on a whole section (bytes). path 'a.b.c' or 'row:<accountId>'."""
    obj=json.loads(raw); vb=json.dumps(value).encode()
    if path.startswith('row:'):
        key=path[4:]; m=list(re.finditer(rb'(\["'+re.escape(key.encode())+rb'",(?:"[^"]*",){6})('+NUM+rb')',raw)); assert len(m)==1,f'{path}: {len(m)} matches'
        cands=[(m[0].start(2),m[0].end(2))]
        def getset(o,v=None):
            row=next(r for r in o['accounts']['rows'] if r[0]==key)
            if v is not None: row[7]=v
            return row[7]
    else:
        keys=path.split('.')
        def getset(o,v=None):
            for k in keys[:-1]: o=o[k]
            if v is not None: o[keys[-1]]=v
            return o[keys[-1]]
        start=0
        if len(keys)>1:
            a=raw.find(json.dumps(keys[0]).encode()+b':{'); start=max(a,0)
        cands=[(m.start(1),m.end(1)) for m in re.finditer(re.escape(json.dumps(keys[-1]).encode())+rb':('+NUM+rb')',raw[start:])][:50]
        cands=[(a+start,b+start) for a,b in cands]
    old=getset(obj); exp=json.loads(raw); getset(exp,value)
    for a,b in cands:
        new=raw[:a]+vb+raw[b:]
        try: o2=json.loads(new)
        except Exception: continue
        if o2==exp: return new,old
    raise SystemExit(f'no safe substitution for {path}')
def nO(cheats,ci):
    """Mirror of the game's validator (coherence rules)."""
    assert isinstance(cheats,dict) and cheats.get('schema')==1,'cheats.schema'
    assert ci.get('schema')==1,'schema'
    u=ci['usedCheatIds']; assert isinstance(u,list) and all(isinstance(x,str) for x in u) and len(set(u))==len(u),'usedCheatIds'
    q=len(u)>0
    assert not(ci['achievementsEligible']==q or q!=(ci['firstCheatId'] is not None) or q!=(ci['firstCheatDay'] is not None) or (q and ci['firstCheatId']!=u[0])),'coherence'
    return True
def replace_obj(raw,key,new):
    tag=b'"'+key+b'":'; i=raw.find(tag); assert i>=0 and raw.find(tag,i+1)<0,f'{key}: expected exactly one'
    s=i+len(tag)
    old,end=json.JSONDecoder().raw_decode(raw[s:].decode('utf8')); e=s+len(raw[s:].decode('utf8')[:end].encode('utf8'))
    return raw[:s]+ser(new)+raw[e:],old
def next_free(folder,prefix):
    n=1
    while os.path.exists(os.path.join(folder,f'{prefix}{n:03d}.gsav')): n+=1
    return os.path.join(folder,f'{prefix}{n:03d}.gsav')
def ruling_party(c):
    pol=c['pol']; a=((pol.get('institutionState') or {}).get('government') or {}).get('leadPartyId'); b=(c.get('socialMind') or {}).get('leadPartyId')
    if a and b and a!=b: raise SystemExit(f'STOP: ruling party ambiguous: government.leadPartyId={a} socialMind.leadPartyId={b}')
    r=a or b
    if not r: raise SystemExit('STOP: ruling party not found')
    return r,f'pol.institutionState.government.leadPartyId={a}, socialMind.leadPartyId={b}, playerPartyId={pol.get("playerPartyId")}'
def set_party_funds(raw,pk,pid,val):
    obj=json.loads(raw); party=next(x for x in obj[pk]['pol']['parties'] if x['id']==pid); old=party['organization']['treasuryM']
    party['organization']['treasuryM']=val; vb=json.dumps(val).encode()
    a=raw.find(json.dumps(pk).encode()+b':{'); assert a>=0
    for m in re.finditer(rb'"id":'+re.escape(json.dumps(pid).encode()),raw[a:]):
        st=a+m.end(); t=re.search(rb'"treasuryM":('+NUM+rb')',raw[st:st+20000])
        if not t: continue
        new=raw[:st+t.start(1)]+vb+raw[st+t.end(1):]
        try:
            if json.loads(new)==obj: return new,old
        except Exception: pass
    raise SystemExit(f'no safe substitution for party {pid} treasuryM')
# ---------------- editor engine ----------------
_D=json.JSONDecoder()
def sj(o): return json.dumps(o,separators=(',',':'),ensure_ascii=False)
def _load_json(fn,default):
    try: return json.load(open(os.path.join(HERE,fn),encoding='utf-8'))
    except Exception: return default
COUNTRY_NAMES=_load_json('country_names.json',{})
_EQJ=_load_json('equipment_classes.json',{'classes':{}}); EQUIP=_EQJ['classes']; TECH_MODELS=_EQJ.get('techModels',[])
NAVAL={'carrier','sub','destroyer','corvette','amphib'}
EQUIP_LIMIT=1000000
def country_name(k): return COUNTRY_NAMES.get(str(k),str(k))
def list_saves(folder=SAVES_DIR):
    fs=[f for f in glob.glob(os.path.join(folder,'*.gsav')) if os.path.isfile(f)]
    return sorted(fs,key=os.path.getmtime,reverse=True)
def sub_value(text,s,e,key,old,new,expected,check=True):
    """In text[s:e] (one JSON value whose parse must equal `expected` after the edit), replace the value of
    "key": that currently equals `old` with `new`. Returns (new_text,new_e)."""
    tag='"'+key+'":'; cands=[]; i=text.find(tag,s,e)
    while i>=0:
        v=i+len(tag); val,end=_D.raw_decode(text,v)
        if val==old and type(val)==type(old): cands.append((v,end))
        i=text.find(tag,end,e)
    nb=sj(new)
    for v,end in cands:
        t2=text[:v]+nb+text[end:]; e2=e+len(nb)-(end-v)
        if len(cands)==1 and not check: return t2,e2
        try:
            if json.loads(t2[s:e2])==expected: return t2,e2
        except Exception: pass
    raise GsavError(f'no safe place to change "{key}" ({len(cands)} candidates)')
class Save:
    """A loaded save. Only small pieces are parsed (player country ~0.6 MB, aiWars, sim header)."""
    def __init__(self,path):
        self.path=path; self.d=open(path,'rb').read(); v=verify(self.d)
        if not all(v.values()): raise GsavError(f'File check failed: {[k for k,x in v.items() if not x]}')
        self.ml,self.mo,self.t,self.secs=parse(self.d); self.names=[name(s) for s in self.secs]
        self.meta=json.loads(self.d[self.mo:self.mo+self.ml]); self.pk=str(self.meta['playerKey'])
        self.text={}
        core=self.sec('core'); m=re.search(r'"sim":\{"day":(\d+)',core)
        if not m: raise GsavError('day not found')
        self.day=int(m.group(1))
        if core.count('"playerKey":')==1:
            i=core.find('"playerKey":'); ck=str(_D.raw_decode(core,i+12)[0])
            if ck!=self.pk: raise GsavError(f'player mismatch: file says {self.pk}, game data says {ck}')
        self.cs,self.ce,self.country=self.country_span(self.pk)
        self.party_id,_=ruling_party(self.country)
        p=self.party(); self.party_name=f'{p["nameDesc"].get("qual","")} {p["nameDesc"].get("noun","")}'.strip()
        self.country_label=(self.meta.get('nation') or {}).get('name') or country_name(self.pk)
    def sec(self,n):
        if n not in self.text:
            s=self.secs[self.names.index(n)]; self.text[n]=dec(s[1],self.d[s[2]:s[2]+s[3]],s[4]).decode('utf-8')
        return self.text[n]
    def country_span(self,key):
        C=self.sec('countries'); tag='"%s":{'%key; hits=[]; i=C.find(tag)
        while i>=0:
            v,e=_D.raw_decode(C,i+len(tag)-1)
            if isinstance(v,dict) and 'forces' in v and 'pol' in v: hits.append((i+len(tag)-1,e,v))
            i=C.find(tag,i+1)
        if len(hits)!=1: raise GsavError(f'country {key}: found {len(hits)} times')
        return hits[0]
    def has_country(self,key):
        try: self.country_span(str(key)); return True
        except GsavError: return False
    def party(self,c=None): return next(x for x in (c or self.country)['pol']['parties'] if x['id']==self.party_id)
    def cash(self):
        F=self.sec('finance'); m=list(re.finditer(r'\["treasury-cash:%s",'%re.escape(self.pk),F))
        if len(m)!=1: raise GsavError(f'cash row found {len(m)} times')
        row,_=_D.raw_decode(F,m[0].start()); return row[7]
    # ---- wars ----
    def wars_raw(self):
        core=self.sec('core'); i=core.find('"aiWars":'); 
        if i<0 or core.count('"aiWars":')!=1: return []
        v,_=_D.raw_decode(core,i+9); return (v or {}).get('wars') or []
# ---- field registry: add a Field to FIELDS to get a new row in the GUI ----
class Field:
    def __init__(s,id,label,note,get,put,lo,hi,maxv,integer=False):
        s.id,s.label,s.note,s.get,s.put,s.lo,s.hi,s.maxv,s.integer=id,label,note,get,put,lo,hi,maxv,integer
def _put_country(keyfld,anchor=None):
    def put(c,v):
        if anchor: c[anchor]=c[anchor]+(v-c[keyfld])
        c[keyfld]=v
    return put
def _put_party(c,v):
    sv=SaveCtx.cur; next(x for x in c['pol']['parties'] if x['id']==sv.party_id)['organization']['treasuryM']=v
class SaveCtx: cur=None
FIELDS=[
 Field('cash','Cash','USD billions (1000 = $1 trillion).  Max $40T is a safe tested amount, not a game limit.',lambda s:s.cash(),'finance',0,1e7,40000),
 Field('approval','Approval','0 to 100.  Game limit is 100.',lambda s:s.country['approval'],_put_country('approval','_apprAnchor'),0,100,100),
 Field('stability','Stability','0 to 100.  Game limit is 100.',lambda s:s.country['stab'],_put_country('stab','_stabAnchor'),0,100,100),
 Field('party_funds','Party money','USD millions (10000 = $10 billion).  $10B is the game\'s limit.',lambda s:s.party()['organization']['treasuryM'],_put_party,0,PARTY_CAP,PARTY_CAP),
]
def field(id): return next(f for f in FIELDS if f.id==id)
def check_value(f,v):
    try: v=float(v)
    except Exception: raise GsavError(f'{f.label}: please type a number')
    if v!=v or v<f.lo or v>f.hi: raise GsavError(f'{f.label}: must be from {f.lo:g} to {f.hi:g}')
    return int(v) if v==int(v) else v
# ---- arsenal ----
def arsenal(save):
    """[(classId, name, total, editable, worldMax)]"""
    eq=save.country['forces']['equipment']; out=[]
    for cid,info in EQUIP.items():
        lots=eq.get(cid)
        tot=sum(max(0,l.get('units') or 0) for l in lots) if isinstance(lots,list) else 0
        ok=isinstance(lots,list) and (len(lots)>0 or can_add_new(save.country,cid))
        out.append((cid,info.get('name',cid),tot,ok,int(info.get('worldMax',0))))
    return out
def new_model(country,pk,cid):
    """Same rule as the game's add_equipment (r5 in simulation-worker.bundle.js): the country's baseline model
    for the class, upgraded to the best researched tech model. Returns a lot template (units 0)."""
    t=country.get('technology') if isinstance(country.get('technology'),dict) else {}
    ok=t.get('schemaVersion')==2
    b=((t.get('baseline') or {}).get('equipmentModels') or {}).get(cid) if ok else None
    m=dict(b) if isinstance(b,dict) else {'id':f'{cid}.baseline.400','year':2000,'quality':4,'sourceTechId':None}
    if ok:
        nodes=t.get('nodes') or {}
        for tm in TECH_MODELS:
            if tm['classId']!=cid: continue
            pr=(nodes.get(tm['node']) or {}).get('progress',0)
            try: pr=min(100.0,max(0.0,float(pr)))
            except Exception: pr=0.0
            if pr+1e-9>=100 and (tm['quality']>float(m['quality']) or (tm['quality']==float(m['quality']) and tm['year']>int(m['year']))):
                m={'id':tm['modelId'],'year':tm['year'],'quality':tm['quality'],'sourceTechId':tm['node']}
    return {'modelId':str(m['id']),'units':0,'year':int(m['year']),'quality':m['quality'],'sourceTechId':m.get('sourceTechId'),'originKey':str(pk)}
def has_coast_proxy(country):
    eq=country['forces']['equipment']; return any(isinstance(eq.get(n),list) and eq.get(n) for n in NAVAL)
def can_add_new(country,cid):
    """Empty class: can start new stock, except ships for a country with no navy at all (game needs a coast)."""
    return cid not in NAVAL or has_coast_proxy(country)
def check_lots(lots,cid):
    """Same checks the game's load validator does on each lot."""
    import math
    if not isinstance(lots,list): raise GsavError(f'{cid}: not a list')
    for l in lots:
        if not isinstance(l.get('modelId'),str): raise GsavError(f'{cid}: bad modelId')
        for k in ('units','year','quality'):
            x=l.get(k)
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x): raise GsavError(f'{cid}: bad {k}')
        if l['units']<0: raise GsavError(f'{cid}: negative units')
def set_total(lots,new):
    """increase: add to best lot (highest quality, newest). decrease: remove from lowest quality first."""
    cur=sum(l['units'] for l in lots); delta=new-cur
    if not lots: raise GsavError('no equipment of this type to copy')
    if delta>0:
        b=max(range(len(lots)),key=lambda i:(lots[i]['quality'],lots[i]['year']))
        u=lots[b]['units']+delta; lots[b]['units']=int(u) if float(u).is_integer() else u
    elif delta<0:
        need=-delta
        for l in sorted(lots,key=lambda l:(l['quality'],l['year'],l['modelId'])):
            take=min(l['units'],need); u=l['units']-take; l['units']=int(u) if float(u).is_integer() else u; need-=take
            if need<=1e-9: break
        keep=[l for l in lots if l['units']>1e-9]; lots[:]=keep
    return lots
def check_equip(cid,v):
    try: v=float(v)
    except Exception: raise GsavError(f'{EQUIP.get(cid,{}).get("name",cid)}: please type a number')
    if v!=v or v<0 or v>EQUIP_LIMIT or not v.is_integer(): raise GsavError(f'{EQUIP.get(cid,{}).get("name",cid)}: whole number from 0 to {EQUIP_LIMIT}')
    return int(v)
# ---- wars ----
def player_wars(save):
    out=[]
    for pair in save.wars_raw():
        wid,w=pair[0],pair[1]; parts=w.get('participants') or {}
        me=parts.get(save.pk,{}).get('side') or ('A' if str(w.get('a'))==save.pk or w.get('sideAKey')==save.pk else 'B' if str(w.get('b'))==save.pk or w.get('sideBKey')==save.pk else None)
        if not me: continue
        co=w.get('coalitions') or {}
        side=lambda S:[str(k) for k in (co.get(S) or {}).get('members') or []]
        out.append({'id':wid,'status':w.get('status'),'aName':w.get('aName'),'bName':w.get('bName'),'my_side':me,
                    'enemy':w.get('bName') if me=='A' else w.get('aName'),'A':side('A'),'B':side('B'),'participants':list(parts)})
    return out
def new_participant(key,side,day): return {"countryKey":key,"side":side,"role":"support","joinedDay":day,"formationIds":[],"contributions":{}}
# ---- legislature ----
def chambers_summary(c,pid):
    """[(chamberId, seats, rulingSeats, composition)] for the country's chambers."""
    out=[]
    for ch in c['pol'].get('chambers') or []:
        comp=ch.get('composition') or {}; tot=sum(v for v in comp.values() if isinstance(v,(int,float))) or ch.get('seats') or 0
        out.append((str(ch.get('id')),int(tot),int(comp.get(pid,0) or 0),dict(comp)))
    return out
def fill_chambers(c,pid):
    """Give every seat of every chamber to party pid. Keeps total = chamber.seats (so the game's load
    rescale bMQ/nz does nothing) and keeps the other parties as 0-seat keys. Returns list of log lines."""
    pol=c['pol']; ids={p['id'] for p in pol['parties']}
    if pid not in ids: raise GsavError(f'party {pid} not in this country')
    log=[]
    for ch in pol.get('chambers') or []:
        comp=ch.get('composition')
        if not isinstance(comp,dict) or not comp: raise GsavError(f'chamber {ch.get("id")}: no composition')
        if not all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in comp.values()): raise GsavError(f'chamber {ch.get("id")}: odd seat numbers')
        seats=ch.get('seats'); tot=sum(comp.values())
        if not (isinstance(seats,int) and seats>=1): seats=tot
        if tot!=seats: raise GsavError(f'chamber {ch.get("id")}: seats {seats} but parties hold {tot} (not touching it)')
        old=comp.get(pid,0); ch['composition']={k:(seats if k==pid else 0) for k in comp}
        if pid not in comp: ch['composition'][pid]=seats
        log.append(f'Chamber {ch.get("id")}: {pid} {old} -> {seats} of {seats} seats')
    gov=(pol.get('institutionState') or {}).get('government')
    if isinstance(gov,dict) and gov.get('status')=='minority' and gov.get('leadPartyId')==pid:
        gov['status']='installed'; log.append('Government status: minority -> installed')
    return log
LEG_KEY='_legislature'
SUP_KEY='_support'   # value: ruling-party support in percent (1..99)
def support_summary(c):
    """[(partyId, support 0..1)] in save order."""
    return [(p['id'],float(p.get('support') or 0)) for p in c['pol']['parties']]
def set_support(c,pid,pct):
    """Set party pid's support to pct% and scale every other party down/up proportionally so the total
    stays exactly 1 (the game renormalises to 1 every week: rZB/pVA). Also scales each party's 'valence'
    (its pull in the vote model xPA) by new/old support, so the game's own weekly drift target moves
    with the edit instead of pulling support straight back. On load the game re-fits valence to the
    stored support anyway (tSQ -> yJ), so the edited support becomes the new baseline."""
    try: pct=float(pct)
    except Exception: raise GsavError('support must be a number')
    if not (1<=pct<=99): raise GsavError('support must be between 1 and 99 %')
    ps=c['pol']['parties']; me=next((p for p in ps if p['id']==pid),None)
    if me is None: raise GsavError(f'party {pid} not in this country')
    new=pct/100; others=[p for p in ps if p is not me]
    if not others: raise GsavError('only one party in this country')
    old=float(me.get('support') or 0); rest=sum(float(p.get('support') or 0) for p in others)
    want={id(me):new}
    for p in others: want[id(p)]=(float(p.get('support') or 0)/rest*(1-new)) if rest>0 else (1-new)/len(others)
    tot=sum(want.values())
    for p in ps:
        o=float(p.get('support') or 0); n=want[id(p)]/tot
        if isinstance(p.get('valence'),(int,float)) and o>1e-9 and n>0: p['valence']=p['valence']*n/o
        p['support']=n
    return [f'Party support: {pid} {old*100:.1f}% -> {new*100:.1f}% (others scaled to share {(1-new)*100:.1f}%)']
# ---- save ----
def save_as_new(save,values=None,equipment=None,war_adds=None,clear_flag=True,reset_toggles=False,folder=None,prefix='Mira_edit_'):
    """values {field_id: new}; equipment {classId: new_total}; war_adds [(war_id,key,side)]. Only changed values are written."""
    values=dict(values or {}); equipment=equipment or {}; war_adds=war_adds or []; SaveCtx.cur=save
    fill_leg=bool(values.pop(LEG_KEY,False))
    sup=values.pop(SUP_KEY,None)
    log=[f'from: {os.path.basename(save.path)}   country: {save.country_label} ({save.pk})   day {save.day}']
    texts={}
    # mirror check (same as clear_cheat_flag)
    meta_raw=save.d[save.mo:save.mo+save.ml]; mir=[k.decode() for k in MIRROR_KEYS if k in meta_raw]
    for n in save.names:
        if n!='core':
            b=save.sec(n).encode('utf-8') if n in save.text else dec(*(lambda s:(s[1],save.d[s[2]:s[2]+s[3]],s[4]))(save.secs[save.names.index(n)]))
            mir+= [f'{n}:{k.decode()}' for k in MIRROR_KEYS if k in b]
    if mir: raise GsavError(f'STOP: cheat data found in unexpected places: {mir}')
    # country edits
    c=copy.deepcopy(save.country); C=save.sec('countries'); s,e=save.cs,save.ce; changed_c=False
    for fid,v in values.items():
        f=field(fid); v=check_value(f,v)
        if f.put=='finance' or v==f.get(save): continue
        before=copy.deepcopy(c); f.put(c,v)
        # substitute each leaf that changed
        for k in ('approval','_apprAnchor','stab','_stabAnchor'):
            if before[k]!=c[k]:
                exp=copy.deepcopy(before); exp[k]=c[k]; C,e=sub_value(C,s,e,k,before[k],c[k],exp); before=exp
        if fid=='party_funds':
            po=save.party(before)['organization']; C,e=sub_value(C,s,e,'treasuryM',po['treasuryM'],v,c)
        log.append(f'{f.label}: {f.get(save)} -> {v}'); changed_c=True
    if sup is not None:
        before=copy.deepcopy(c); ll=set_support(c,save.party_id,sup)
        if abs(dict(support_summary(before))[save.party_id]-sup/100)<5e-4: log.append('Party support: already at that level, nothing to change')
        else:
            exp=copy.deepcopy(before); exp['pol']['parties']=c['pol']['parties']
            C,e=sub_value(C,s,e,'parties',before['pol']['parties'],c['pol']['parties'],exp); log+=ll; changed_c=True
        sup_target=dict(support_summary(c))[save.party_id]
    if fill_leg:
        before=copy.deepcopy(c); ll=fill_chambers(c,save.party_id); leg_changed=before!=c
        if before['pol']['chambers']!=c['pol']['chambers']:
            exp=copy.deepcopy(before); exp['pol']['chambers']=c['pol']['chambers']
            C,e=sub_value(C,s,e,'chambers',before['pol']['chambers'],c['pol']['chambers'],exp); before=exp
        g0=before['pol']['institutionState']['government']; g1=c['pol']['institutionState']['government']
        if g0!=g1: C,e=sub_value(C,s,e,'government',g0,g1,c)
        if leg_changed: log+=ll; changed_c=True
        else: log.append('Parliament: already full, nothing to change')
    for cid,v in equipment.items():
        v=check_equip(cid,v); lots=c['forces']['equipment'].get(cid)
        if not isinstance(lots,list): raise GsavError(f'{EQUIP[cid]["name"]}: missing in this save')
        old=sum(l['units'] for l in lots)
        if round(old)==v: continue
        before=copy.deepcopy(c['forces']['equipment']); new_stock=''
        if not lots:
            if not can_add_new(c,cid): raise GsavError(f'{EQUIP[cid]["name"]}: this country has no navy (needs a coast)')
            nl=new_model(c,save.pk,cid); nl['units']=v; lots.append(nl); new_stock=f'  (new stock: {nl["modelId"]}, {nl["year"]}, quality {nl["quality"]})'
        else: set_total(lots,v)
        check_lots(lots,cid)
        C,e=sub_value(C,s,e,'equipment',before,c['forces']['equipment'],c)
        log.append(f'{EQUIP[cid]["name"]}: {round(old):,} -> {v:,}{new_stock}'); changed_c=True
    if changed_c:
        if json.loads(C[s:e])!=c: raise GsavError('country check failed')
        if C[:save.cs]!=save.sec('countries')[:save.cs] or C[e:]!=save.sec('countries')[save.ce:]: raise GsavError('other countries changed')
        texts['countries']=C
    # cash
    if 'cash' in values:
        v=check_value(field('cash'),values['cash']); old=save.cash()
        if v!=old:
            texts['finance'],o=apply_row_fast(save.sec('finance'),f'treasury-cash:{save.pk}',v); log.append(f'Cash: {o} -> {v}  (${v/1000:g} trillion)')
    # core: wars + cheat flag
    core=save.sec('core'); core0=core
    if war_adds:
        i=core.find('"aiWars":'); aw,ae=_D.raw_decode(core,i+9); exp=copy.deepcopy(aw); ws=i+9
        for wid,key,side in war_adds:
            key=str(key); side=side.upper()
            if side not in('A','B'): raise GsavError('side must be A or B')
            war=next((p[1] for p in exp['wars'] if p[0]==wid),None)
            if war is None: raise GsavError(f'war {wid} not found')
            if key==save.pk: raise GsavError('that is your own country')
            if not save.has_country(key): raise GsavError(f'unknown country {key}')
            co=war['coalitions']; already=key in (war.get('participants') or {}) or any(key in [str(x) for x in (co.get(S) or {}).get('members',[])] for S in('A','B')) or key in (str(war.get('a')),str(war.get('b')))
            if already: raise GsavError(f'{country_name(key)} is already in this war')
            co[side]['members'].append(key); war['participants'][key]=new_participant(key,side,save.day)
            if isinstance(war.get('_participantRevision'),int): war['_participantRevision']+=1
            log.append(f'War {wid}: added {country_name(key)} ({key}) to side {side}, joined day {save.day}  [EXPERIMENTAL]')
        core=core[:ws]+sj(exp)+core[ae:]
        if json.loads(core[ws:ws+len(sj(exp))])!=exp: raise GsavError('war check failed')
    if clear_flag or reset_toggles:
        b=core.encode('utf-8')
        if clear_flag: b,old=replace_obj(b,b'campaignIntegrity',CLEAN_CI); log.append(f'Cheat flag cleared (was {sj(old)})')
        if reset_toggles: b,old=replace_obj(b,b'cheats',CLEAN_CHEATS); log.append('Cheat switches reset')
        core=b.decode('utf-8')
    if core!=core0: texts['core']=core
    if not texts: raise GsavError('Nothing to change')
    raws={save.names.index(n):t.encode('utf-8') for n,t in texts.items()}
    origs={save.names.index(n):save.sec(n).encode('utf-8') for n in texts}
    nd,rl=repack(save.d,raws,origs); log+=rl
    # verify
    v=verify(nd)
    if not all(v.values()): raise GsavError(f'output check failed {v}')
    pa,pb=parse(save.d)[3],parse(nd)[3]
    for i,(x,y) in enumerate(zip(pa,pb)):
        same=save.d[x[2]:x[2]+x[3]]==nd[y[2]:y[2]+y[3]]
        if same==(i in raws): raise GsavError(f'{save.names[i]}: unexpected identical={same}')
    if save.d[:0x10]!=nd[:0x10] or save.d[save.mo:save.mo+save.ml]!=nd[save.mo:save.mo+save.ml]: raise GsavError('header changed')
    folder=folder or os.path.dirname(os.path.abspath(save.path)); out=next_free(folder,prefix)
    with open(out,'xb') as fh: fh.write(nd)
    # read back from disk
    r=Save(out); bad=[]
    for fid,val in values.items():
        f=field(fid); want=check_value(f,val)
        if f.get(r)!=want: bad.append(f'{f.label}={f.get(r)} (wanted {want})')
    for cid,val in equipment.items():
        got=round(sum(l['units'] for l in r.country['forces']['equipment'][cid]))
        if got!=int(val): bad.append(f'{cid}={got}')
    for wid,key,side in war_adds:
        w=next(p[1] for p in r.wars_raw() if p[0]==wid); pp=w['participants'].get(str(key))
        if not pp or pp['side']!=side.upper() or pp['joinedDay']!=r.day or str(key) not in [str(x) for x in w['coalitions'][side.upper()]['members']]: bad.append(f'war {wid} {key}')
    if sup is not None:
        ss=dict(support_summary(r.country))
        if abs(ss[r.party_id]-sup_target)>1e-12 or abs(sum(ss.values())-1)>1e-9: bad.append('party support')
    if fill_leg:
        for cid,tot,mine,comp in chambers_summary(r.country,r.party_id):
            if mine!=tot or sum(comp.values())!=tot: bad.append(f'chamber {cid}')
    core_r=r.sec('core')
    if clear_flag:
        i=core_r.find('"campaignIntegrity":'); ci=_D.raw_decode(core_r,i+20)[0]; j=core_r.find('"cheats":'); ch=_D.raw_decode(core_r,j+9)[0]
        if ci!=CLEAN_CI or not nO(ch,ci): bad.append('cheat flag')
    if reset_toggles:
        j=core_r.find('"cheats":')
        if _D.raw_decode(core_r,j+9)[0]!=CLEAN_CHEATS: bad.append('cheat switches')
    if bad:
        raise GsavError(f'Saved {os.path.basename(out)} but read-back failed: {bad}. Do NOT use that file.')
    log.append(f'read back OK; all file checks OK; unchanged parts byte-identical')
    log.append('now: '+', '.join(f'{field(f).label}={field(f).get(r):g}' for f in values))
    return out,log
def apply_row_fast(F,key,value):
    m=list(re.finditer(r'(\["'+re.escape(key)+r'",(?:"[^"]*",){6})('+NUM.decode()+')',F))
    if len(m)!=1: raise GsavError(f'{key}: {len(m)} matches')
    row,end=_D.raw_decode(F,m[0].start()); old=row[7]; exp=list(row); exp[7]=value
    F2=F[:m[0].start(2)]+sj(value)+F[m[0].end(2):]
    if _D.raw_decode(F2,m[0].start())[0]!=exp: raise GsavError('cash check failed')
    return F2,old

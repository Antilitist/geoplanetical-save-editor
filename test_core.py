"""Self-test for the Geoplanetical Save Editor.

Usage:
    python test_core.py path\to\some_save.gsav
    (or set the environment variable GSAV_TEST_SAVE to a save path)

Works on a COPY of the save in a temporary folder. The save you point at is
never changed. If no save is given, the tests are skipped (exit code 0).
"""
import os, sys, shutil, hashlib, tempfile, traceback, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gsav_core as G

args = [a for a in sys.argv[1:] if not a.startswith('--')]
SRC = args[0] if args else os.environ.get('GSAV_TEST_SAVE', '')
if not SRC or not os.path.isfile(SRC):
    print('SKIPPED: no test save given. Run:  python test_core.py path\\to\\save.gsav  (or set GSAV_TEST_SAVE)')
    sys.exit(0)

RES = []
def test(name):
    def deco(fn):
        t0 = time.time()
        try: fn(); RES.append(True); print(f'PASS  {name}  ({time.time()-t0:.1f}s)')
        except Exception as e: RES.append(False); print(f'FAIL  {name}: {e!r}'); traceback.print_exc()
        return fn
    return deco

sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
src_hash = sha(SRC)
TMP = tempfile.mkdtemp(prefix='gsav_test_')
COPY = os.path.join(TMP, 'test_copy.gsav'); shutil.copy2(SRC, COPY)
S = {}

@test('load copy and verify hashes')
def _():
    s = S['s'] = G.Save(COPY)
    assert all(G.verify(open(COPY, 'rb').read()).values())
    print(f'   {s.country_label} ({s.pk}) day {s.day} cash {s.cash():.1f}')

@test('bad input rejected, nothing written')
def _():
    for f, v in (('approval', 101), ('approval', -1), ('party_funds', 10001), ('stability', 'abc'), ('cash', -5)):
        try: G.check_value(G.field(f), v); raise AssertionError(f'{f}={v} accepted')
        except G.GsavError: pass
    before = set(os.listdir(TMP))
    try: G.save_as_new(S['s'], {'approval': 150}); raise AssertionError('saved bad value')
    except G.GsavError: pass
    assert set(os.listdir(TMP)) == before

@test('save as new -> Mira_edit_001, then Mira_edit_002 (never overwrites)')
def _():
    out, _ = G.save_as_new(S['s'], {'approval': 90, 'stability': 90})
    assert os.path.basename(out) == 'Mira_edit_001.gsav'
    r = G.Save(out); assert r.country['approval'] == 90 and r.country['stab'] == 90
    assert all(G.verify(open(out, 'rb').read()).values())
    out2, _ = G.save_as_new(S['s'], {'approval': 55})
    assert os.path.basename(out2) == 'Mira_edit_002.gsav' and G.Save(out2).country['approval'] == 55

@test('arsenal: add 10 to first editable type, read back')
def _():
    ar = [(c, t) for c, n, t, ok, wm in G.arsenal(S['s']) if ok]; assert ar
    cid, t = ar[0]; v = round(t) + 10
    out, _ = G.save_as_new(S['s'], equipment={cid: v}, clear_flag=False)
    assert round(dict((c, x) for c, n, x, o, w in G.arsenal(G.Save(out)))[cid]) == v

@test('parliament fill + party support 70%')
def _():
    s = S['s']; pid = s.party_id
    out, _ = G.save_as_new(s, {G.SUP_KEY: 70, G.LEG_KEY: True}, clear_flag=False)
    r = G.Save(out); assert all(G.verify(open(out, 'rb').read()).values())
    assert abs(dict(G.support_summary(r.country))[pid] - 0.70) < 1e-12
    assert all(m == t for cid, t, m, comp in G.chambers_summary(r.country, pid))

@test('original save unchanged')
def _():
    assert sha(SRC) == src_hash

shutil.rmtree(TMP, ignore_errors=True)
print(f'\nSUMMARY: {sum(RES)}/{len(RES)} PASS')
sys.exit(0 if all(RES) else 1)
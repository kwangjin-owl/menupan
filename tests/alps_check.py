"""알프스 메뉴판 검사 — 인수인계 8장 목록을 새 파일과 기준 파일에 똑같이 돌리고 판정한다.
사용:  python3 alps_check.py 새.html 기준.html [검사이름 ...] [-j 동시실행수]
       검사이름을 안 주면 전부. 결과는 ./_check/ 에 쌓이고 마지막에 표로 나온다.
필요:  pip install playwright pillow --break-system-packages && playwright install chromium ;  poppler-utils(pdftotext · pdftoppm) ; node(있으면 문법 검사)
주의:  -j 를 크게 주면 전환 도중에 찍혀 헛차이가 난다(235번). 차이가 나면 그 검사만 -j 1 로 다시 돌릴 것"""
from playwright.sync_api import sync_playwright
import json, sys, os, re, subprocess, io, time
from PIL import Image, ImageChops

def pixels(img):
    """Pillow 14 에서 getdata() 가 없어진다 — 있는 쪽을 쓴다"""
    f = getattr(img, 'get_flattened_data', None)
    return f() if f else img.getdata()

D = os.path.join(os.getcwd(), '_check') + '/'
os.makedirs(D + 'res', exist_ok=True)
NOREN = ["full","flat","wave","scallop","ridge","saw","arch","ribbon","twin","fade","frame","line","plain"]
FONTS = ['gungseo','myeongjo','gothic','round','hand','batang','serif','plex']   # 272번. 파일의 FONTS 를 못 읽을 때만 쓴다 — 도는 목록은 파일에서 읽는다(font_list)
def font_list(c):
    try: return c.js("()=>Object.keys(FONTS)")   # 글꼴을 늘려도 검사 파일을 안 고쳐도 되게(272번 — 고정 목록이라 새 글꼴 셋을 안 돌렸다)
    except Exception: return FONTS
SEALS = ['none','tri','mtn','word','star','rtri','rword','rmtn','sstar','ring']
SHAPES = ['bordeaux','burgundy','champagne','stout','flute','port','dessert','madeira','provence']
KINDS = ['red','white','sparkling','rose','orange']
MM = 25.4 / 72

def url(f): return 'file://' + D + f

class Ctx:
    def __init__(self, b, f, W=1400, H=900, dl=False):
        self.c = b.new_context(viewport={'width': W, 'height': H}, accept_downloads=dl)
        self.pg = self.c.new_page(); self.errs = []
        self.pg.on('pageerror', lambda e: self.errs.append(str(e)))
        self.pg.goto(url(f)); self.pg.wait_for_timeout(250)
    def js(self, s, a=None): return self.pg.evaluate(s, a) if a is not None else self.pg.evaluate(s)
    def close(self): self.c.close()

APPLY = "()=>{syncControls(); applyLook(); render(); applyScale();}"
FIT = "()=>{MENU.sheets.forEach((_,i)=>P(i).autofit=true); syncControls(); applyLook(); render(); fitNow(); applyScale();}"
OVER = "()=>[...MENU.sheets.keys()].map(i=>overA4(i))"

# 1쪽 메뉴 · 2쪽 와인 요소의 종이 기준 좌표
POS = """(sel)=>[...document.querySelectorAll('.sheet')].map(sh=>{const o=sh.getBoundingClientRect();
  return [...sh.querySelectorAll(sel)].filter(e=>e.offsetHeight>0).map(e=>{const r=e.getBoundingClientRect();
   return [+(r.left-o.left).toFixed(1), +(r.top-o.top).toFixed(1)]})})"""
INK_SEL = '.row .name > span:first-child, .row .price, h2 .hv, .note .nv, .wname, .wf, .wprice'


CLICKPT = """(e)=>{const r=e.getBoundingClientRect(); const fs=parseFloat(getComputedStyle(e).fontSize);
  if (r.width < 1 && e.classList.contains('vol')) return [r.left + 1.43*fs, r.top + r.height/2 + 0.1*fs];   // 238번. 보이는 것은 ::before 조각
  return [r.left + r.width/2, r.top + r.height/2]}"""

# ───────────────────────── 2. 그 밖의 설정
def t02(b, f):
    out = {}
    c = Ctx(b, f)
    for o in ('portrait', 'landscape'):
        fs = []
        for fo in font_list(c):
            for se in SEALS:
                c.pg.goto(url(f))
                fs.append([fo, se, c.js("([o,fo,se])=>{SETTINGS.orient=o; SETTINGS.font=fo; MENU.sheets.forEach((_,i)=>{P(i).seal=se; P(i).autofit=true;}); syncControls(); applyLook(); render(); fitNow(); applyScale(); return [...MENU.sheets.keys()].map(i=>overA4(i))}", [o, fo, se])])
        out['font_seal_' + o] = [x for x in fs if any(x[2])]
        out['font_seal_n_' + o] = len(fs)
        arts = []
        for a in ['none','horse','zebra','ibex','mountain','fir','cabin','night','bridge','highball','beer','soju','sake','wine','pasta','beerpasta','edelweiss','vine']:
            c.pg.goto(url(f))
            r = c.js("""([o,a,sel])=>{SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>P(i).art=a); syncControls(); applyLook(); render(); fitNow(); applyScale();
              let hid=0, n=0; document.querySelectorAll(sel).forEach(e=>{ if(!e.offsetHeight) return; const r=e.getBoundingClientRect(); n++;
                if (r.top<0||r.bottom>innerHeight){ e.scrollIntoView({block:'center'}); }
                const q=e.getBoundingClientRect(); const hit=document.elementFromPoint(q.left+Math.min(4,q.width/2), q.top+q.height/2);
                if (hit && hit.closest('.art')) hid++; });
              return [[...MENU.sheets.keys()].map(i=>overA4(i)), hid, n]}""", [o, a, INK_SEL])
            arts.append([a] + r)
        out['art_' + o] = [x for x in arts if any(x[1]) or x[2]]
        out['art_checked_' + o] = sum(x[3] for x in arts)
        misc = []
        for key, vals in [('shape', SHAPES), ('mark', ['★','●','◆','✿']), ('pageno', ['of','num','none']),
                          ('bilingual', [False, True]), ('origin', [False, True]), ('bold', [False, True])]:
            for v in vals:
                c.pg.goto(url(f))
                r = c.js("""([o,k,v,KINDS])=>{SETTINGS.orient=o;
                  if(k==='shape'){ SETTINGS.bottles={}; KINDS.forEach(x=>SETTINGS.bottles[x]={shape:v}); }
                  else if(k==='origin'){ MENU.sheets.forEach((_,i)=>{P(i).showOrigin=v; F(i).origin=v?'돼지고기: 국내산, 쌀: 국내산, 배추김치(배추 중국산, 고춧가루 국내산)':'';}); }
                  else SETTINGS[k]=v;
                  syncControls(); applyLook(); render(); fitNow(); applyScale(); return [...MENU.sheets.keys()].map(i=>overA4(i))}""", [o, key, v, KINDS])
                misc.append([key, v, r])
        out['misc_' + o] = [x for x in misc if any(x[2])]
        out['misc_n_' + o] = len(misc)
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 3. 상단 모양 눈으로
def t03(b, f):
    shots = []
    for o in ('portrait', 'landscape'):
        c = Ctx(b, f, 1500, 1000)
        for n in NOREN:
            c.js("([o,n])=>{SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>P(i).noren=n); syncControls(); applyLook(); render(); applyScale();}", [o, n])
            c.pg.wait_for_timeout(80)
            r = c.js("()=>{const s=document.querySelector('.sheet');s.scrollIntoView();const q=s.getBoundingClientRect();return [q.left+scrollX,q.top+scrollY,q.width]}")
            img = Image.open(io.BytesIO(c.pg.screenshot(full_page=True, clip={'x': r[0], 'y': r[1], 'width': r[2], 'height': 240}))).convert('RGB')
            shots.append((o, n, img))
        c.close()
    TW = 420
    thumbs = [(o, n, i.resize((TW, int(i.height * TW / i.width)))) for o, n, i in shots]
    TH = max(t.height for _, _, t in thumbs)
    sheet = Image.new('RGB', (TW * 2 + 12, 13 * (TH + 6)), 'white')
    for o, n, t in thumbs:
        sheet.paste(t, ((0 if o == 'portrait' else TW + 12), NOREN.index(n) * (TH + 6)))
    sheet.save(D + f'res/noren_{f}.png')
    import hashlib
    return {'hash': [hashlib.md5(i.tobytes()).hexdigest() for _, _, i in shots]}

# ───────────────────────── 4. 마우스로 실제로 눌러 보기 (도달성)
REACH = """(tg)=>{ const root=document.querySelector('[data-tgt="'+tg+'"]');
  const vis=e=>{const r=e.getBoundingClientRect(), s=getComputedStyle(e); return r.width>0&&r.height>0&&s.visibility!=='hidden'&&+s.opacity>0.05&&s.display!=='none'&&r.top>=0&&r.bottom<=innerHeight-120&&r.left>=0&&r.right<=innerWidth};
  const own=[...root.querySelectorAll('button, select')].filter(e=>{const t=e.closest('[data-tgt]'); return t===root || (root.matches('section') && !t.matches('section'))});
  return own.filter(vis).map(e=>{const r=e.getBoundingClientRect(); return {x:r.left+r.width/2,y:r.top+r.height/2,dis:e.disabled||getComputedStyle(e).pointerEvents==='none',t:(e.title||e.textContent).trim().slice(0,14), dy:r.top+scrollY}});
}"""
def t04(b, f):
    c = Ctx(b, f, 1500, 1000); pg = c.pg
    pg.click('#b-edit'); pg.wait_for_timeout(250)
    c.js("()=>{document.querySelector('#panel').hidden=true; placePanel();}")
    targets = c.js("""()=>{const L=[]; document.querySelectorAll('.sheet').forEach((sh,si)=>{
       sh.querySelectorAll('.row, section > .sec-head, section, .note, .hours > div, .hours, .zone, .pagebar').forEach((e,k)=>{ e.dataset.tgt=si+'-'+L.length; L.push(si+'-'+(L.length)); }); }); return L}""")
    seen = {}; tot = 0; ok = 0; dis = 0; bad = []
    for t in targets:
        el = pg.locator(f'[data-tgt="{t}"]')
        el.evaluate("e=>{const r=e.getBoundingClientRect(); scrollTo(0, r.top+scrollY-90)}")
        bb = el.bounding_box()
        if not bb: continue
        hx, hy = bb['x'] + min(30, bb['width'] / 2), bb['y'] + min(10, bb['height'] / 2)
        pg.mouse.move(hx, hy); pg.wait_for_timeout(40)
        for btn in c.js(REACH, t):
            key = f"{t}|{btn['t']}|{round(btn['x'])}|{round(btn['y'])}"
            sk = f"{btn['t']}|{round(btn['x'])}|{round(btn['dy'])}"
            if sk in seen: continue
            if btn['dis']: seen[sk] = 'dis'; dis += 1; continue
            pg.mouse.move(hx, hy); pg.mouse.move(btn['x'], btn['y'], steps=12); pg.wait_for_timeout(15)
            hit = c.js("([x,y,t])=>{const e=document.elementFromPoint(x,y); const b=e&&e.closest('button,select'); return !!b && ((b.title||b.textContent).trim().slice(0,14)===t)}", [btn['x'], btn['y'], btn['t']])
            seen[sk] = hit; tot += 1; ok += hit
            if not hit: bad.append(key)
    # 빈 칸에 글자가 실제로 들어가는지 (226번)
    fill = {}
    c.js("()=>{SETTINGS.bilingual=true; const it=MENU.sheets[0][0][0].items[1]; it.desc=''; render();}"); pg.wait_for_timeout(150)
    for name, sel, path in [('vol', '.sheet .row .vol >> nth=1', None), ('en', '.sheet .row .en', None), ('ml', '.sheet .ml', None),
                            ('desc', '.sheet .desc', None), ('wf', '.sheet .row.wine .worigin [contenteditable], .sheet .row.wine .worigin[contenteditable]', None)]:
        loc = pg.locator(sel).first
        if loc.count() == 0: fill[name] = 'none'; continue
        loc.evaluate("e=>e.scrollIntoView({block:'center'})")
        bb = loc.bounding_box()
        row = loc.evaluate("e=>{const r=e.closest('.row,section'); const b=r.getBoundingClientRect(); return [b.left+20,b.top+b.height/2]}")
        pg.mouse.move(row[0], row[1]); cp = loc.evaluate(CLICKPT); pg.mouse.move(cp[0], cp[1], steps=8)
        pg.mouse.click(cp[0], cp[1]); pg.keyboard.type('Q')
        fill[name] = loc.evaluate("e=>{const p=(e.dataset.path?e:e.querySelector('[data-path]')||e).dataset.path; return [p, p && String(p.split('.').reduce((o,k)=>o&&o[k], eval('MENU'))).includes('Q')]}")
    # 누르면 값이 바뀌는지 (대표 동작)
    act = {}
    def clickTitle(scope_js, title):
        r = c.js("""([s,t])=>{const e=eval(s); e.scrollIntoView({block:'center'}); const b=e.getBoundingClientRect(); return [b.left+15,b.top+b.height/2]}""", [scope_js, title])
        pg.mouse.move(r[0], r[1]); pg.wait_for_timeout(40)
        r2 = c.js("""([s,t])=>{const e=eval(s); const x=[...e.querySelectorAll('button,select')].find(q=>q.title===t||q.textContent.trim()===t); if(!x) return null; const b=x.getBoundingClientRect(); return [b.left+b.width/2,b.top+b.height/2]}""", [scope_js, title])
        if not r2: return 'nobtn'
        pg.mouse.move(r2[0], r2[1], steps=10); pg.mouse.click(r2[0], r2[1]); pg.wait_for_timeout(120); return 'ok'
    row0 = "document.querySelectorAll('.sheet')[0].querySelectorAll('.row')[2]"
    b0 = c.js("()=>JSON.stringify(MENU.sheets[0][0][0].items[2])")
    clickTitle(row0, '추천 표시'); act['star'] = c.js("()=>JSON.stringify(MENU.sheets[0][0][0].items[2])") != b0
    b0 = c.js("()=>MENU.sheets[0][0][0].items[2].name")
    clickTitle("document.querySelectorAll('.sheet')[0].querySelectorAll('.row')[2]", '위로 옮기기'); act['up'] = c.js("()=>MENU.sheets[0][0][0].items[1].name") == b0
    n0 = c.js("()=>MENU.sheets[0][0][0].items.length")
    clickTitle("document.querySelectorAll('.sheet')[0].querySelector('section')", '＋ 메뉴 추가'); act['addrow'] = c.js("()=>MENU.sheets[0][0][0].items.length") == n0 + 1
    h0 = c.js("()=>MENU.hours.length")
    hb = pg.locator('.sheet .hours'); hb.evaluate("e=>scrollTo(0,e.getBoundingClientRect().top+scrollY-120)"); q = hb.bounding_box(); pg.mouse.move(q['x']+10, q['y']+5); pg.wait_for_timeout(60)
    q2 = pg.locator('.sheet .hours .addbtn').bounding_box(); pg.mouse.move(q2['x']+q2['width']/2, q2['y']+q2['height']/2, steps=8); pg.mouse.click(q2['x']+q2['width']/2, q2['y']+q2['height']/2); pg.wait_for_timeout(120)
    act['hours'] = c.js("()=>MENU.hours.length") == h0 + 1
    s0 = c.js("()=>MENU.sheets.length")
    clickTitle("document.querySelector('.sheet .pagebar')", '＋ 메뉴 장 추가'); act['page'] = c.js("()=>MENU.sheets.length") == s0 + 1
    out = {'targets': len(targets), 'reach': [ok, tot], 'disabled': dis, 'bad': bad[:20], 'fill': fill, 'act': act, 'err': c.errs}
    out['unreached_kinds'] = sorted(set(k.split('|')[1] for k in bad))
    c.close(); return out

# ───────────────────────── 5. 편집 대 미리보기 (위치만) + 22. 넓은 화면 직렬화
def t05(b, f):
    out = {}
    for W in (1600, 1200, 1024, 901, 900, 640, 430):
        for o in ('portrait', 'landscape'):
            for bi in (False, True):
                c = Ctx(b, f, W, 900)
                c.js("([o,bi])=>{SETTINGS.orient=o; SETTINGS.bilingual=bi; const s=MENU.sheets[0][0][0]; s.items[0].out=true; s.items[0].pick=true; s.items[1].name='아주 아주 긴 메뉴 이름을 넣어 두 줄로 접히는지 보는 줄입니다'; syncControls(); applyLook(); render(); applyScale();}", [o, bi])
                c.pg.wait_for_timeout(100)
                fin = c.js(POS, '.row, h2, .note, .price, .dots, .wprice, .wname, .seal')
                dots_mask = c.js("()=>[...document.querySelectorAll('.sheet')].map(sh=>[...sh.querySelectorAll('.row, h2, .note, .price, .dots, .wprice, .wname, .seal')].filter(e=>e.offsetHeight>0).map(e=>!e.classList.contains('dots')))")
                ser = c.js("()=>({scale:MENU.sheets.map((_,i)=>P(i).scale), why:[...MENU.sheets.keys()].map(i=>overWhy(i)), fit:[...MENU.sheets.keys()].map(i=>fitPct(i)), vars:[...document.querySelectorAll('.sheet')].map(s=>[getComputedStyle(s).getPropertyValue('--gap'),getComputedStyle(s).getPropertyValue('--wgap'),getComputedStyle(s).getPropertyValue('--price-w')])})")
                c.js("()=>document.querySelector('#b-edit').click()"); c.pg.wait_for_timeout(250)
                ed = c.js(POS, '.row, h2, .note, .price, .wprice, .wname, .seal')
                c.js("()=>document.querySelector('#b-preview').click()"); c.pg.wait_for_timeout(300)
                pv = c.js(POS, '.row, h2, .note, .price, .dots, .wprice, .wname, .seal')
                def md(a, bb):
                    if [len(x) for x in a] != [len(x) for x in bb]: return 'count'
                    return max([0] + [max(abs(p[0] - q[0]), abs(p[1] - q[1])) for sa, sb in zip(a, bb) for p, q in zip(sa, sb)])
                fin_nd = [[p for p, e in zip(sa, sl) if e] for sa, sl in zip(fin, dots_mask)]
                out[f'{W}-{o}-{bi}'] = {'edit': md(fin_nd, ed), 'prev': md(fin, pv), 'ser': ser, 'fin': fin, 'err': c.errs}
                c.close()
    return out

# ───────────────────────── 6. 마우스를 올렸을 때 들썩임
def t06(b, f):
    c = Ctx(b, f, 1500, 1000); pg = c.pg
    pg.click('#b-edit'); pg.wait_for_timeout(250)
    DOC = "()=>[...document.querySelectorAll('.row, h2, .note, .foot, .hours')].map(r=>+(r.getBoundingClientRect().top+scrollY).toFixed(1))"
    base = c.js(DOC); worst = 0; n = 0
    for sel in ['.sheet .row', '.sheet section', '.sheet .note', '.sheet .hours > div', '.sheet .row.wine']:
        for k in range(pg.locator(sel).count()):
            loc = pg.locator(sel).nth(k); loc.evaluate("e=>e.scrollIntoView({block:'center'})")
            bb = loc.bounding_box()
            if not bb: continue
            pg.mouse.move(bb['x'] + 20, bb['y'] + min(8, bb['height'] / 2)); pg.wait_for_timeout(30)
            now = c.js(DOC); n += 1
            worst = max(worst, max(abs(a - b2) for a, b2 in zip(base, now)))
    out = {'hovers': n, 'worst': worst, 'err': c.errs}; c.close(); return out

# ───────────────────────── 7 · 13 · 18. 인쇄
def pdf_of(c, name):
    p = D + 'res/' + name + '.pdf'
    c.pg.pdf(path=p, prefer_css_page_size=True, print_background=True); return p
def margins(p):
    bb = subprocess.run(['pdftotext', '-bbox', p, '-'], capture_output=True, text=True).stdout
    res = []
    for W, H, body in re.findall(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', bb, re.S):
        ws = [tuple(map(float, w)) for w in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"', body)]
        W, H = float(W), float(H)
        res.append([round(min(w[0] for w in ws) * MM, 1), round((W - max(w[2] for w in ws)) * MM, 1), round((H - max(w[3] for w in ws)) * MM, 1), round(W * MM), round(H * MM)])
    return res, bb
def raster(p):
    subprocess.run(['pdftoppm', '-r', '60', '-png', p, p[:-4]], check=True)
    return sorted(x for x in os.listdir(D + 'res') if x.startswith(os.path.basename(p)[:-4] + '-'))
def t07(b, f):
    out = {}
    for o in ('portrait', 'landscape'):
        c = Ctx(b, f)
        c.js("(o)=>{SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>P(i).autofit=true); syncControls(); applyLook(); render(); fitNow(); applyScale();}", o)
        c.pg.wait_for_timeout(150)
        p1 = pdf_of(c, f'p7_{o}_final_{f}')
        m1, bb1 = margins(p1)
        lay = subprocess.run(['pdftotext', '-layout', '-f', '1', '-l', '1', p1, '-'], capture_output=True, text=True).stdout
        multi = any(re.search(r'\d{1,3},\d{3}\s.{3,}?\S.*\d{1,3},\d{3}', l) for l in lay.splitlines())
        # 편집 중(마우스 올린 줄 · 빈 칸 · 넘침 띠 없음) 그대로 Ctrl+P
        c.pg.click('#b-edit'); c.pg.wait_for_timeout(250)
        bb = c.pg.locator('.sheet .row').nth(2).bounding_box(); c.pg.mouse.move(bb['x'] + 20, bb['y'] + 5)
        p2 = pdf_of(c, f'p7_{o}_edit_{f}')
        m2, bb2 = margins(p2)
        i1 = raster(p1); i2 = raster(p2); px = []
        for a, bq in zip(i1, i2):
            A = Image.open(D + 'res/' + a).convert('RGB'); B = Image.open(D + 'res/' + bq).convert('RGB')
            px.append(sum(1 for q in pixels(ImageChops.difference(A, B)) if max(q) > 16) if A.size == B.size else 'size')
        out[o] = {'pages': len(m1), 'size': [x[3:] for x in m1], 'margins': [x[:3] for x in m1], 'multicol': multi,
                  'edit_text_same': re.sub(r'<head>.*?</head>', '', bb1, flags=re.S) == re.sub(r'<head>.*?</head>', '', bb2, flags=re.S),
                  'edit_px_diff': px, 'err': c.errs}
        c.close()
    # 18. 긴 메뉴 이름
    ln = {}
    for L in (8, 14, 18, 22, 30, 45):
        c = Ctx(b, f)
        name = ('가나다라마바사아자차카타파하' * 4)[:L]
        r = c.js("""(nm)=>{const it=MENU.sheets[0][0][0].items[0]; it.name=nm; it.price=13579; render(); applyScale();
           const row=document.querySelector('.sheet .row'), col=row.closest('.col'), pr=row.querySelector('.price');
           const lh=parseFloat(getComputedStyle(row.querySelector('.name')).lineHeight);
           return {lines: Math.round(row.querySelector('.name').getBoundingClientRect().height/lh), priceIn: pr.getBoundingClientRect().right <= col.getBoundingClientRect().right+0.5,
                   colRight: col.getBoundingClientRect().right - document.querySelector('.sheet').getBoundingClientRect().left}}""", name)
        pv = c.js("()=>{document.querySelector('#b-edit').click(); document.querySelector('#b-preview').click(); const row=document.querySelector('.sheet .row'), col=row.closest('.col'); return row.querySelector('.price').getBoundingClientRect().right <= col.getBoundingClientRect().right+0.5}")
        c.js("()=>{document.querySelector('#b-preview').click(); document.querySelector('#b-edit').click();}")
        p = pdf_of(c, f'p18_{L}_{f}')
        bbx = subprocess.run(['pdftotext', '-bbox', '-f', '1', '-l', '1', p, '-'], capture_output=True, text=True).stdout
        xs = [float(x) for x in re.findall(r'xMin="[\d.]+" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">13,579<', bbx)]
        r['pdfPriceXmm'] = [round(x * MM, 1) for x in xs]; r['colRightMm'] = round(r['colRight'] * 25.4 / 96, 1); r['prevIn'] = pv; r['err'] = c.errs
        ln[L] = r; c.close()
    out['long'] = ln
    return out

# ───────────────────────── 14. 저장 왕복 · 옛 저장본
SPECIAL = '</script><b>&amp; <!-- x --> "q" \\\\ 🍷'
def t14(b, f):
    out = {}
    c = Ctx(b, f, dl=True)
    c.js("(s)=>{const it=MENU.sheets[0][0][0].items[0]; it.name=s; it.desc=s; F(0).notes.push(s); MENU.brand.sub=s; render(); touch();}", SPECIAL)
    before = c.js("()=>JSON.stringify([MENU,SETTINGS])")
    fin = c.js(POS, '.row, h2, .note')
    with c.pg.expect_download() as d: c.pg.click('#b-file'); c.pg.click('#b-save')
    p = D + 'res/rt_' + f; d.value.save_as(p); c.close()
    c = Ctx(b, 'res/rt_' + f)
    out['roundtrip_same'] = c.js("()=>JSON.stringify([MENU,SETTINGS])") == before
    out['roundtrip_pos'] = c.js(POS, '.row, h2, .note') == fin
    out['rt_err'] = c.errs; c.close()
    # 옛 저장본: 80번 이전 모양(columns · legend · unit · address · tel · hours.note · 맨 위 장별 키 · footnotes · origin)
    src = open(D + f, encoding='utf-8').read()
    m = re.search(r'(\n<script id="menu-data">)(.*?)(</script>)', src, re.S)
    c = Ctx(b, f)
    legacy = c.js("""()=>{const M=JSON.parse(JSON.stringify(MENU)), S=JSON.parse(JSON.stringify(SETTINGS));
      M.columns = M.sheets[0]; delete M.sheets; M.footnotes = ['모든 메뉴 포장 가능합니다']; M.legend='알프스가 권하는 메뉴'; M.unit='단위 : 원';
      M.address='서울 동작구 서달로14길 24-1'; M.tel='02-000-0000'; M.origin='돼지고기: 국내산'; delete M.feet;
      M.hours[1].time='17:00 — 24:00'; M.hours[1].note='가끔 변동';
      const pg=S.pages[0]; delete S.pages; Object.assign(S,{noren:'low', scale:0.9, showNotes:true, art:'horse', seal:'word', showOrigin:true, layout:'portrait2'}); delete S.orient;
      return 'const MENU = '+JSON.stringify(M,null,2)+';\\n\\nconst SETTINGS = '+JSON.stringify(S,null,2)+';\\n'}""")
    c.close()
    open(D + 'res/legacy_' + f, 'w', encoding='utf-8').write(src[:m.start(2)] + '\n' + legacy.replace('<', '\\u003C') + src[m.end(2):])
    c = Ctx(b, 'res/legacy_' + f, dl=True)
    out['legacy_open'] = c.js("()=>({sheets:MENU.sheets.length, cols:MENU.sheets[0].length, columns:'columns' in MENU, notes:F(0).notes, origin:F(0).origin, hours:MENU.hours[1].time, noren:P(0).noren, ns:P(0).norenScale, orient:SETTINGS.orient, drawn:document.querySelectorAll('.sheet .row').length})")
    with c.pg.expect_download() as d: c.pg.click('#b-file'); c.pg.click('#b-save')
    p = D + 'res/legacy_saved_' + f; d.value.save_as(p)
    saved = open(p, encoding='utf-8').read(); md = re.search(r'\n<script id="menu-data">(.*?)</script>', saved, re.S).group(1)
    out['legacy_saved_oldkeys'] = [k for k in ['"columns"', '"legend"', '"unit"', '"address"', '"tel"', '"note"', '"footnotes"', '"footline"', '"layout"', '"norenTall"', '"sheetArt"', '"line"'] if k in md]
    top = re.search(r'const SETTINGS = (\{.*\});', md, re.S).group(1)
    S = json.loads(top); out['legacy_saved_toplevel_pagekeys'] = [k for k in ['noren','norenScale','scale','art','seal','showNotes','showOrigin','autofit'] if k in S]
    out['legacy_err'] = c.errs; c.close()
    return out

# ───────────────────────── 15. 사용법의 수
def t15(b, f):
    out = {}
    c = Ctx(b, f)
    c.js("()=>{SETTINGS.bilingual=true; syncControls(); applyLook(); render(); applyScale();}"); c.pg.wait_for_timeout(100)
    c.js("()=>document.querySelector('#b-edit').click()"); c.pg.wait_for_timeout(150)   # 252번. 넘침 알림은 쪽 탭 줄(.pstat)의 title 에 있다
    out['bilingual_toast'] = c.js("()=>{const e=document.querySelector('.pagebar .pstat'); return e ? '1쪽이 넘침 · ' + e.title : ''}")
    c.close()
    # 구성별 최대 pt (120 · 201 · 212번 방법)
    pts = {}
    for name, o, nsh, ncol in [('세로 2장 2단', 'portrait', 2, 2), ('세로 1장 2단', 'portrait', 1, 2), ('가로 1장 4단', 'landscape', 1, 4), ('가로 2장 2단', 'landscape', 2, 2), ('가로 1장 2단', 'landscape', 1, 2)]:
        c = Ctx(b, f)
        pts[name] = c.js("""([o,nsh,ncol])=>{const secs=MENU.sheets[0].flat().filter(s=>!s.wine).slice(0,6);
            const per=Math.ceil(secs.length/nsh); const sheets=[];
            for(let s=0;s<nsh;s++){ const part=secs.slice(s*per,(s+1)*per); const cols=Array.from({length:ncol},()=>[]); part.forEach((x,i)=>cols[Math.floor(i*ncol/part.length)].push(x)); sheets.push(cols); }
            MENU.sheets=sheets; MENU.feet=MENU.feet.slice(0,1); SETTINGS.pages=SETTINGS.pages.slice(0,1); SETTINGS.orient=o;
            MENU.sheets.forEach((_,i)=>{P(i).autofit=true;}); syncControls(); applyLook(); render(); fitNow(); applyScale();
            return MENU.sheets.map((_,i)=>+(16*P(i).scale*.9*.75).toFixed(1))}""", [o, nsh, ncol])
        c.close()
    out['pt'] = pts
    c = Ctx(b, f)
    # 원산지 한 줄만큼 바닥 글이 올라가는 양
    out['origin_push'] = c.js("""()=>{const y=()=>document.querySelector('.sheet .note').getBoundingClientRect().top; const a=y();
        P(0).showOrigin=true; F(0).origin='돼지고기: 국내산'; render(); applyScale(); return +(a-y()).toFixed(1)}""")
    # 와인: 한 단 카드 수 · 틈 · 넷째 카드 · 두 줄 끄면 넷
    out['wine'] = c.js("""()=>{P(0).showOrigin=false; F(0).origin=''; render(); applyScale();
        const sh=()=>document.querySelectorAll('.sheet')[1]; const g=()=>getComputedStyle(sh()).getPropertyValue('--wgap');
        const col=MENU.sheets[1][0][0]; const r={cards:col.items.length, gap3:g(), over3:overA4(1)};
        col.items.push(JSON.parse(JSON.stringify(col.items[0]))); render(); applyScale();
        r.over4=overA4(1); r.gap4=g(); r.fitPct4=fitPct(1);
        SETTINGS.wineFields=['bottle','aroma','taste','score']; render(); applyScale(); r.over4_minus2=overA4(1);
        SETTINGS.wineFields=['bottle','grapes','aroma','taste','score']; render(); applyScale(); r.over4_minus1=overA4(1);
        delete SETTINGS.wineFields; col.items.pop(); render(); applyScale();
        // 틈 최대 · 최소: 카드 1장일 때와 넘치기 직전
        const keep=col.items.slice(); col.items.length=1; MENU.sheets[1][1].forEach(s=>{}); render(); applyScale(); r.gapMax=g();
        col.items.length=0; keep.forEach(x=>col.items.push(x)); render(); applyScale();
        return r}""")
    # 와인 이름 한 줄 글자 수
    out['winename'] = c.js("""()=>{const it=MENU.sheets[1][0][0].items[0]; const res=[];
        for(let n=12;n<=22;n++){ it.name='가'.repeat(n); render(); const e=document.querySelectorAll('.sheet')[1].querySelector('.wname .name'); const lh=parseFloat(getComputedStyle(e).lineHeight); res.push([n, Math.round(e.getBoundingClientRect().height/lh)]); }
        const lat=[]; for(let n=12;n<=26;n++){ it.name='Saperavi Kakheti Reserve Wine'.slice(0,n); render(); const e=document.querySelectorAll('.sheet')[1].querySelector('.wname .name'); const lh=parseFloat(getComputedStyle(e).lineHeight); lat.push([n, Math.round(e.getBoundingClientRect().height/lh)]); }
        return {ko:res, latin:lat}}""")
    # 메뉴 이름 한 줄 글자 수 (221번: 18자부터 두 줄)
    out['menuname'] = c.js("""()=>{const it=MENU.sheets[0][0][0].items[0]; const res=[];
        for(let n=12;n<=22;n++){ it.name='가'.repeat(n); render(); applyScale(); const e=document.querySelector('.sheet .row .name'); const lh=parseFloat(getComputedStyle(e).lineHeight); res.push([n, Math.round(e.getBoundingClientRect().height/lh)]); }
        return res}""")
    # 상표 세 줄 높이
    out['label'] = c.js("""()=>{const it=MENU.sheets[1][0][0].items[0]; it.label='ABC\\nDEF\\nGHI'; render(); const l=document.querySelectorAll('.sheet')[1].querySelector('.wlabel');
        return {sh:l.scrollHeight, ch:l.clientHeight, lh:parseFloat(getComputedStyle(l).lineHeight)}}""")
    # ＋ㅡ 4% · 막대 1% · 기본값
    c.js("()=>{MENU.sheets[1][0][0].items[0].label='SAPERAVI'; MENU.sheets[0][0][0].items[0].name='단호박 크림 파스타'; render(); applyScale();}")
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200)
    c.js("()=>{panelTab='page'; syncPageTabs(); syncPage();}")
    s0 = c.js("()=>P(0).scale"); c.pg.click('#b-minus'); s1 = c.js("()=>P(0).scale")
    out['step'] = [s0, s1, c.js("()=>[document.querySelector('#sz-range').step, document.querySelector('#nsz-range').step, P(0).norenScale, document.querySelector('#nsz-val').textContent]")]
    # 창 밀림 시작 폭 (1410px)
    c.close()
    push = []
    for W in (1500, 1420, 1411, 1410, 1409, 1400, 1300):
        c = Ctx(b, f, W, 900)
        a = c.js("()=>document.querySelector('.sheet').getBoundingClientRect().left"); c.pg.click('#b-edit'); c.pg.wait_for_timeout(500)
        push.append([W, round(a - c.js("()=>document.querySelector('.sheet').getBoundingClientRect().left"), 1)]); c.close()
    out['panel_push'] = push
    return out

# ───────────────────────── 16. 줌 뒤 [편집]
def t16(b, f):
    out = {}
    for z in (0.67, 0.75, 0.9, 1.1, 1.25):
        c = Ctx(b, f, 1500, 900)
        cdp = c.c.new_cdp_session(c.pg)
        rel = "()=>{const s=document.querySelectorAll('.sheet');return [...document.querySelectorAll('.row,h2,.note')].map(r=>{const sh=r.closest('.sheet').getBoundingClientRect(),q=r.getBoundingClientRect();return +(q.top-sh.top).toFixed(1)})}"
        cdp.send('Emulation.setDeviceMetricsOverride', {'width': round(1500 / z), 'height': round(900 / z), 'deviceScaleFactor': z, 'mobile': False})
        c.pg.wait_for_timeout(500)
        a = c.js(rel)
        c.js("()=>document.querySelector('#b-edit').click()"); c.pg.wait_for_timeout(300)
        e = c.js(rel)
        out[z] = {'maxmove': max(abs(x - y) for x, y in zip(a, e)) if len(a) == len(e) else 'count', 'err': c.errs}
        c.close()
    return out

# ───────────────────────── 17. 글꼴이 늦게 와도 (컨테이너 대용 세 가지)
def t17(b, f):
    c = Ctx(b, f); out = {}
    out['restore'] = c.js("""()=>{const s=document.querySelector('.sheet'); const good=getComputedStyle(s).getPropertyValue('--price-w');
        document.querySelectorAll('.sheet').forEach(x=>x.style.setProperty('--price-w','3px')); applyScale();
        return [good, getComputedStyle(s).getPropertyValue('--price-w')]}""")
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200)
    loc = c.pg.locator('.sheet .row .name [data-path]').first; loc.click(); c.pg.keyboard.type('Z')
    out['focus'] = c.js("()=>{const a=document.activeElement; applyScale(); return a===document.activeElement && a.textContent.includes('Z')}")
    out['accum'] = c.js("""async ()=>{let n=0; const orig=applyScale; window.applyScale=function(){n++; return orig.apply(this,arguments)};
        const sel=document.querySelector('#f-theme'); const vals=['night','sumi','pat','forest'];
        for(let i=0;i<20;i++){ sel.value=vals[i%4]; sel.dispatchEvent(new Event('change')); }
        const sync=n; await new Promise(r=>setTimeout(r,800)); return [sync, n-sync]}""")
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 21. 창 폭이 결과를 바꾸지 않는지
def t21(b, f):
    c = Ctx(b, f, 1400, 900, dl=True)
    c.js(FIT); c.pg.wait_for_timeout(150)
    with c.pg.expect_download() as d: c.pg.click('#b-file'); c.pg.click('#b-save')
    p = D + 'res/w21_' + f; d.value.save_as(p); c.close()
    out = {}
    for W in (1400, 1024, 900, 780, 640):
        c = Ctx(b, 'res/w21_' + f, W, 900)
        out[W] = c.js("()=>MENU.sheets.map((_,i)=>P(i).scale)")
        if W == 640: out['pdf640'] = margins(pdf_of(c, 'w21_640_' + f))[0]
        c.close()
    return out

# ───────────────────────── 23 · 33 · 34. 좁은 화면
def t23(b, f):
    out = {'clip': {}, 'a4': {}, 'narrow': {}}
    base_lines = None
    LINES = "()=>[...document.querySelectorAll('.sheet .row .name, .sheet .wname, .sheet .note')].map(e=>Math.round(e.getBoundingClientRect().height))"
    for W in (1600, 900, 820, 640, 430, 390):
        c = Ctx(b, f, W, 900)
        dims = c.js("()=>[...document.querySelectorAll('.sheet')].map(s=>[+s.getBoundingClientRect().width.toFixed(2), +s.getBoundingClientRect().height.toFixed(2)])")
        lines = c.js(LINES)
        if base_lines is None: base_lines = lines
        out['a4'][W] = {'dims': dims, 'lines_same': lines == base_lines}
        c.js("()=>document.querySelector('#b-edit').click()"); c.js("()=>document.querySelector('#b-preview').click()"); c.pg.wait_for_timeout(300)
        out['clip'][W] = c.js("()=>[...document.querySelectorAll('.sheet')].map(s=>s.scrollHeight-s.clientHeight)")
        out['a4'][W]['err'] = c.errs; c.close()
    for W in (1024, 900, 834, 768, 560, 430, 390):
        r = {}
        for ed in (False, True):
            c = Ctx(b, f, W, 900)
            if ed: c.pg.click('#b-edit', force=True); c.pg.wait_for_timeout(300)
            r['hscroll_' + str(ed)] = c.js("()=>document.documentElement.scrollWidth-innerWidth")
            r['left0_' + str(ed)] = c.js("()=>{scrollTo(0,0); return +document.querySelector('.sheet').getBoundingClientRect().left.toFixed(1)}")
            r['rightEnd_' + str(ed)] = c.js("()=>{scrollTo(99999,0); return +(innerWidth-document.querySelector('.sheet').getBoundingClientRect().right).toFixed(1)}")
            r['sheetW_' + str(ed)] = c.js("()=>+document.querySelector('.sheet').getBoundingClientRect().width.toFixed(1)")
            if ed:
                r['panel'] = c.js("""()=>{scrollTo(0,0); const p=document.querySelector('#panel').getBoundingClientRect(), bar=document.querySelector('#barwrap').getBoundingClientRect();
                   return {inView: p.left>=-0.5 && p.right<=innerWidth+0.5 && p.top>=-0.5 && p.bottom<=innerHeight+0.5, overBar: p.top<bar.bottom-0.5 && p.bottom>bar.top+0.5 && p.left<bar.right && p.right>bar.left}   /* 283번. 두 상자가 실제로 겹치는가 — 전에는 막대가 아래라고 가정했다 */}""")
            r['fit_' + str(ed)] = c.js("()=>{MENU.sheets.forEach((_,i)=>P(i).autofit=true); fitNow(); applyScale(); return MENU.sheets.map((_,i)=>P(i).scale)}")
            r['err_' + str(ed)] = c.errs; c.close()
        out['narrow'][W] = r
    return out

# ───────────────────────── 24 · 29. 저장 크기
def t24(b, f):
    c = Ctx(b, f, dl=True); sizes = []
    for k in range(3):
        if k == 1: c.pg.click('#b-print') if False else None
        with c.pg.expect_download() as d: c.pg.click('#b-file'); c.pg.click('#b-save')
        p = D + f'res/s24_{k}_' + f; d.value.save_as(p); sizes.append(os.path.getsize(p)); c.pg.wait_for_timeout(300)
        if k == 0:   # 두 번째 저장 전에 화면 상태를 흔든다: 편집 · 꾸미기 탭 · 인쇄 경고 · 도움말
            c.js("()=>{document.querySelector('#b-edit').click(); panelTab='page'; panelPage=1; syncPageTabs(); syncPage(); document.querySelector('#b-edit').click();}")
            c.js("()=>{SETTINGS.bilingual=true; render(); applyScale(); document.querySelector('#b-print').click(); document.querySelector('#ow-go').click(); const d=document.querySelector('#printhint details'); if(d) d.open=true; document.querySelector('#printhint .dlg-x').click(); document.querySelector('#b-help').click(); document.querySelector('#help .dlg-x').click(); SETTINGS.bilingual=false; render(); applyScale(); document.querySelector('#b-edit').click(); document.querySelector('#b-preview').click(); document.querySelector('#b-preview').click();}")
    src = open(D + f, encoding='utf-8').read(); s0 = open(D + 'res/s24_0_' + f, encoding='utf-8').read()
    md = lambda s: re.search(r'\n<script id="menu-data">(.*?)</script>', s, re.S).group(1)
    other0 = len(s0.encode()) - len(md(s0).encode()); othersrc = len(src.encode()) - len(md(src).encode())
    import difflib
    rest = lambda s: re.sub(r'\n<script id="menu-data">.*?</script>', '', s, flags=re.S).splitlines()
    extra = [l[:120] for l in difflib.unified_diff(rest(src), rest(s0), lineterm='', n=0) if l.startswith('+') and not l.startswith('+++')]
    out = {'sizes': sizes, 'nonMenuGrowth': other0 - othersrc, 'extraLines': extra[:40], 'err': c.errs}
    c.close(); return out

# ───────────────────────── 25. 모드 전환 튐
def t25(b, f):
    out = {}
    for H in (700, 900, 1100):
        for W in (1800, 1600, 1500, 1450, 1400, 1366, 1240, 1160, 1120, 1024, 900, 640, 430, 360):
            c = Ctx(b, f, W, H)
            c.js("()=>scrollTo(0,document.documentElement.scrollHeight)"); c.pg.wait_for_timeout(60)
            P_ = "()=>{const s=document.querySelectorAll('.sheet'); const r=s[s.length-1].getBoundingClientRect(); return [+r.top.toFixed(1), +r.left.toFixed(1)]}"
            seq = [c.js(P_)]
            for btn in ('#b-edit', '#b-preview', '#b-preview', '#b-edit'):
                c.js(f"()=>document.querySelector('{btn}').click()"); c.pg.wait_for_timeout(350); seq.append(c.js(P_))
            dy = max(abs(seq[i][0] - seq[i - 1][0]) for i in range(1, 5)); dx = [abs(seq[i][1] - seq[i - 1][1]) for i in range(1, 5)]
            out[f'{W}x{H}'] = {'dy': dy, 'dx': dx, 'dxBad': [d for d in dx if 0.5 < d < 25], 'err': c.errs}
            c.close()
    return out

# ───────────────────────── 27. 상한까지
def t27(b, f):
    c = Ctx(b, f); pg = c.pg
    pg.click('#b-edit'); pg.wait_for_timeout(200)
    c.js("()=>{document.querySelector('#panel').hidden=true; placePanel();}")
    def press(scope_sel, text, times):
        n = 0
        for _ in range(times):
            host = pg.locator(scope_sel).first
            host.evaluate("e=>{const r=e.getBoundingClientRect(); scrollTo(0, r.top+scrollY-120)}"); bb = host.bounding_box()
            pg.mouse.move(bb['x'] + 12, bb['y'] + min(8, bb['height'] / 2)); pg.wait_for_timeout(60)
            btn = host.locator('button', has_text=text)
            if btn.count() and not btn.first.is_visible():   # 부하가 크면 ＋ 가 늦게 뜬다 — 한 번 더 기다린다
                pg.mouse.move(bb['x'] + 14, bb['y'] + min(9, bb['height'] / 2)); pg.wait_for_timeout(250)
            if btn.count() == 0 or not btn.first.is_visible(): break
            b2 = btn.first.bounding_box(); pg.mouse.move(b2['x'] + b2['width'] / 2, b2['y'] + b2['height'] / 2, steps=6)
            pg.mouse.click(b2['x'] + b2['width'] / 2, b2['y'] + b2['height'] / 2); pg.wait_for_timeout(80); pg.keyboard.type('x'); pg.wait_for_timeout(40); n += 1
        return n
    out = {}
    out['secnote'] = [press('.sheet section', '＋ 안내 추가', 8), c.js("()=>(MENU.sheets[0][0][0].notes||[]).length")]
    out['notes'] = [press('.sheet .foot .zone', '＋ 바닥 글 추가', 12), c.js("()=>F(0).notes.length")]
    out['hours'] = [press('.sheet .hours', '＋ 시간 추가', 8), c.js("()=>MENU.hours.length")]
    c.js("()=>{panelTab='common'; syncPageTabs(); document.querySelector('#panel').hidden=false; placePanel();}")
    nb = 0
    for _ in range(12):
        btn = pg.locator('#btpick button', has_text='병 추가')
        if btn.count() == 0 or not btn.first.is_visible(): break
        btn.first.scroll_into_view_if_needed(); btn.first.click(); pg.wait_for_timeout(60); nb += 1
    out['bottles'] = [nb, c.js("()=>(SETTINGS.bottleMore||[]).length")]
    out['plusGone'] = c.js("""()=>{const t=[...document.querySelectorAll('.sheet button')].map(b=>b.textContent.trim());
        return {secnote:!document.querySelector('.sheet section').querySelector(':scope > .addrow button') || ![...document.querySelector('.sheet section').querySelectorAll('button')].some(b=>b.textContent.trim()==='＋ 안내 추가'),
                notes:!t.includes('＋ 바닥 글 추가'), hours:!t.includes('＋ 시간 추가'), bottle:![...document.querySelectorAll('#btpick button')].some(b=>/병 추가/.test(b.textContent))}}""")
    out['null'] = c.js("()=>[...document.querySelectorAll('.sheet')].some(s=>/null|undefined|NaN/.test(s.textContent))")
    c.js("()=>{document.querySelector('#b-edit').click()}")
    out['null_final'] = c.js("()=>[...document.querySelectorAll('.sheet')].some(s=>/null|undefined|NaN/.test(s.textContent))")
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 28. 넘침 표시가 판정과 맞는지
CONS = """()=>[...MENU.sheets.keys()].map(i=>{const s=document.querySelectorAll('.sheet')[i], w=overWhy(i);
  return (s.classList.contains('over')===(w==='tall')) && (s.classList.contains('overwide')===(w==='wide')) && (overPages.includes(i+1)===(w!==null)) && (!window.overReason || (overReason[i+1]||null)===(overPages.includes(i+1)?w:null) || !overPages.includes(i+1))})"""
def t28(b, f):
    c = Ctx(b, f); pg = c.pg; out = []
    pg.click('#b-edit'); pg.wait_for_timeout(200)
    def chk(tag): pg.wait_for_timeout(200); out.append([tag, c.js(CONS), c.js("()=>overPages")])
    SEL = "([id,v])=>{const e=document.getElementById(id); e.value=v; e.dispatchEvent(new Event('change',{bubbles:true}));}"
    CHK = "([id,v])=>{const e=document.getElementById(id); e.checked=v; e.dispatchEvent(new Event('change',{bubbles:true}));}"
    CLK = "(id)=>document.getElementById(id).click()"
    chk('start')
    c.js(SEL, ['f-layout', 'landscape']); chk('landscape')
    c.js(SEL, ['f-layout', 'portrait']); chk('portrait')
    c.js(CHK, ['f-bi', True]); chk('bilingual')
    c.js("()=>{panelTab='page'; syncPageTabs(); syncPage();}")
    for k in range(3): c.js(CLK, 'b-plus'); pg.wait_for_timeout(60)
    chk('plus')
    c.js(CLK, 'b-minus'); chk('minus')
    c.js("()=>{const r=document.querySelector('#sz-range'); r.value=70; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change'));}"); chk('slider70')
    c.js("()=>{const r=document.querySelector('#sz-range'); r.value=120; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change'));}"); chk('slider120')
    c.js(CLK, 'b-fit'); chk('fit')
    c.js("()=>{panelPage=1; syncPageTabs(); syncPage();}"); c.js(CLK, 'b-plus'); c.js(CLK, 'b-plus'); chk('wine plus')
    c.js(CHK, ['f-bi', False]); chk('bi off')
    c.js("()=>{const s=MENU.sheets[0]; MENU.sheets[0]=s.flat().slice(0,6).map(x=>[x]); render();}"); chk('6cols')
    c.js(CLK, 'b-fit'); chk('fit wide')
    r = {'steps': out, 'allOk': all(all(x[1]) for x in out), 'err': c.errs}; c.close(); return r

# ───────────────────────── 30 · 31. 빈 칸
def t30(b, f):
    c = Ctx(b, f); pg = c.pg; out = {}
    pg.click('#b-edit'); pg.wait_for_timeout(200)
    c.js("()=>{const s=MENU.sheets[0][0][0]; s.items[1].desc=''; s.items.splice(3,0,{name:'',price:''}); render(); applyScale();}"); pg.wait_for_timeout(150)
    SEC = "()=>[...document.querySelectorAll('.sheet section, .sheet .row')].map(e=>+(e.getBoundingClientRect().top-e.closest('.sheet').getBoundingClientRect().top).toFixed(1))"
    a = c.js(SEC); c.js("()=>document.querySelector('#b-preview').click()"); pg.wait_for_timeout(300); p_ = c.js(SEC)
    fin = None
    c.js("()=>{document.querySelector('#b-preview').click(); document.querySelector('#b-edit').click();}"); pg.wait_for_timeout(300); fin = c.js(SEC)
    out['edit_vs_prev_samecol'] = max(abs(x - y) for x, y in zip(a, p_)) if len(a) == len(p_) else ('count', len(a), len(p_))
    out['prev_vs_final'] = max(abs(x - y) for x, y in zip(p_, fin)) if len(fin) == len(p_) else ('count', len(p_), len(fin))
    # 128번 기준: 옆 단 이동 · 칸 간격(--gap) 변화
    OTHER = "()=>[...document.querySelectorAll('.sheet')[0].querySelectorAll('.col')[1].querySelectorAll('section, .row')].map(e=>+(e.getBoundingClientRect().top-e.closest('.sheet').getBoundingClientRect().top).toFixed(1))"
    GAP = "()=>getComputedStyle(document.querySelector('.sheet')).getPropertyValue('--gap')"
    c.js("()=>document.querySelector('#b-edit').click()"); pg.wait_for_timeout(250); o1 = c.js(OTHER); g1 = c.js(GAP)
    c.js("()=>document.querySelector('#b-preview').click()"); pg.wait_for_timeout(300); o2 = c.js(OTHER); g2 = c.js(GAP)
    out['otherCol_move'] = max([abs(x - y) for x, y in zip(o1, o2)] + [0]); out['gap'] = [g1, g2]
    # 빈 줄 높이: 완성본 · 미리보기 · 인쇄
    c.js("()=>{document.querySelector('#b-preview').click(); document.querySelector('#b-edit').click();}"); pg.wait_for_timeout(250)
    c.js("()=>{const s=MENU.sheets[0][0][0]; s.items.splice(6,0,{name:'',price:9000}); render(); applyScale();}")
    H = "()=>[...document.querySelectorAll('.sheet .row:not(.wine)')].map(r=>+r.getBoundingClientRect().height.toFixed(1))"
    hf = c.js(H); c.js("()=>{document.querySelector('#b-edit').click(); document.querySelector('#b-preview').click();}"); pg.wait_for_timeout(300); hp = c.js(H)
    c.js("()=>{document.querySelector('#b-preview').click(); document.querySelector('#b-edit').click();}"); pg.wait_for_timeout(250)
    out['blankRowHeights'] = {'final_set': sorted(set(hf)), 'same_as_preview': hf == hp}
    p1 = pdf_of(c, 'blank_' + f); lay = subprocess.run(['pdftotext', '-layout', '-f', '1', '-l', '1', p1, '-'], capture_output=True, text=True).stdout
    out['blankPrint'] = {'has9000': '9,000' in lay, 'pages': len(margins(p1)[0])}
    out['err'] = c.errs
    c.close()
    # 31. 빈 칸 첫 글자
    fc = {}
    for name, prep, sel in [('vol', "()=>{}", '.sheet .row .vol >> nth=2'),
                            ('en', "()=>{SETTINGS.bilingual=true; MENU.sheets[0][0][0].items[2].en=''; render(); applyScale();}", '.sheet section .row:nth-of-type(3) .en'),
                            ('desc', "()=>{MENU.sheets[0][0][0].items[2].desc=''; render(); applyScale();}", '.sheet section .row:nth-of-type(3) .desc')]:
        c = Ctx(b, f); pg = c.pg
        pg.click('#b-edit'); pg.wait_for_timeout(200); c.js(prep); pg.wait_for_timeout(150)
        loc = pg.locator(sel).first
        if loc.count() == 0: fc[name] = 'none'; c.close(); continue
        ROWS = "()=>[...document.querySelectorAll('.sheet .row')].map(e=>+(e.getBoundingClientRect().top+scrollY).toFixed(1))"
        loc.evaluate("e=>e.scrollIntoView({block:'center'})"); before = c.js(ROWS)
        rb = loc.evaluate("e=>{const b=e.closest('.row').getBoundingClientRect(); return [b.left+20,b.top+b.height/2]}"); pg.mouse.move(rb[0], rb[1])
        cp = loc.evaluate(CLICKPT); pg.mouse.move(cp[0], cp[1], steps=6)
        pg.mouse.click(cp[0], cp[1]); before = c.js(ROWS)
        pg.keyboard.type('A'); pg.wait_for_timeout(80); after = c.js(ROWS)
        fc[name] = {'move': max(abs(x - y) for x, y in zip(before, after)), 'typed': loc.evaluate("e=>e.textContent")}
        c.close()
    out['first_char'] = fc
    return out

# ───────────────────────── 32. 가격 칸과 점선 끝
def t32(b, f):
    out = {}
    for name, o, nsh, ncol in [('세로 2장 2단', 'portrait', 2, 2), ('세로 1장 2단', 'portrait', 1, 2), ('가로 1장 4단', 'landscape', 1, 4), ('가로 2장 2단', 'landscape', 2, 2)]:
        c = Ctx(b, f)
        c.js("""([o,nsh,ncol])=>{const secs=MENU.sheets[0].flat().filter(s=>!s.wine).slice(0,6); const per=Math.ceil(secs.length/nsh); const sheets=[];
            for(let s=0;s<nsh;s++){ const part=secs.slice(s*per,(s+1)*per); const cols=Array.from({length:ncol},()=>[]); part.forEach((x,i)=>cols[Math.floor(i*ncol/part.length)].push(x)); sheets.push(cols); }
            MENU.sheets=sheets; SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>P(i).autofit=true); syncControls(); applyLook(); render(); fitNow(); applyScale();}""", [o, nsh, ncol])
        DOT = """()=>[...document.querySelectorAll('.sheet .col')].map(col=>{const xs=[...col.querySelectorAll('.row')].filter(r=>r.offsetHeight&&r.querySelector('.dots').offsetWidth>0).map(r=>r.querySelector('.dots').getBoundingClientRect().right-col.getBoundingClientRect().left); return xs.length? +(Math.max(...xs)-Math.min(...xs)).toFixed(3):0})"""
        PR = "()=>[...document.querySelectorAll('.sheet .row .price')].map(e=>{const s=e.closest('.sheet').getBoundingClientRect(),q=e.getBoundingClientRect(); return [+(q.left-s.left).toFixed(2),+(q.right-s.left).toFixed(2)]})"
        fin_spread = c.js(DOT); fin_pr = c.js(PR)
        c.js("()=>{document.querySelector('#b-edit').click(); document.querySelector('#b-preview').click();}"); c.pg.wait_for_timeout(300)
        pv_spread = c.js(DOT); pv_pr = c.js(PR)
        c.js("()=>document.querySelector('#b-preview').click()"); c.pg.wait_for_timeout(250); ed_pr = c.js(PR)
        md = lambda a, bb: max([abs(x[0] - y[0]) + abs(x[1] - y[1]) for x, y in zip(a, bb)] + [0]) if len(a) == len(bb) else 'count'
        out[name] = {'dotSpreadFinal': max(fin_spread), 'dotSpreadPrev': max(pv_spread), 'price_ed_vs_prev': md(ed_pr, pv_pr), 'price_fin_vs_prev': md(fin_pr, pv_pr), 'err': c.errs}
        c.close()
    return out

# ───────────────────────── 35. 손잡이 잘림
def t35(b, f):
    c = Ctx(b, f, 1500, 1000); pg = c.pg
    pg.click('#b-edit'); pg.wait_for_timeout(250); cut = []
    for tab in ('common', 'page'):
        for pp in (0, 1):
            c.js("([t,p])=>{panelTab=t; panelPage=p; syncPageTabs(); syncPage();}", [tab, pp])
            for kind in ['red', 'white', 'sparkling', 'rose', 'orange']:
                c.js("(k)=>{panelBottle=k; syncBottles();}", kind)
                # 290번 — select 는 scrollWidth 가 글자 폭을 안 따른다('생맥주와 파스'가 잘렸는데 못 잡았다). 고른 글자의 폭을 캔버스로 재 안쪽 폭과 비교한다
                cut += c.js("""()=>{const g=document.createElement('canvas').getContext('2d'); return [...document.querySelectorAll('select')].filter(s=>s.offsetWidth>0).filter(s=>{const cs=getComputedStyle(s);
                  g.font=cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily; const tx=s.options[s.selectedIndex]?.text||'';
                  return s.scrollWidth>s.clientWidth || g.measureText(tx).width > s.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight)}).map(s=>(s.id||s.className||s.title)+':'+s.options[s.selectedIndex]?.text)}""")
    out = {'cut': sorted(set(cut)), 'err': c.errs}; c.close(); return out

# ───────────────────────── 36. 실물 사진 대조 — 그림 코드 동일성
def t36(b, f):
    c = Ctx(b, f)
    r = c.js("()=>JSON.stringify([ART, BOTTLE, SEALS])")
    c.close()
    import hashlib
    return {'hash': hashlib.md5(r.encode()).hexdigest()}

# ───────────────────────── 37. 병 잉크 바닥 − 특징 줄 잉크 바닥
def t37(b, f):
    c = Ctx(b, f, 1600, 1300); res = []; worst = 0
    for o in ('portrait', 'landscape'):
        for fo in font_list(c):
            for sh in SHAPES:
                c.js("""([o,fo,sh,K])=>{SETTINGS.orient=o; SETTINGS.font=fo; SETTINGS.bottles={}; K.forEach(k=>SETTINGS.bottles[k]={shape:sh,color:'ink'});
                   MENU.sheets.forEach((_,i)=>{P(i).art='none'; P(i).autofit=true;}); syncControls(); applyLook(); render(); fitNow(); applyScale();}""", [o, fo, sh, KINDS])
                c.pg.wait_for_timeout(30)
                boxes = c.js("""()=>{const s=document.querySelectorAll('.sheet')[1]; s.scrollIntoView(); return [...s.querySelectorAll('.row.wine')].map(r=>{
                    const b=r.querySelector('.wbottle svg').getBoundingClientRect(), g=r.querySelector('.wscore').getBoundingClientRect();
                    return [b.left+scrollX,b.top+scrollY,b.width,b.height, g.left+scrollX,g.top+scrollY,g.width,g.height]})}""")
                img = Image.open(io.BytesIO(c.pg.screenshot(full_page=True))).convert('L')
                paper = img.getpixel((int(boxes[0][0]) + 2, int(boxes[0][1]) - 6)) if boxes else 230
                for k, (bx, by, bw, bh, gx, gy, gw, gh) in enumerate(boxes):
                    def inkbottom(x0, y0, x1, y1):
                        for y in range(int(y1), int(y0), -1):
                            row = [img.getpixel((x, y)) for x in range(int(x0), int(x1))]
                            if min(row) < paper - 60: return y
                        return None
                    bb_ = inkbottom(bx + 1, by, bx + bw - 1, by + bh + 3)
                    gb = inkbottom(gx, gy, gx + gw, gy + gh + 1)
                    d = None if bb_ is None or gb is None else bb_ - gb
                    if d is None or abs(d) > 1: res.append([o, fo, sh, k, d])
                    if d is not None: worst = max(worst, abs(d))
    out = {'bad': res[:30], 'nbad': len(res), 'worst': worst, 'n': 2 * 8 * 9 * 6, 'over': c.js('()=>[...MENU.sheets.keys()].map(i=>overA4(i))'), 'err': c.errs}; c.close(); return out

# ───────────────────────── 38. 병 아홉 잉크 바닥 · 호일
def t38(b, f):
    c = Ctx(b, f)
    r = c.js("""()=>{const out={}; const host=document.createElement('div'); document.body.appendChild(host);
      for (const k of Object.keys(BOTTLE)){ host.innerHTML=BOTTLE[k]; const svg=host.querySelector('svg'); svg.setAttribute('width',60); svg.setAttribute('height',200);
        const body=svg.querySelector('.wb'), foil=svg.querySelector('.wc'); const pt=svg.createSVGPoint();
        const w=(p,y)=>{let n=0,l=null,r=null; for(let x=0;x<=60;x+=0.25){pt.x=x;pt.y=y; if(p.isPointInFill(pt)){n++; if(l===null)l=x; r=x;}} return [l,r]};
        let bottom=0; for(let y=0;y<=200;y+=0.25){ const [l]=w(body,y); if(l!==null) bottom=y; }
        let over=0; for(let y=0;y<=200;y+=0.5){ const [fl,fr]=foil?w(foil,y):[null,null]; if(fl===null) continue; const [bl,br]=w(body,y);
          if (bl===null) continue; const o = Math.max(bl-fl, fr-br, 0); over=Math.max(over,o); }
        out[k]=[bottom, +over.toFixed(2)]; }
      host.remove(); return out}""")
    c.close(); return r

# ───────────────────────── 39. 망가진 저장본
def t39(b, f):
    src = open(D + f, encoding='utf-8').read()
    m = re.search(r'(\nconst SETTINGS = )(\{.*?\})(;\n)', src, re.S)
    S = json.loads(m.group(2))
    S.update({'font': 'nope', 'theme': 42, 'mark': 'toolongmark', 'pageno': 'zzz', 'secAlign': 'diag', 'wineAlign': 5})   # 274번. 'X' 는 이제 올바른 글자 표시(영문 1자) — 7자 넘는 글자로 시험
    for k, pg in enumerate(S.get('pages', [])):
        pg.update({'noren': 'bogus', 'art': 'dragon', 'seal': 7,
                   'norenScale': ['abc', None, 0, -1][k % 4], 'scale': ['big', -2, 0, None][k % 4]})
    bad = src[:m.start(2)] + json.dumps(S, ensure_ascii=False, indent=2).replace('<', '\\u003C') + src[m.end(2):]
    open(D + 'res/bad_' + f, 'w', encoding='utf-8').write(bad)
    c = Ctx(b, 'res/bad_' + f)
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200)
    out = c.js("""()=>{const r={}; r.S={font:SETTINGS.font, theme:SETTINGS.theme, mark:SETTINGS.mark, pageno:SETTINGS.pageno, sec:SETTINGS.secAlign, wine:SETTINGS.wineAlign};
      r.pages=MENU.sheets.map((_,i)=>[P(i).noren, P(i).art, P(i).seal, P(i).scale, P(i).norenScale]);
      r.ui={font:document.querySelector('#f-font').value, theme:document.querySelector('#f-theme').value, mark:document.querySelector('#f-mark').value, pageno:document.querySelector('#f-pageno').value,
            sec:document.querySelector('#f-secalign').value, wine:document.querySelector('#f-winealign').value};
      r.pageui=[]; for (const i of [0,1]){ panelPage=i; panelTab='page'; syncPageTabs(); syncPage(); r.pageui.push([document.querySelector('#f-noren').value, document.querySelector('#f-art').value, document.querySelector('#f-seal').value, document.querySelector('#sz-val').textContent, document.querySelector('#nsz-val').textContent]); }
      r.sheets=document.querySelectorAll('.sheet').length; r.rows=document.querySelectorAll('.sheet .row').length;
      r.nr=[...document.querySelectorAll('.noren')].map(n=>n.className); return r}""")
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 40. 도장
def t40(b, f):
    c = Ctx(b, f); pg = c.pg
    SE = "()=>[...document.querySelectorAll('.sheet')].map(s=>{const e=s.querySelector('.seal'); if(!e) return null; const a=s.getBoundingClientRect(), q=e.getBoundingClientRect(); return [+(a.right-q.right).toFixed(2), +(a.bottom-q.bottom).toFixed(2), +q.width.toFixed(2), +q.height.toFixed(2)]})"
    base = c.js(SE); steps = []
    def st(tag, js=None):
        if js: c.js(js)
        pg.wait_for_timeout(120); steps.append([tag, c.js(SE) == base, c.js(SE)])
    st('add', "()=>{MENU.sheets[0][0][0].items.push({name:'추가',price:1000}); render(); applyScale();}")
    st('del', "()=>{MENU.sheets[0][0][0].items.splice(0,2); render(); applyScale();}")
    st('notes5', "()=>{const n=F(0).notes; while(n.length<5) n.push('안내 '+n.length); render(); applyScale();}")
    st('origin', "()=>{P(0).showOrigin=true; F(0).origin='돼지고기: 국내산, 쌀: 국내산'; render(); applyScale();}")
    st('scaleUp', "()=>{P(0).scale=1.15; render(); applyScale();}")
    st('scaleDown', "()=>{P(0).scale=0.7; render(); applyScale();}")
    st('edit', "()=>document.querySelector('#b-edit').click()")
    st('prev', "()=>document.querySelector('#b-preview').click()")
    st('editEnd', "()=>{document.querySelector('#b-preview').click(); document.querySelector('#b-edit').click();}")
    out = {'base': base, 'steps': steps, 'allSame': all(s[1] for s in steps), 'err': c.errs}; c.close(); return out

# ───────────────────────── 41. 칸 아래 구멍 · 틈
def t41(b, f):
    c = Ctx(b, f)
    out = c.js("""()=>[...document.querySelectorAll('.sheet')].map((sh,i)=>{
      const room=bodyRoom(sh); const body=sh.querySelector('.body').getBoundingClientRect();
      const cols=[...sh.querySelectorAll('.col')].map(col=>{const secs=[...col.querySelectorAll(':scope > section')]; const last=secs[secs.length-1];
         return last? +(body.top+room-last.getBoundingClientRect().bottom).toFixed(1) : null});
      const sg=new Set(), rg=new Set();
      sh.querySelectorAll('.col').forEach(col=>{const secs=[...col.querySelectorAll(':scope > section')];
        for(let k=1;k<secs.length;k++) sg.add(+(secs[k].getBoundingClientRect().top-secs[k-1].getBoundingClientRect().bottom).toFixed(1));
        secs.forEach(s=>{const rows=[...s.querySelectorAll(':scope .row')].filter(r=>r.offsetHeight); for(let k=1;k<rows.length;k++) rg.add(+(rows[k].getBoundingClientRect().top-rows[k-1].getBoundingClientRect().bottom).toFixed(1));});});
      return {holes:cols, secGaps:[...sg], rowGaps:[...rg]}})""")
    out = {'sheets': out, 'err': c.errs}; c.close(); return out

# ───────────────────────── 42. 정렬 셋
def t42(b, f):
    out = {}
    for al in ('left', 'center', 'right'):
        c = Ctx(b, f)
        c.js("(a)=>{SETTINGS.secAlign=a; SETTINGS.wineAlign=a; syncControls(); applyLook(); render(); applyScale();}", al)
        Q = "()=>[...document.querySelectorAll('.sheet h2 .hv, .sheet .wname .name')].map(e=>{const s=e.closest('.sheet').getBoundingClientRect(),q=e.getBoundingClientRect(); return [+(q.left-s.left).toFixed(1),+(q.top-s.top).toFixed(1)]})"
        MARG = "()=>[...document.querySelectorAll('.sheet h2')].map(h=>{const q=h.querySelector('.hv').getBoundingClientRect(), box=h.closest('section').getBoundingClientRect(); return +((q.left-box.left)-(box.right-q.right)).toFixed(1)})"
        fin = c.js(Q); marg = c.js(MARG) if al == 'center' else None
        c.js("()=>document.querySelector('#b-edit').click()"); c.pg.wait_for_timeout(250); ed = c.js(Q)
        c.js("()=>document.querySelector('#b-preview').click()"); c.pg.wait_for_timeout(300); pv = c.js(Q)
        md = lambda a, bb: max([abs(x[0] - y[0]) + abs(x[1] - y[1]) for x, y in zip(a, bb)] + [0]) if len(a) == len(bb) else 'count'
        out[al] = {'edit': md(fin, ed), 'prev': md(fin, pv), 'centerMarginDiff': marg, 'err': c.errs}
        c.close()
    return out

# ───────────────────────── 43. 두 줄 쓰기
def t43(b, f):
    c = Ctx(b, f, dl=True); pg = c.pg; out = {}
    pg.click('#b-edit'); pg.wait_for_timeout(200)
    for name, sel, getter in [('sec', '.sheet h2 .hv', "MENU.sheets[0][0][0].name"),
                              ('wine', ".sheet .wname .name [data-path]", "MENU.sheets[1][0][0].items[0].name"),
                              ('label', '.sheet .wlabel', "MENU.sheets[1][0][0].items[0].label")]:
        loc = pg.locator(sel).first; loc.evaluate("e=>e.scrollIntoView({block:'center'})")
        loc.evaluate("e=>{e.focus(); const r=document.createRange(); r.selectNodeContents(e); r.collapse(false); const s=getSelection(); s.removeAllRanges(); s.addRange(r);}")
        for k in range(4): pg.keyboard.press('Enter'); pg.keyboard.type('L' + str(k))
        pg.wait_for_timeout(100)
        v = c.js("()=>" + getter)
        loc2 = pg.locator(sel).first
        lh = loc2.evaluate("e=>[e.getBoundingClientRect().height, parseFloat(getComputedStyle(e).lineHeight), e.scrollHeight, e.clientHeight]")
        out[name] = {'value': v, 'newlines': v.count('\n'), 'heightLines': round(lh[0] / lh[1], 1), 'raw': lh}
    c.js("()=>document.querySelector('#b-edit').click()")
    with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
    p = D + 'res/t43_' + f; d.value.save_as(p); c.close()
    c = Ctx(b, 'res/t43_' + f)
    out['saved'] = c.js("()=>[MENU.sheets[0][0][0].name, MENU.sheets[1][0][0].items[0].name, MENU.sheets[1][0][0].items[0].label]")
    out['err'] = c.errs; c.close(); return out


# ───────────────────────── 8 · 9 · 12. 안내창 — 창 크기 · 열 때 · 단추
def t08(b, f):
    out = {}
    for H in (1150, 900, 800, 760, 700, 640, 600):
        for W in (1400, 390):
            c = Ctx(b, f, W, H); pg = c.pg; res = {}
            for dlg, btn in (('printhint', '#b-print'), ('help', '#b-help')):
                c.js("()=>{MENU.sheets.forEach((_,i)=>P(i).autofit=true); fitNow(); applyScale();}")   # 경고창 없이
                c.js(f"()=>document.querySelector('{btn}').click()"); pg.wait_for_timeout(150)
                for state in ('closed', 'open'):
                    if state == 'open':
                        if dlg != 'printhint' or not c.js("()=>!!document.querySelector('#printhint details')"): continue
                        c.js("()=>document.querySelector('#printhint summary').click()"); pg.wait_for_timeout(150)
                    res[f'{dlg}-{state}'] = c.js("""(id)=>{const d=document.getElementById(id); if(!d.open) return {notOpen:true}; const dr=d.getBoundingClientRect();
                      const vis=el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth};
                      const foot=[...d.querySelectorAll('.foot2 button, .foot2 input')];
                      const hit=foot.every(el=>{const r=el.getBoundingClientRect();const e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return e===el||el.contains(e)||!!(e&&e.closest('label')&&e.closest('label').contains(el))});
                      const over=[...d.querySelectorAll('.in *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.right>dr.right+1||r.left<dr.left-1)}).length;
                      const h3=d.querySelector('h3'); const det=d.querySelector('details[open]'); let detVis=null;
                      if(det){const ft=d.querySelector('.foot2'); const p=det.querySelector('p'); detVis=!ft||!p||p.getBoundingClientRect().top<ft.getBoundingClientRect().top;}
                      return {foot:foot.every(vis), hit, over, shadeOk: !d.querySelector('.foot2') || d.classList.contains('hasmore')===(d.scrollHeight-d.clientHeight-d.scrollTop>1),
                              detVis, top: d.scrollTop, h3: h3? h3.getBoundingClientRect().top>=dr.top-1 : true}}""", dlg)
                    if state == 'closed' and dlg == 'printhint': res[f'{dlg}-{state}']['atOpenTop'] = res[f'{dlg}-{state}']['top'] == 0
                pg.keyboard.press('Escape'); pg.wait_for_timeout(80)
            out[f'{W}x{H}'] = {'r': res, 'err': c.errs}; c.close()
    return out

# ───────────────────────── 10. 넘침 경고창 문구
def t10(b, f):
    out = {}
    W = "()=>[document.querySelector('#overwarn').open, (document.querySelector('#ow-title')||{}).textContent, document.querySelector('#ow-msg').textContent, (document.querySelector('#ow-sub')||document.querySelector('#overwarn .sub')).textContent]"
    cases = {'tall': "()=>{SETTINGS.bilingual=true; MENU.sheets.forEach((_,i)=>P(i).autofit=false); render(); applyScale();}",
             'wide': "()=>{const all=MENU.sheets[0].flat().filter(s=>!s.wine).slice(0,6).map(s=>({...s,items:s.items.slice(0,3),notes:[]})); MENU.sheets[0]=all.map(s=>[s]); render(); applyScale();}"}
    for k, js in cases.items():
        c = Ctx(b, f); c.js("()=>{window.print=()=>{}}"); c.js(js); c.pg.wait_for_timeout(200)
        why = c.js("()=>[...MENU.sheets.keys()].map(i=>overWhy(i))")
        c.js("()=>document.querySelector('#b-print').click()"); c.pg.wait_for_timeout(150)
        w = c.js(W); t = c.js("()=>document.querySelector('#undo').hidden?'':document.querySelector('#undo .t').textContent")
        out[k] = {'why': why, 'warn': w, 'toast': t, 'err': c.errs}; c.close()
    return out

# ───────────────────────── 11. 인쇄 안내 끄고 되살리기
def t11(b, f):
    c = Ctx(b, f, dl=True); pg = c.pg; st = []
    c.js("()=>{window.__p=0; window.print=()=>{window.__p++}; MENU.sheets.forEach((_,i)=>P(i).autofit=true); fitNow(); applyScale();}")
    c.js("()=>document.querySelector('#b-print').click()"); pg.wait_for_timeout(100)
    st.append(['열림', c.js("()=>document.querySelector('#printhint').open")])
    c.js("()=>{document.querySelector('#ph-skip').checked=true; document.querySelector('#ph-go').click()}"); pg.wait_for_timeout(200)
    st.append(['끔', c.js("()=>[__p, SETTINGS.printHint, document.body.classList.contains('unsaved')]") == [1, False, True]])
    c.js("()=>document.querySelector('#b-print').click()"); pg.wait_for_timeout(200)
    st.append(['바로 인쇄', c.js("()=>[__p, document.querySelector('#printhint').open]") == [2, False]])
    has = c.js("()=>!!document.querySelector('#help-ph')")
    if has:
        c.js("()=>document.querySelector('#b-help').click()"); pg.wait_for_timeout(100)
        st.append(['도움말 체크 꺼짐', c.js("()=>document.querySelector('#help-ph').checked") is False])
        c.js("()=>{const e=document.querySelector('#help-ph'); e.checked=true; e.dispatchEvent(new Event('change')); document.querySelector('#help .dlg-x').click();}")
        st.append(['되살림', c.js("()=>'printHint' in SETTINGS") is False])
        c.js("()=>document.querySelector('#b-print').click()"); pg.wait_for_timeout(100)
        st.append(['체크 빈 채 열림', c.js("()=>[document.querySelector('#printhint').open, document.querySelector('#ph-skip').checked]") == [True, False]])
    out = {'steps': st, 'hasHelpToggle': has, 'err': c.errs}; c.close(); return out

# ───────────────────────── 정적 검사 · 원본 대조(230번)
def tstatic(b, f):
    src = open(D + f, encoding='utf-8').read()
    st = src[src.index('\n<style>'):src.index('\n</style>')]; body = src[src.index('\n<body'):]   # 파일 머리 주석에도 같은 글자가 있다
    scr = src[src.index('<script>\n', src.index('\n<script id="menu-data">')) + 9:src.rindex('</script>')]
    open(D + 'res/_js_' + f + '.js', 'w', encoding='utf-8').write(scr)
    try: node = subprocess.run(['node', '--check', D + 'res/_js_' + f + '.js'], capture_output=True, text=True).returncode == 0
    except FileNotFoundError: node = 'node 없음'
    import collections
    tags = {}
    for m in re.finditer(r'<dialog id="(\w+)">(.*?)</dialog>', body, re.S):
        tags[m.group(1)] = {t: (len(re.findall(r'<' + t + r'[\s>]', m.group(2))), m.group(2).count('</' + t + '>')) for t in ('div', 'p', 'ul', 'ol', 'li', 'details', 'label')}
    return {'css_comments': [st.count('/*'), st.count('*/')], 'html_comments': [body.count('<!--'), body.count('-->')], 'node': node,
            'dialog_tags_ok': all(a == c for d in tags.values() for a, c in d.values()), 'dialog_tags': tags}

def origdiff(new, base):
    import difflib
    a = open(D + base, encoding='utf-8').read().splitlines(); bb = open(D + new, encoding='utf-8').read().splitlines()
    st = next(i for i, l in enumerate(bb) if l.startswith('<script id="menu-data">'))
    en = next(i for i in range(st, len(bb)) if bb[i].startswith('</script>'))
    ops = [o for o in difflib.SequenceMatcher(None, a, bb, autojunk=False).get_opcodes() if o[0] != 'equal']
    blocks, miss, nums = 0, [], set()
    for t, i1, i2, j1, j2 in ops:
        if st <= j1 <= en: continue
        blocks += 1
        n = re.findall(r'(\d{2,3})번', '\n'.join(a[i1:i2] + bb[j1:j2])) or re.findall(r'(\d{2,3})번', '\n'.join(bb[max(0, j1 - 40):j2 + 40]))
        if not n: miss.append((i1 + 1, j1 + 1, '\n'.join(bb[j1:j2])[:80]))
        nums.update(n)
    return {'blocks': blocks, 'missing': miss, 'numbers': sorted(nums, key=int)[-15:]}


# ───────────────────────── 4-가. 줄 도구가 가격을 덮지 않는지 (238번)
def t04p(b, f):
    out = {}
    for name, o, n in (('세로 2단', 'portrait', None), ('가로 2단', 'landscape', None), ('가로 4단', 'landscape', 4)):
        c = Ctx(b, f, 1600, 900); pg = c.pg
        c.js("([o,n])=>{SETTINGS.orient=o; if(n){const secs=MENU.sheets[0].flat().filter(s=>!s.wine); MENU.sheets[0]=Array.from({length:n},(_,k)=>secs.filter((_,i)=>i%n===k));} render(); applyScale();}", [o, n])
        pg.click('#b-edit'); pg.wait_for_timeout(250)
        bad = []
        for L in range(8, 46, 2):
            c.js("(L)=>{const it=MENU.sheets[0][0][0].items[1]; it.name=('가나다라 마바사아 자차카타 파하가나 '.repeat(4)).slice(0,L); render();}", L); pg.wait_for_timeout(50)
            row = pg.locator('.sheet .row').nth(1); row.evaluate("e=>e.scrollIntoView({block:'center'})"); bb = row.bounding_box()
            pg.mouse.move(5, 5); pg.mouse.move(bb['x'] + 12, bb['y'] + 6); pg.wait_for_timeout(40)
            pr = row.locator('.price').bounding_box(); cx, cy = pr['x'] + pr['width'] / 2, pr['y'] + pr['height'] / 2
            pg.mouse.move(cx, cy, steps=10)
            if not c.js("([x,y])=>{const e=document.elementFromPoint(x,y); return !!(e&&e.closest('.price'))}", [cx, cy]): bad.append(L)
        out[name] = bad; out[name + '_err'] = c.errs; c.close()
    return out

# ───────────────────────── 31-가. 보이는 빈 "용량" 상자를 눌러 입력되는지 (238번)
def t31v(b, f):
    res = []
    for sc in (1, 0.6, 1.2):
        for pick in (False, True):
            for long in (False, True):
                c = Ctx(b, f, 1600, 900); pg = c.pg
                c.js("([s,pk,lg])=>{SETTINGS.orient=lg?'landscape':'portrait'; P(0).scale=s; const it=MENU.sheets[0][0][0].items[2]; it.pick=pk; delete it.vol; if(lg) it.name='아주 아주 긴 메뉴 이름을 넣어 두 줄로 접히는지 보는 줄입니다'; render(); applyScale();}", [sc, pick, long])
                pg.click('#b-edit'); pg.wait_for_timeout(250)
                row = pg.locator('.sheet .row').nth(2); row.evaluate("e=>e.scrollIntoView({block:'center'})"); bb = row.bounding_box()
                pg.mouse.move(bb['x'] + 12, bb['y'] + 6); pg.wait_for_timeout(50)
                cp = row.locator('.vol').evaluate(CLICKPT)
                pg.mouse.move(cp[0], cp[1], steps=8); pg.mouse.click(cp[0], cp[1]); pg.wait_for_timeout(50)
                pg.keyboard.type('500ml'); pg.wait_for_timeout(60)
                ok = c.js("()=>{const it=MENU.sheets[0][0][0].items[2]; return it.vol==='500ml' && !it.name.endsWith('500ml')}")
                res.append([sc, pick, long, ok]); c.close()
    return {'cases': res}

# ───────────────────────── 44. 창 손잡이의 동작 (239번)
def t44(b, f):
    out = {}
    c = Ctx(b, f); pg = c.pg; pg.click('#b-edit'); pg.wait_for_timeout(200)
    # (a) [다른 장에도 똑같이] — 켜짐(키 없음)도 옮겨 가는지. 2쪽을 끄고 1쪽은 켠 채 복사
    out['copy'] = c.js("""()=>{ panelPage=0; delete P(0).showNotes; delete P(0).showTitle; delete P(0).showSub;
      P(1).showNotes=false; P(1).showTitle=false; P(1).showSub=false; syncPage(); document.querySelector('#b-copypage').click();
      return PAGE_KEYS.every(k=>JSON.stringify(P(0)[k])===JSON.stringify(P(1)[k])) }""")
    # (b) 병 색 상자가 지금 쓰는 색인지 — color-mix 값(짚색 등)이 검게 나오면 안 된다
    out['swatch'] = c.js("""()=>{ const o={}; for (const k of ['white','sparkling','rose','orange']){ panelBottle=k; syncBottles();
      const v=document.querySelectorAll('#f-bottle input[type=color]')[0].value; o[k]=[v, bottleProbeHex(COLOR_CSS.bottle[bottleOf(k).color])]; } return o }""")
    # (c) 색 고르기 창을 끄는 동안 그 상자가 문서에 남는지 · 되돌리기가 안 쌓이는지
    out['drag'] = c.js("""()=>{ panelBottle='red'; syncBottles(); const n0=undoStack.length;
      const ci=document.querySelectorAll('#f-bottle input[type=color]')[0];
      for (let i=0;i<20;i++){ ci.value='#'+(0x203040+i*3).toString(16); ci.dispatchEvent(new Event('input',{bubbles:true})); }
      const r=[ci.isConnected, undoStack.length-n0, (SETTINGS.bottles||{}).red && SETTINGS.bottles.red.color];
      const cp=document.querySelector('#c-accent'), n1=undoStack.length;
      for (let i=0;i<20;i++){ cp.value='#'+(0x502010+i*3).toString(16); cp.dispatchEvent(new Event('input',{bubbles:true})); }
      r.push(undoStack.length-n1); return r }""")
    # (c-2) 240번. 끄는 동안은 다시 그리지 않고(render 0번), 그 병을 쓰는 카드만 다음 화면에 바뀌는지 — 다른 종류를 빌린 카드 포함
    out['live'] = c.js("""async ()=>{ MENU.sheets[1][1][1].items[0].bottle='red'; render(); panelBottle='red'; syncBottles();
      const frame=()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      let n=0; const R=render; render=(...a)=>{n++; return R(...a)};
      const ci=document.querySelectorAll('#f-bottle input[type=color]')[0];
      for (let i=0;i<20;i++){ ci.value='#4'+(i%10)+'2030'; ci.dispatchEvent(new Event('input',{bubbles:true})); }
      await frame(); render=R;
      const cards=[...document.querySelectorAll('#pages .row.wine .wbottle')];
      const red=cards.filter(x=>x.dataset.bk==='red').map(x=>x.style.getPropertyValue('--bcol'));
      const other=cards.filter(x=>x.dataset.bk!=='red').map(x=>x.style.getPropertyValue('--bcol'));
      ci.dispatchEvent(new Event('change',{bubbles:true}));
      return [n, red.length, red.every(v=>v==='#492030'), other.some(v=>v==='#492030')] }""")
    # (d) [＋ 와인 장 추가]의 빈 카드에 0 이 찍히지 않는지
    out['wineprice'] = c.js("""()=>{ document.querySelector('.pagebar .addbtn:nth-of-type(2)').click(); toggleEdit();
      const t=document.querySelectorAll('.sheet')[1].querySelector('.row.wine .price').textContent; toggleEdit(); return t }""")
    # (e) 상단 크기 ＋ㅡ 걸음 = 글자 크기 ＋ㅡ 걸음(4%)
    out['nstep'] = c.js("""()=>{ panelTab='page'; panelPage=0; syncPageTabs(); P(0).norenScale=0.8; document.querySelector('#b-nplus').click(); return P(0).norenScale }""")
    # (f) 저장한 뒤 [＋ 병 추가] — 빈 목록 키를 지운 뒤에도 병이 남는지
    out['saveadd'] = c.js("""()=>{ const d=download; download=()=>{}; saveFile(); toggleEdit();
      delete SETTINGS.bottleMore; syncBottles(); const btn=document.querySelector('#btpick .addb'); saveFile(); toggleEdit(); download=d;
      btn.click(); return [bottleMore().length, panelBottle[0]==='@'] }""")
    out['err'] = c.errs; c.close()
    return out

# ───────────────────────── 판정
# ───────────────────────── 45. 프린터가 못 찍는 테두리(241번)
#   글자 · 로고 · 도장 · 쪽 번호 · 액자 윗선이 종이 네 변에서 --nogo(4mm, 242번) + 1mm 넘게 안쪽인지.
#   글자는 **글자 상자**(Range)로, 로고 · 도장은 요소 상자로 잰다. 그림(.art)은 일부러 종이 끝까지 가므로 뺀다.
#   그리고 흰 테두리(.nogo)가 4mm 이고 완성본 · 미리보기 · 인쇄(편집 중 인쇄도)는 흰색, 편집은 반투명 흰색인지
EDGE = """()=>{const mm=v=>+(v/96*25.4).toFixed(1); const out=[];
  document.querySelectorAll('.sheet').forEach((s,si)=>{const R=s.getBoundingClientRect();
    const add=(k,tag)=>{ if(!k.width||!k.height) return; out.push([si,tag,mm(k.top-R.top),mm(R.bottom-k.bottom),mm(k.left-R.left),mm(R.right-k.right)]) };
    s.querySelectorAll('.logo,.seal').forEach(e=>{ if(getComputedStyle(e).visibility!=='hidden') add(e.getBoundingClientRect(), e.className.baseVal ?? e.className) });
    const w=document.createTreeWalker(s, NodeFilter.SHOW_TEXT); let n;
    while((n=w.nextNode())){ if(!n.textContent.trim()) continue; const el=n.parentElement;
      if(el.closest('.art,.guide,.nogo')) continue; const cs=getComputedStyle(el); if(cs.display==='none'||cs.visibility==='hidden') continue;
      const r=document.createRange(); r.selectNodeContents(n); for(const k of r.getClientRects()) add(k, el.className||el.tagName) }
    const fr=s.querySelector('.noren.nr-frame'); if(fr){ const t=parseFloat(getComputedStyle(fr,'::before').top); out.push([si,'frame-line',mm(t),99,99,99]) }
  });
  return [0,1,2,3].map(i=>out.reduce((a,x)=>x[2+i]<a[2+i]?x:a))}"""
def t45(b, f):
    out = {'worst': {}, 'show': {}}
    for o in ('portrait', 'landscape'):
        c = Ctx(b, f, W=1600, H=1000)
        for nr in NOREN:
            for ns in (0.6, 0.8, 1.05):
                c.js("([o,nr,ns])=>{SETTINGS.orient=o; SETTINGS.pageno='of'; MENU.sheets.forEach((_,i)=>{const p=P(i); p.noren=nr; p.norenScale=ns; p.autofit=true});}", [o, nr, ns]); c.js(FIT)
                for side, x in zip(('top', 'bottom', 'left', 'right'), c.js(EDGE)):
                    k = o + ':' + side; v = x[2 + ('top', 'bottom', 'left', 'right').index(side)]
                    if k not in out['worst'] or v < out['worst'][k][0]: out['worst'][k] = [v, nr, ns, x[1]]
        vis = "()=>[...document.querySelectorAll('.nogo')].map(e=>{const c=getComputedStyle(e); return [c.display, +(parseFloat(c.borderTopWidth)/96*25.4).toFixed(1), c.borderTopColor, c.outlineStyle]})"
        out['show'][o] = {'idle': c.js(vis)}
        c.pg.click('#b-edit'); c.pg.wait_for_timeout(150); out['show'][o]['edit'] = c.js(vis)
        c.pg.emulate_media(media='print'); out['show'][o]['editPrint'] = c.js(vis); c.pg.emulate_media(media='screen')
        c.pg.click('#b-preview'); c.pg.wait_for_timeout(150); out['show'][o]['preview'] = c.js(vis)
        out['err_' + o] = c.errs; c.close()
    return out

# ───────────────────────── 46. 넘침 판정 · 바닥 고정 · 위 여백(244 ~ 256번). 265번에서 넣었다 — 그전에는 흉내 스크립트로만 봤다(7장)
#   흉내 조건은 부록 A 각 항목의 "흉내" 줄 그대로. 벌린 틈 · 빈 자리를 키운 뒤에는 applyScale() 을 부르지 않고 overWhy() 만 부른다 —
#   다시 벌리면(spread) 키운 것이 흡수돼 흉내가 사라진다. 구성마다 새로 연다(126번)
T46_SEC = "(n)=>{const s=document.querySelectorAll('.sheet')[0]; const col=s.querySelectorAll('.body .col')[1]; const sec=[...col.children].pop(); sec.style.paddingBottom=n+'px'; return overWhy(0)}"
def t46(b, f):
    out = {}
    c = Ctx(b, f)
    gap0 = c.js("()=>{const s=document.querySelector('.sheet'),o=s.getBoundingClientRect(); return +(o.bottom-s.querySelector('.foot').getBoundingClientRect().bottom).toFixed(1)}")
    c.js("()=>{for(let i=0;i<8;i++) MENU.sheets[0][0][0].items.push({name:'넘침 시험 '+i, price:9000}); render(); applyScale();}")
    gap1 = c.js("()=>{const s=document.querySelector('.sheet'),o=s.getBoundingClientRect(); return +(o.bottom-s.querySelector('.foot').getBoundingClientRect().bottom).toFixed(1)}")
    out['244_foot_fixed'] = [gap0, gap1, c.js("()=>overWhy(0)")]            # 바닥은 그대로 · 진짜 넘침은 tall
    out['err'] = list(c.errs); c.close()
    c = Ctx(b, f)                                                             # 245 — 와인 칸 아래 3px 안 보이는 요소는 넘침이 아니다
    out['245_invisible'] = c.js("()=>{const s=document.querySelectorAll('.sheet')[1]; const sec=[...s.querySelectorAll('.body .col')].map(x=>[...x.children].pop()).pop(); const d=document.createElement('div'); d.style.cssText='height:3px;visibility:hidden'; sec.append(d); return overWhy(1)}")
    out['err'] += c.errs; c.close()
    for n in (10, 30, 45, 60):                                                # 248 · 251 · 252 — 빈 자리로 키운 것은 넘침이 아니다
        c = Ctx(b, f); out[f'sec_pad_{n}'] = c.js(T46_SEC, n); out['err'] += c.errs; c.close()
    for seal in ('on', 'off'):                                                # 254 · 255 — 빈 분류의 밑줄이 도장 윗변을 20px 지나면: 도장 켬 = 넘침, 끔 = 아님
        c = Ctx(b, f)
        out['254_line_' + seal] = c.js("""(off)=>{ if(off){ P(0).seal='none'; }
          MENU.sheets[0][1].push({name:'', items:[]}); render();
          const s=document.querySelectorAll('.sheet')[0]; const seal=s.querySelector('.seal'); const col=s.querySelectorAll('.body .col')[1]; const sec=[...col.children].pop();
          const sealTop = off ? (s.getBoundingClientRect().bottom - 40 - 52) : seal.getBoundingClientRect().top;
          const line = sec.getBoundingClientRect().bottom; sec.style.marginTop = (parseFloat(getComputedStyle(sec).marginTop) + (sealTop + 20 - line)) + 'px';
          return [overWhy(0), Math.round(sec.getBoundingClientRect().bottom - sealTop)] }""", seal == 'off')
        out['err'] += c.errs; c.close()
    top = {}
    for o in ('portrait', 'landscape'):                                       # 256 — 로고 윗변 = 위 11mm
        c = Ctx(b, f); c.js("(o)=>{SETTINGS.orient=o; syncControls(); applyLook(); render(); applyScale();}", o)
        top[o] = c.js("()=>{const s=document.querySelector('.sheet'),l=s.querySelector('.noren .logo'); return +((l.getBoundingClientRect().top-s.getBoundingClientRect().top)/96*25.4).toFixed(2)}")
        out['err'] += c.errs; c.close()
    out['256_logo_top_mm'] = top
    c = Ctx(b, f)                                                             # 246 — 글꼴이 도착할 때마다(loadingdone) 다시 잰다
    out['246_loadingdone'] = c.js("async()=>{let n=0; const o=applyScale; applyScale=function(){n++; return o.apply(this, arguments)}; document.fonts.dispatchEvent(new Event('loadingdone')); await new Promise(r=>setTimeout(r,300)); applyScale=o; return n}")
    out['err'] += c.errs; c.close()
    return out

# ───────────────────────── 47. 첫 화면 · 빈 메뉴판(264 · 265번). 검사 파일에 설정 한 줄("startScreen": true)을 넣은 사본을 연다
def t47(b, f):
    from PIL import Image, ImageDraw
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'start_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    def mk(im): buf = io.BytesIO(); im.save(buf, 'PNG'); return {'name': 'logo.png', 'mimeType': 'image/png', 'buffer': buf.getvalue()}
    im = Image.new('RGB', (400, 300), 'white'); ImageDraw.Draw(im).ellipse((120, 60, 280, 240), fill='black'); png = mk(im)          # 바탕이 분명한 로고
    am = Image.new('RGB', (400, 300), 'white'); dd = ImageDraw.Draw(am); dd.rectangle((200, 0, 400, 300), fill='black'); dd.ellipse((140, 70, 260, 230), fill=(128, 128, 128)); png_amb = mk(am)   # 가장자리가 반반 — 애매
    out = {}
    c = Ctx(b, 'start_' + f, dl=True); pg = c.pg
    out['open_first'] = c.js("()=>[document.querySelector('#start').open, getComputedStyle(document.querySelector('#st-closerow')).display, document.querySelector('#st-photo').disabled]")
    pg.keyboard.press('Escape'); pg.wait_for_timeout(150); out['esc_stays'] = c.js("()=>document.querySelector('#start').open")
    pg.mouse.click(8, 8); pg.wait_for_timeout(150); out['backdrop_stays'] = c.js("()=>document.querySelector('#start').open")   # 266번 — 바깥 누르기
    pg.click('#st-blank'); pg.fill('#st-shop', '시험 가게'); pg.wait_for_timeout(100)
    out['top_follows'] = [pg.input_value('#st-top'), pg.inner_text('#st-prev'), pg.query_selector('#st-fname') is None]   # 293번 — 「저장하면 ○○.html」 줄은 걷었다(배포 주소는 자동 저장이라 사실과 달랐다)
    pg.click('#st-seg button[data-m="img"]')
    def up(f):   # 268번 — 점선 상자를 실제로 눌러 파일 창에 넣는다(앱의 받는 곳을 그대로 거친다. 흉내 낸 받는 곳이 낡아 헛실패가 났다)
        with pg.expect_file_chooser() as fc: pg.click('#st-up')
        fc.value.set_files(f); pg.wait_for_timeout(600)
    up(png)
    m1 = c.js("()=>document.querySelector('#st-prev .st-mask')?.style.getPropertyValue('--src').length || 0")
    t_clear = c.js("()=>document.querySelectorAll('#st-tiles .st-exb').length")   # 268번 — 분명한 로고에는 두 모양을 안 띄운다
    up(png_amb)
    t_amb = c.js("()=>document.querySelectorAll('#st-tiles .st-exb').length"); m1 = c.js("()=>document.querySelector('#st-prev .st-mask')?.style.getPropertyValue('--src').length || 0")
    pg.click('#st-tiles .st-exb.no'); pg.wait_for_timeout(400)   # 애매할 때만 묻는다 — 알프스 예시 ✗ 를 누른다
    m2 = c.js("()=>document.querySelector('#st-prev .st-mask')?.style.getPropertyValue('--src').length || 0")
    out['logo_mask_invert'] = [m1 > 0, m1 != m2, t_clear == 0, t_amb == 2]
    pg.click('#st-go'); pg.wait_for_timeout(700)
    out['guide_up'] = c.js("()=>!!document.querySelector('.gd-tip')"); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)   # 269번부터 시작하면 가이드가 뜬다 — 닫고 간다
    out['started'] = c.js("()=>({open:document.querySelector('#start').open, editing:document.body.classList.contains('editing'), sheets:document.querySelectorAll('.sheet').length, title:document.title, flag:SETTINGS.startScreen===undefined, undo:undoStack.length, font:SETTINGS.font, seal:P(0).seal, art:P(0).art, logo:!!SETTINGS.logoImg, focus:document.activeElement?.dataset?.path||''})")
    with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
    out['save_name'] = d.value.suggested_filename; d.value.save_as(D + 'res/start_saved_' + f)
    out['err'] = list(c.errs); c.close()
    c = Ctx(b, 'res/start_saved_' + f); pg = c.pg
    out['saved_opens_direct'] = not c.js("()=>document.querySelector('#start').open")
    pg.click('#b-edit'); pg.wait_for_timeout(200); pg.click('#b-file'); pg.click('#b-start')   # 283번. [파일 ▾] 안; pg.wait_for_timeout(200)
    out['reopen_close'] = c.js("()=>!document.querySelector('#st-closerow').hidden")
    pg.click('#st-blank'); pg.wait_for_timeout(150); pg.mouse.click(8, 8); pg.wait_for_timeout(150)
    out['setup_backdrop_stays'] = c.js("()=>document.querySelector('#start').open && !document.querySelector('#st-setup').hidden")   # 266번 — 다시 연 정하기 창도
    pg.click('#st-back'); pg.wait_for_timeout(100)
    pg.click('#st-alps'); pg.wait_for_timeout(500)
    out['alps_no_guide'] = c.js("()=>!document.querySelector('.gd-tip')")   # 270번 — 가이드를 본 사람은 길을 다시 골라도 안 뜬다
    out['alps'] = c.js("()=>[document.querySelectorAll('.sheet').length, MENU.brand.shop, !document.querySelector('#undo-btn').hidden]")
    pg.click('#undo-btn'); pg.wait_for_timeout(400)
    out['undo_back'] = c.js("()=>[MENU.brand.shop, document.querySelectorAll('.sheet').length]")
    out['err'] += c.errs; c.close()
    c = Ctx(b, 'start_' + f, dl=True); pg = c.pg                               # 265 — 상호명을 비우면 "메뉴판"
    pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_timeout(700); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
    out['noname'] = [c.js("()=>document.title"), d.value.suggested_filename]
    out['err'] += c.errs; c.close()
    return out

# ───────────────────────── 48. 글자가 바뀌는 막대 단추의 폭(규칙 I · 267번). 263번이 "편집"↔"편집 끝" 폭을 망가뜨렸는데 t25(종이 튐)는 못 잡았다
def t48(b, f):
    c = Ctx(b, f); w = lambda: c.js("()=>[...document.querySelectorAll('.bar button')].map(e=>[e.id, +e.getBoundingClientRect().width.toFixed(1)])")
    a = w(); c.pg.click('#b-edit'); c.pg.wait_for_timeout(200); e = w()
    h = c.js("()=>[[...document.querySelectorAll('#btpick button')].map(b=>Math.round(b.getBoundingClientRect().height)), [...document.querySelectorAll('.wfrow button')].map(b=>Math.round(b.getBoundingClientRect().height))]")   # 268번 — 병 단추 · ▲▼ 높이
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200); z = w()
    out = {'idle': a, 'edit': e, 'back': z, 'heights': h, 'err': c.errs}; c.close(); return out

# ───────────────────────── 49. 가이드(269번) — 첫 화면에서 길을 고른 직후에만 뜨고, 단계마다 짚는 것이 화면에 있고 보이는지
def t49(b, f):
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'g_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    out = {'steps': []}
    c = Ctx(b, f); c.pg.wait_for_timeout(600); out['plain_open'] = c.js("()=>document.querySelectorAll('.gd-tip').length"); c.close()
    c = Ctx(b, 'g_' + f); pg = c.pg
    pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_timeout(900)
    for i in range(5):
        out['steps'].append(c.js("""()=>{const h=document.querySelector('.gd-hole'),t=document.querySelector('.gd-tip'); if(!h||!t) return null;
          const a=h.getBoundingClientRect(),q=t.getBoundingClientRect(); const see=[...document.querySelectorAll('.tohere .rowtools, .addhere > .addrow')].some(e=>getComputedStyle(e).visibility==='visible');
          return {h:t.querySelector('h4').textContent, hole:[Math.round(a.width),Math.round(a.height)], cover:!(q.right<a.left||q.left>a.right||q.bottom<a.top||q.top>a.bottom), inview:q.left>=0&&q.right<=innerWidth&&q.top>=0&&q.bottom<=innerHeight, tools:see}}"""))
        pg.click('.gd-tip button.fill'); pg.wait_for_timeout(300)   # 291번 — [다음]도 채운 단추
    out['done'] = c.js("()=>[SETTINGS.guideDone === true, document.querySelectorAll('.gd-tip,.gd-hole,.gd-block').length]")
    pg.click('#b-help'); pg.wait_for_timeout(200); pg.click('#help-guide'); pg.wait_for_timeout(500)
    out['again'] = c.js("()=>!!document.querySelector('.gd-tip')"); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
    out['esc'] = c.js("()=>document.querySelectorAll('.gd-tip').length"); out['err'] = c.errs; c.close()
    return out

# ───────────────────────── 50. 되돌리기 · 다시 하기(271번) — 막대 단추의 흐림과 Ctrl+Z · Ctrl+Y
def t50(b, f):
    c = Ctx(b, f); pg = c.pg; pg.click('#b-edit'); pg.wait_for_timeout(300)
    st = lambda: c.js("()=>[document.querySelector('#b-undo').disabled, document.querySelector('#b-redo').disabled, MENU.sheets[0][0][0].items.length]")
    out = {'start': st()}
    c.js("()=>{MENU.sheets[0][0][0].items.pop(); render(); touch();}"); out['edited'] = st()
    pg.click('#b-undo'); pg.wait_for_timeout(250); out['undo'] = st()
    pg.click('#b-redo'); pg.wait_for_timeout(250); out['redo'] = st()
    pg.keyboard.press('Control+z'); pg.wait_for_timeout(250); out['ctrlz'] = st()
    pg.keyboard.press('Control+y'); pg.wait_for_timeout(250); out['ctrly'] = st()
    pg.keyboard.press('Control+z'); pg.wait_for_timeout(250); c.js("()=>{MENU.sheets[0][0][0].name='시험'; render(); touch();}"); out['newedit'] = st()
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 51. 모양만 바꾸는 손잡이(273번) — 값마다 종이 위 칸의 자리 · 크기가 기본과 0px. 이것이 통과하면 넘침 · 인쇄 검사를 조합마다 돌리지 않아도 된다
RECT51 = """()=>[...document.querySelectorAll('.sheet section, .sheet .row, .sheet .sec-head, .sheet .foot, .sheet .noren')].map(e=>{const r=e.getBoundingClientRect(); return [Math.round(r.left*10)/10,Math.round(r.top*10)/10,Math.round(r.width*10)/10,Math.round(r.height*10)/10]})"""
def t51(b, f):
    c = Ctx(b, f); base = c.js(RECT51); out = {'n': len(base), 'diff': {}}
    knobs = c.js("()=>({paper:[...document.querySelectorAll('#f-paper option')].map(o=>o.value), sec:[...document.querySelectorAll('#f-secstyle option')].map(o=>o.value), leader:[...document.querySelectorAll('#f-leader option')].map(o=>o.value), theme:Object.keys(THEMES)})")
    for k, vals in knobs.items():
        for v in vals:
            c.js("([k,v])=>{ if(k==='paper') SETTINGS.paper=v; if(k==='sec') SETTINGS.secStyle=v; if(k==='leader'){ if(v==='none') SETTINGS.showDots=false; else { delete SETTINGS.showDots; SETTINGS.leader=v; } } if(k==='theme') SETTINGS.theme=v; applyLook(); render(); }", [k, v])
            now = c.js(RECT51); d = max((abs(a - q) for x, y in zip(base, now) for a, q in zip(x, y)), default=0) if len(now) == len(base) else 999
            out['diff'][k + '=' + v] = d
            c.js("()=>{ delete SETTINGS.paper; delete SETTINGS.secStyle; delete SETTINGS.leader; delete SETTINGS.showDots; SETTINGS.theme='night'; applyLook(); render(); }")
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 52. 추천 조합(273번) — 꾸미기 창에서 맞추면 PRESETS 값이 걸리고, 글자 크기 · 내용 · 맨 위는 그대로, 되돌리기로 돌아온다
def t52(b, f):
    c = Ctx(b, f); pg = c.pg; pg.click('#b-edit'); pg.wait_for_timeout(300)
    snap = "()=>JSON.stringify({sz:P(0).scale, top:MENU.brand.top||'', tm:SETTINGS.topMode||'', items:MENU.sheets.map(s=>s.map(col=>col.map(x=>(x.items||[]).length)))})"
    before = c.js(snap); st = c.js("()=>JSON.stringify({f:SETTINGS.font,t:SETTINGS.theme,m:SETTINGS.mark})"); out = {'apply': {}}
    keys = c.js("()=>Object.keys(PRESETS).filter(k=>!PRESETS[k].hidden)")   # 285번. 숨긴 조합(basic = 내 조합의 시작 모양)은 타일이 없다
    for k in keys:
        c.js("()=>document.querySelector('#f-presets').scrollIntoView()"); pg.click(f'#f-presets [data-p="{k}"]'); pg.wait_for_timeout(200)   # 284번. 목록 → 타일
        out['apply'][k] = c.js("(k)=>{const q=PRESETS[k]; return [SETTINGS.font===q.font, SETTINGS.theme===q.theme, (SETTINGS.paper||'grain')===q.paper, (SETTINGS.secStyle||'line')===q.sec, SETTINGS.mark===q.mark, P(0).noren===q.noren, P(0).seal!=='word' && P(0).seal!=='rword', (document.querySelector('#f-presets .pl-tile.on')||{}).dataset?.p===k]}", k)
    out['same_size_content'] = c.js(snap) == before
    for _ in keys: pg.keyboard.press('Control+z'); pg.wait_for_timeout(120)
    out['undo_back'] = c.js("()=>JSON.stringify({f:SETTINGS.font,t:SETTINGS.theme,m:SETTINGS.mark})") == st
    out['err'] = c.errs; c.close(); return out

# ───────────────────────── 53. 글자 추천 표시(274번) — 가장 긴 표시를 모든 줄에 붙여도 줄 높이가 그대로, 각주의 보통 낱말은 안 바뀐다, 길이 제한
def t53(b, f):
    c = Ctx(b, f)
    h0 = c.js("()=>[...document.querySelectorAll('.sheet .row')].map(r=>Math.round(r.getBoundingClientRect().height*10)/10)")
    c.js("()=>{ MENU.feet[0].notes=['추천 메뉴는 매일 바뀝니다']; applyMark('추천'); applyMark('great'); MENU.sheets.forEach(sh=>sh.forEach(col=>col.forEach(sec=>(sec.items||[]).forEach(it=>{ if(it.name) it.pick=true; })))); render(); applyScale(); }")
    h1 = c.js("()=>[...document.querySelectorAll('.sheet .row')].map(r=>Math.round(r.getBoundingClientRect().height*10)/10)")
    out = {'rows': len(h0), 'grew': sum(1 for a, q in zip(h0, h1) if q > a + 0.5), 'pills': c.js("()=>document.querySelectorAll('.pick.tx').length"),
           'note': c.js("()=>MENU.feet[0].notes[0]"), 'over': c.js("()=>[...Array(MENU.sheets.length).keys()].map(i=>overWhy(i))"),
           'limit': c.js("()=>[markOk('강력추천'), markOk('강력추천요'), markOk('great!'), markOk('greatest')]"), 'err': c.errs}
    out['over_match'] = c.js("""()=>[...document.querySelectorAll('.sheet')].every((sh,i)=>{ const lim=sh.getBoundingClientRect().bottom - parseFloat(getComputedStyle(sh).paddingBottom);
        const real=[...sh.querySelectorAll('.row')].some(r=>r.getBoundingClientRect().bottom > lim + 1); return real === !!overWhy(i); })""")
    c.close(); return out

# 283번. [파일로 저장] · [새로 만들기]는 위쪽 막대 [파일 ▾] 안 — 누르기 전에 메뉴를 연다
# ───────────────────────── 54. 사진으로 시작(275번) — 붙여 넣기 길과 제미나이 길(인터넷 대신 가짜 답). 요청 모양 · 키는 브라우저에만 · 확인 화면 · 노란 칸 · 시작 뒤 메뉴
ANS54 = "[식사]\n단호박 크림 파스타 | 14000\n고사리 들깨 크림 파스타? | 14000\n오징어 페코리노 파스타 | 14,000원\n[안주]\n生 연어구이 | 10000\n국물바지락 | 11000?\n피망 | 시가\n[음료]\n콜라 · 사이다 | 3000"
def t54(b, f):
    from PIL import Image, ImageDraw
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    im = Image.new('RGB', (600, 800), 'white'); ImageDraw.Draw(im).rectangle((30, 30, 570, 770), outline='black', width=4)
    buf = io.BytesIO(); im.save(buf, 'PNG'); png = {'name': 'menu.png', 'mimeType': 'image/png', 'buffer': buf.getvalue()}
    out = {}
    c = Ctx(b, 'p_' + f); pg = c.pg
    # 288번 — 다른 앱 길은 바로 읽기가 안 될 때만 나온다. 서버가 꺼 둔 경우로 연다
    pg.route('**/api/read', lambda r: r.fulfill(status=200, content_type='application/json', body='{"enabled":false}'))
    pg.click('#st-photo'); pg.wait_for_timeout(400); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', ANS54); pg.click('#st-appgo'); pg.wait_for_timeout(250)
    out['check'] = c.js("()=>[!document.querySelector('#st-check').hidden, document.querySelectorAll('#st-ctab input').length, document.querySelectorAll('#st-ctab input.un').length]")
    pg.click('#st-check-go'); pg.wait_for_timeout(150); pg.click('#st-go'); pg.wait_for_timeout(700); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    out['menu'] = c.js("()=>MENU.sheets[0].map(col=>col.map(s=>[s.name, s.items.map(i=>i.name+'='+i.price)]))")
    out['err'] = list(c.errs); c.close()
    c = Ctx(b, 'p_' + f); pg = c.pg; reqs = []
    def ok_route(r):   # 276번 — 버셀 서버 함수(파일로 열었으니 배포 주소)를 가로챈다. 278번 — 켜져 있나 묻는 GET 은 켜짐으로
        if r.request.method == 'GET': r.fulfill(status=200, content_type='application/json', body='{"enabled":true}'); return
        reqs.append({'url': r.request.url, 'body': r.request.post_data or '', 'hdr': dict(r.request.headers)})
        r.fulfill(status=200, content_type='application/json', body=json.dumps({'text': '가게: 솔밭식당\n' + ANS54, 'model': 'test'}))   # 290번 — 가게 이름 줄
    pg.route('**/api/read', ok_route)
    pg.click('#st-photo'); pg.wait_for_timeout(300)
    out['other'] = [c.js("()=>document.querySelector('#st-other').hidden")]   # 288번 — 바로 읽기가 되면 한 길만
    with pg.expect_file_chooser() as fc: pg.click('#st-pic')
    fc.value.set_files(png); pg.wait_for_timeout(500)
    out['no_key_box'] = c.js("()=>!document.querySelector('#st-key')")
    pg.click('#st-gemgo'); pg.wait_for_timeout(700)
    q = reqs[0] if reqs else {'url': '', 'body': '', 'hdr': {}}
    bd = json.loads(q['body'] or '{}')
    out['gem'] = [q['url'].endswith('/api/read'), (bd.get('image') or '').startswith('data:image/jpeg;base64,'), set(bd) == {'image'}, not any(k.lower() == 'x-goog-api-key' for k in q['hdr']), c.js("()=>!document.querySelector('#st-check').hidden"), c.js("()=>document.querySelector('#st-cshop').value") == '솔밭식당']   # 290번 — 읽은 가게 이름이 확인 화면에
    pg.unroute('**/api/read')
    pg.route('**/api/read', lambda r: r.fulfill(status=429, content_type='application/json', body='{"error":"limit","code":"limit"}'))
    pg.click('#st-check-back'); pg.click('#st-gemgo'); pg.wait_for_timeout(500)
    out['limit_msg'] = '한도' in c.js("()=>document.querySelector('#st-gemmsg').textContent")
    out['other'].append(not c.js("()=>document.querySelector('#st-other').hidden"))   # 288번 — 한 번 실패하면 다른 앱 길이 나온다
    out['err'] += c.errs; c.close()
    c = Ctx(b, 'p_' + f); pg = c.pg   # 278번 — 서버에서 꺼 두면(READ_ENABLED=off) 사진 창을 열 때 알아채 흐리게
    pg.route('**/api/read', lambda r: r.fulfill(status=200, content_type='application/json', body='{"enabled":false}'))
    pg.click('#st-photo'); pg.wait_for_timeout(500)
    out['off'] = [c.js("()=>document.querySelector('#st-way [data-w=\"gem\"]').disabled"), c.js("()=>document.querySelector('#st-gemgo').disabled"), c.js("()=>stWay") == 'app', '쉬고' in c.js("()=>document.querySelector('#st-gemmsg').textContent")]
    out['err'] += c.errs; c.close()
    # 276번 — 메뉴판의 요청 글(READ_PROMPT)과 서버 함수의 요청 글(PROMPT)이 같은가. 서버 함수 파일을 찾으면 본다
    here = os.path.dirname(os.path.abspath(__file__)); cand = [os.path.join(here, 'api', 'read.js'), os.path.join(here, '..', 'api', 'read.js')]
    fn = next((p for p in cand if os.path.exists(p)), None); out['prompt_same'] = None
    if fn:
        def arr(t, head):
            i = t.find(head); j = t.find('].join', i); return json.loads(t[i + len(head):j + 1]) if i >= 0 else None
        out['prompt_same'] = arr(src, 'const READ_PROMPT = ') == arr(open(fn, encoding='utf-8').read(), 'const PROMPT = ')
    return out

# ───────────────────────── 55. 자동 저장 · 불러오기(277번) — 이 폴더를 작은 웹 서버로 띄워 버셀 주소처럼(http) 연다
def t55(b, f):
    import threading, http.server, socketserver, functools
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'w_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=D)); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = {}
    try:
        ctx = b.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True); pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'http://127.0.0.1:{port}/w_{f}'); pg.wait_for_timeout(400)
        out['first'] = [pg.evaluate("document.querySelector('#start').open"), pg.evaluate("localStorage.getItem('menupan-auto')") is None]
        pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_timeout(800); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
        pg.evaluate("()=>{MENU.sheets[0][0][0].name='자동 저장 시험'; render(); touch();}"); pg.wait_for_timeout(900)
        out['saved'] = ['자동 저장됨' in pg.inner_text('#autost'), '자동 저장 시험' in (pg.evaluate("localStorage.getItem('menupan-auto')") or ''), not pg.evaluate("getComputedStyle(document.querySelector('#b-save')).backgroundColor").startswith('rgb(239')]
        pg.reload(); pg.wait_for_timeout(600)
        out['reopen'] = [not pg.evaluate("document.querySelector('#start').open"), pg.evaluate("MENU.sheets[0][0][0].name") == '자동 저장 시험', '지난번' in pg.evaluate("document.querySelector('#undo')?.innerText||''")]
        with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
        sv = open(d.value.path(), encoding='utf-8').read(); mm = re.search(r'id="autost"[^>]*>([^<]*)</span>', sv)
        out['file_clean'] = [' web' not in sv.split('<body')[1][:80], bool(mm) and mm.group(1).strip() == '']   # 칸 안의 글자만 — 옆 주석을 세지 않는다
        pg.set_input_files('#st-hfile', D + f); pg.wait_for_timeout(1200)
        imp = [pg.evaluate("MENU.sheets.length"), not pg.evaluate("document.querySelector('#start').open"), '불러왔습니다' in pg.evaluate("document.querySelector('#undo')?.innerText||''")]
        pg.click('#undo-btn'); pg.wait_for_timeout(1200)
        out['import'] = imp + [pg.evaluate("MENU.sheets[0][0][0].name") == '자동 저장 시험']
        out['err'] = errs; ctx.close()
        c = Ctx(b, 'w_' + f); c.pg.click('#st-blank'); c.pg.click('#st-go'); c.pg.wait_for_timeout(700); c.pg.keyboard.press('Escape')
        c.js("()=>{MENU.sheets[0][0][0].name='파일 쪽'; render(); touch();}"); c.pg.wait_for_timeout(800)
        out['file'] = [c.pg.inner_text('#autost') == '자동 저장 안 됨', c.js("()=>localStorage.getItem('menupan-auto')") is None, c.js("()=>document.body.classList.contains('unsaved')")]
        out['err'] += c.errs; c.close()
    finally:
        srv.shutdown()
    return out

def near(x, y, t): return abs(x - y) <= t
def judge(t, r):
    """(통과?, 한 줄 요약). None 이면 사람이 볼 것"""
    try:
        if t == 't02': ok = not any(r[k] for k in r if k.startswith(('font_seal_', 'art_', 'misc_')) and not k.endswith(('_n_portrait', '_n_landscape', 'checked_portrait', 'checked_landscape'))) and not r['err']; return ok, f"넘침·가림 {'0' if ok else '있음'} (글꼴×도장 {r['font_seal_n_portrait']}×2)"
        if t == 't03': return None, '상단 모양 그림을 눈으로: _check/res/noren_*.png'
        if t == 't04': ok = r['reach'][0] == r['reach'][1] and all(v is True or (isinstance(v, list) and v[1]) for v in r['fill'].values()) and all(r['act'].values()); return (True if ok else None), f"도달 {r['reach'][0]}/{r['reach'][1]} · 못 닿은 것 {r['unreached_kinds']}(막대 근처면 가운데로 옮겨 다시) · 빈 칸 {r['fill']} · 동작 {r['act']}"
        if t == 't04p': bad = {k: v for k, v in r.items() if not k.endswith('_err') and k != '_sec' and v}; return not bad and not any(r[k] for k in r if k.endswith('_err')), f"가격을 못 누르는 이름 길이 {bad or '없음'}(8 ~ 44자 · 세로 2단 · 가로 2단 · 가로 4단)"
        if t == 't31v': bad = [x[:3] for x in r['cases'] if not x[3]]; return not bad, f"빈 용량 상자 눌러 입력 {len(r['cases']) - len(bad)}/{len(r['cases'])} {bad or ''}"
        if t == 't05':
            e = {k: v['edit'] for k, v in r.items() if k != '_sec' and v['edit']}; p = max(v['prev'] for k, v in r.items() if k != '_sec')
            if p: return False, f"미리보기 대 완성본 {p}px — 예외 없이 0 이어야 한다"
            return not e, f"미리보기 대 완성본 0px · 편집 대 완성본(점선 제외) {e or 0} — 238번 뒤로 예외 없이 0 이어야 한다"
        if t == 't06': return r['worst'] == 0, f"들썩임 {r['worst']}px ({r['hovers']}곳)"
        if t == 't07':
            m = {'portrait': (14, 14, 11.6), 'landscape': (13, 13, 11.3)}; bad = []
            for o in m:
                for pg in r[o]['margins']:
                    if not all(near(x, y, 0.4) for x, y in zip(pg, m[o])): bad.append((o, pg))
                if not r[o]['multicol']: bad.append((o, '다단 아님'))
                if max(r[o]['edit_px_diff'] or [0]) > 100: bad.append((o, '편집 중 인쇄 화소', r[o]['edit_px_diff']))
            for L, v in r['long'].items():
                if not (v['priceIn'] and v['prevIn'] and all(x <= v['colRightMm'] + 0.5 for x in v['pdfPriceXmm'])): bad.append(('긴 이름', L))
            return not bad, f"여백 세로 {r['portrait']['margins'][0]} · 가로 {r['landscape']['margins'][0]} · 편집 중 인쇄 {r['portrait']['edit_px_diff']}/{r['landscape']['edit_px_diff']} {bad or ''}"
        if t == 't08':
            bad = [(k, n) for k, v in r.items() if k != '_sec' for n, x in v['r'].items() if x.get('notOpen') or not (x['foot'] and x['hit'] and x['over'] == 0 and x['shadeOk'] and x['detVis'] in (None, True) and (x['h3'] or n.endswith('-open')))] + [(k, 'err') for k, v in r.items() if k != '_sec' and v['err']]
            return not bad, f"창 14구성 문제 {len(bad)} {bad[:4]}"
        if t == 't10':
            tl, wd = r['tall'], r['wide']; ok = ('tall' in tl['why'] and '잘립니다' in tl['warn'][2] and 'wide' in wd['why'] and '잘립니다' not in wd['warn'][2] and '[＋ 장 추가]' not in tl['toast'] + tl['warn'][3])
            return ok, f"세로: {tl['warn'][1]} / 가로: {wd['warn'][1]}"
        if t == 't11': return all(x[1] for x in r['steps']), str(r['steps'])
        if t == 't14': ok = r['roundtrip_same'] and r['roundtrip_pos'] and not r['legacy_saved_oldkeys'] and not r['legacy_saved_toplevel_pagekeys'] and not (r['rt_err'] or r['legacy_err']) and r['legacy_open']['ns'] == 0.9; return ok, f"왕복 {r['roundtrip_same']} · 옛 저장본 상단 {r['legacy_open']['ns']}(낮게 → 0.9) · 옛 키 {r['legacy_saved_oldkeys']}"
        if t == 't15': return None, f"참고 수(기준과 대조 · 사용법에는 수를 안 적는다, 258번): 영문 알림 '{r['bilingual_toast'][:40]}…' · pt {r['pt']} · 원산지 {r['origin_push']}px · 와인 {r['wine']} · 창 밀림 {r['panel_push'][:5]}"
        if t == 't16': mv = [v['maxmove'] for k, v in r.items() if k != '_sec']; return all(x == 0 for x in mv), f"줌 뒤 [편집] 이동 {mv}"
        if t == 't17': ok = r['restore'][0] == r['restore'][1] and r['focus'] and r['accum'][1] == 0; return ok, str({k: r[k] for k in ('restore', 'focus', 'accum')})
        if t == 't21': vals = [json.dumps(r[k]) for k in r if k.isdigit()]; ok = len(set(vals)) == 1 and r['pdf640'][0][2] >= 10; return ok, f"창 폭별 배율 {set(vals)} · 640px 인쇄 아래 {r['pdf640'][0][2]}mm"
        if t == 't23':
            clip = all(x == 0 for v in r['clip'].values() for x in v); a4 = all(near(v['dims'][0][0], 793.7, 0.5) and v['lines_same'] and not v['err'] for v in r['a4'].values())
            nar = r['narrow']; fits = {json.dumps(v['fit_True']) for v in nar.values()}
            pan = all(v['panel']['inView'] and not v['panel']['overBar'] and v['left0_True'] >= 0 and v['rightEnd_True'] >= -0.5 for v in nar.values())
            return clip and a4 and pan and len(fits) == 1, f"잘림 {'0' if clip else '있음'} · A4 고정 {a4} · 좁은 화면 {pan} · 가로 스크롤(끔/켬) " + ' · '.join(f"{w}:{v['hscroll_False']}/{v['hscroll_True']}" for w, v in nar.items())
        if t == 't24': return len(set(r['sizes'])) == 1, f"흔든 뒤 세 번 저장 {r['sizes']}"
        if t == 't25': dy = max(v['dy'] for k, v in r.items() if k != '_sec'); bad = [k for k, v in r.items() if k != '_sec' and (v['dxBad'] or v['err'])]; return dy == 0 and not bad, f"세로 튐 최대 {dy} · 가로 어중간한 이동 {bad}"
        if t == 't27': ok = all(r['plusGone'].values()) and not r['null'] and not r['null_final'] and r['secnote'][1] == 4 and r['notes'][1] == 8 and r['hours'][1] == 4 and r['bottles'][1] == 8; return ok, f"상한 {[r[k][1] for k in ('secnote', 'notes', 'hours', 'bottles')]} · ＋ 사라짐 {r['plusGone']}"
        if t == 't28': return r['allOk'], f"{len(r['steps'])}단계"
        if t == 't30': fc = r['first_char']; ok = r['prev_vs_final'] == 0 and r['otherCol_move'] == 0 and r['blankRowHeights']['same_as_preview'] and all(isinstance(v, dict) and v['move'] == 0 and v['typed'].endswith('A') for v in fc.values()); return ok, f"미리보기=완성본 {r['prev_vs_final']} · 옆 단 {r['otherCol_move']} · 빈 줄 높이 {r['blankRowHeights']} · 첫 글자 {fc}"
        if t == 't32': ok = all(v['dotSpreadFinal'] <= 0.02 and v['dotSpreadPrev'] <= 0.02 and v['price_ed_vs_prev'] == 0 and v['price_fin_vs_prev'] == 0 for k, v in r.items() if k != '_sec'); return ok, '점선 끝 ≤0.02px · 가격 자리 0'
        if t == 't35': return not r['cut'], f"잘린 select {r['cut']}"
        if t == 't36': return None, '그림 코드 해시 — 기준과 같으면 그림을 안 건드린 것(참고 사진 대조는 사진이 있어야 한다)'
        if t == 't37': return r['nbad'] == 0, f"병 잉크 바닥 {r['n'] - r['nbad']}/{r['n']} 1px 이내 · 최대 {r['worst']}"
        if t == 't38': vals = {k: v for k, v in r.items() if k != '_sec'}; ok = all(v[0] == 190 and v[1] <= 1 for v in vals.values()); return ok, f"잉크 바닥 · 호일 {vals}"
        if t == 't39': p = r['pages']; ok = not r['err'] and r['S'] == {'font': 'gungseo', 'theme': 'night', 'mark': '★', 'pageno': 'of', 'sec': 'left', 'wine': 'left'} and all(x[3] == 1 and x[4] == 0.8 for x in p) and r['ui']['font'] == 'gungseo'; return ok, f"복구 {r['S']} · 장 {p}"
        if t == 't40': return r['allSame'], '도장 9가지 동작 고정'
        if t == 't41': ok = all(len(x['secGaps']) <= 1 for x in r['sheets']); return ok, f"칸 아래 구멍 {[x['holes'] for x in r['sheets']]} · 분류 틈 {[x['secGaps'] for x in r['sheets']]}"
        if t == 't42': ok = all(v['edit'] == 0 and v['prev'] == 0 for k, v in r.items() if k != '_sec') and all(x == 0 for x in r['center']['centerMarginDiff']); return ok, '정렬 셋 · 세 모드 0.0px'
        if t == 't43': ok = all(r[k]['newlines'] == 4 for k in ('sec', 'wine', 'label')) and all(x.count('\n') == 4 for x in r['saved']); return ok, '두 줄 쓰기 · 제한 없음 · 저장 보존'
        if t == 't44':
            dark = lambda h: sum(int(h[i:i+2], 16) for i in (1, 3, 5)) < 60
            sw = r['swatch']; ok = (r['copy'] and all(v[0] == v[1] and not dark(v[0]) for v in sw.values()) and r['drag'][0] and r['drag'][1] == 0
                  and r['drag'][2] == '#203079' and r['drag'][3] == 0 and r['live'] == [0, 4, True, False] and r['wineprice'] == '' and r['nstep'] == 0.84 and r['saveadd'] == [1, True] and not r['err'])
            return ok, f"복사 {r['copy']} · 병 색 상자 {sw} · 끄는 중 {r['drag']} · 끄는 중 다시 그리기 · 레드 병 카드 · 바뀜 · 다른 병도 바뀜 {r['live']} · 빈 와인 카드 가격 '{r['wineprice']}' · 상단 걸음 {r['nstep']} · 저장 뒤 병 추가 {r['saveadd']}"
        if t == 't45':
            w = r['worst']; bad = {k: v for k, v in w.items() if v[0] < 5.0}
            sh = r['show']; W = 'rgb(255, 255, 255)'; H = 'rgba(255, 255, 255, 0.35)'   # 243번
            okv = all(all(x[0] == 'block' and near(x[1], 4.0, 0.3) for x in m) for o in sh.values() for m in o.values()) \
                and all(all(x[2] == H for x in o['edit']) and all(x[2] == W for x in o['idle'] + o['preview'] + o['editPrint']) for o in sh.values())
            mins = {k: v[0] for k, v in w.items()}
            return not bad and okv and not (r['err_portrait'] or r['err_landscape']), f"가장자리 최소 {mins} {bad or ''} · 흰 테두리 4mm · 편집만 반투명 {okv}"
        if t == 't55':
            ok = all(r['first']) and all(r['saved']) and all(r['reopen']) and all(r['file_clean']) and r['import'][:1] == [2] and all(r['import'][1:]) and all(r['file']) and not r['err']
            return ok, f"웹 처음 [첫 화면, 저장본 없음] {r['first']} · 고친 뒤 [상태, 저장본, 불 꺼짐] {r['saved']} · 다시 열기 [첫 화면 없음, 이어짐, 알림] {r['reopen']} · 받은 파일에 [웹 표시 없음, 상태 글자 없음] {r['file_clean']} · 불러오기 [장, 첫 화면 없음, 알림, 되돌리기] {r['import']} · 컴퓨터 파일 [자동 저장 안 됨, 저장본 안 씀, 불] {r['file']} · 오류 {r['err'][:2]}"
        if t == 't54':
            want = [[['식사', ['단호박 크림 파스타=14000', '고사리 들깨 크림 파스타=14000', '오징어 페코리노 파스타=14000']]], [['안주', ['生 연어구이=10000', '국물바지락=11000', '피망=시가']], ['음료', ['콜라 · 사이다=3000']]]]
            ok = r['check'] == [True, 17, 2] and r['menu'] == want and all(r['gem']) and r['no_key_box'] and r['limit_msg'] and all(r.get('off', [False])) and r.get('prompt_same') is not False and r.get('other') == [True, True] and not r['err']
            return ok, f"다른 앱 길 [처음엔 숨김, 실패 뒤 보임] {r.get('other')} · 붙여 넣기 → 확인 화면 [보임, 칸, 노란 칸] {r['check']} · 시작 뒤 메뉴 맞음 {r['menu'] == want} · 서버 함수 [주소, 사진, 사진만 보냄, 키 머리글 없음, 확인 화면, 가게 이름] {r['gem']} · 키 칸 없음 {r['no_key_box']} · 한도 안내 {r['limit_msg']} · 두 요청 글 같음 {r.get('prompt_same')} · 꺼 두면 [흐림, 읽기 흐림, 다른 앱으로, 안내] {r.get('off')} · 오류 {r['err'][:2]}"
        if t == 't51':
            bad = {k: v for k, v in r['diff'].items() if v > 0}
            return not bad and not r['err'] and len(r['diff']) > 0, f"칸 {r['n']} · 값 {len(r['diff'])}가지 · 자리가 바뀐 값 {bad or '없음'}"
        if t == 't52':
            bad = {k: v for k, v in r['apply'].items() if not all(v)}
            return not bad and r['same_size_content'] and r['undo_back'] and not r['err'], f"조합 {list(r['apply'])} · 값이 안 맞은 조합 {bad or '없음'} · 크기 · 내용 그대로 {r['same_size_content']} · 되돌리기 {r['undo_back']}"
        if t == 't53':
            # 글자 표시는 자리를 먹어 긴 이름이 두 줄이 될 수 있다(9장 6번 — 넘침은 붉은 띠가 받는다). 그래서 높아진 줄 수는 참고로만 보고, 넘침 판정이 실제 넘침과 맞는지를 본다
            ok = r['pills'] > 0 and r['note'] == '추천 메뉴는 매일 바뀝니다' and r['limit'] == [True, False, True, False] and r['over_match'] and not r['err']
            return ok, f"줄 {r['rows']} 중 두 줄로 넘어간 줄 {r['grew']}(참고) · 글자 표시 {r['pills']} · 각주 {r['note']} · 넘침 판정 {r['over']} · 실제 넘침과 맞음 {r['over_match']} · 길이 제한 {r['limit']}"
        if t == 't50':
            n = r['start'][2]
            ok = (r['start'] == [True, True, n] and r['edited'] == [False, True, n - 1] and r['undo'] == [True, False, n] and r['redo'] == [False, True, n - 1]
                  and r['ctrlz'] == [True, False, n] and r['ctrly'] == [False, True, n - 1] and r['newedit'][1] is True and not r['err'])
            return ok, f"[↶흐림, ↷흐림, 줄 수] 처음 {r['start']} · 고침 {r['edited']} · ↶ {r['undo']} · ↷ {r['redo']} · Ctrl+Z {r['ctrlz']} · Ctrl+Y {r['ctrly']} · 되돌린 뒤 새로 고침 {r['newedit']} · 오류 {r['err'][:2]}"
        if t == 't49':
            st = r['steps']; ok = (r['plain_open'] == 0 and len(st) == 5 and all(x and x['hole'][0] > 10 and x['hole'][1] > 10 and not x['cover'] and x['inview'] for x in st)
                  and st[1]['tools'] and st[2]['tools'] and r['done'] == [True, 0] and r['again'] and r['esc'] == 0 and not r['err'])
            return ok, f"그냥 열면 {r['plain_open']} · 단계 {[ (x or {}).get('h','없음')[:6] for x in st]} · 짚은 칸 {[ (x or {}).get('hole') for x in st]} · 말풍선이 가림 {[ (x or {}).get('cover') for x in st]} · 도구 보임 2/3단계 {st[1].get('tools') if len(st)>1 and st[1] else None}/{st[2].get('tools') if len(st)>2 and st[2] else None} · 끝 {r['done']} · 다시 {r['again']} · Esc {r['esc']} · 오류 {r['err'][:2]}"
        if t == 't48':
            d = {k: v for k, v in r['idle']}; e = {k: v for k, v in r['edit']}; z = {k: v for k, v in r['back']}
            bad = {k: (d[k], e.get(k)) for k in d if k and k in e and d[k] and e[k] and abs(d[k] - e[k]) > 0.5}   # 폭 0 = 그 모드에서 숨은 단추(편집 도구 막대) — 뺀다
            hb, hw = r.get('heights', [[], []]); hok = bool(hb) and min(hb) > 80 and bool(hw) and max(hw) < 24   # 병은 병 모양이 보이는 높이 · ▲▼는 줄보다 작게(268번)
            return not bad and d == z and hok and not r['err'], f"편집 켜고 끌 때 폭이 바뀐 막대 단추 {bad or '없음'} · 편집 단추 {d.get('b-edit')}/{e.get('b-edit')} · 병 단추 높이 {sorted(set(hb))} · ▲▼ {sorted(set(hw))}"
        if t == 't46':
            g = r['244_foot_fixed']; top = r['256_logo_top_mm']
            ok = (near(g[0], g[1], 1) and g[2] == 'tall' and r['245_invisible'] is None and all(r[f'sec_pad_{n}'] is None for n in (10, 30, 45, 60))
                  and r['254_line_on'][0] == 'tall' and r['254_line_off'][0] is None and all(near(v, 11, 0.4) for v in top.values()) and r['246_loadingdone'] >= 1 and not r['err'])
            return ok, f"바닥 고정 {g} · 안 보이는 3px {r['245_invisible']} · 빈 자리 10·30·45·60px {[r[f'sec_pad_{n}'] for n in (10, 30, 45, 60)]} · 밑줄이 도장 +20px 켬/끔 {r['254_line_on'][0]}/{r['254_line_off'][0]} · 로고 윗변 mm {top} · 글꼴 도착 뒤 다시 재기 {r['246_loadingdone']}회"
        if t == 't47':
            s = r['started']; import re as _re
            ok = (r['open_first'] == [True, 'none', False] and   # 275번 — 사진으로 시작이 준비 중(흐림)에서 눌림으로
                  r['esc_stays'] and r.get('backdrop_stays') and r.get('setup_backdrop_stays') and r['top_follows'] == ['', '가게 이름', True] and all(r['logo_mask_invert'])
                  and not s['open'] and s['editing'] and s['sheets'] == 1 and s['title'] == '시험 가게 — 메뉴' and s['flag'] and s['undo'] == 0 and s['font'] == 'gothic'
                  and s['seal'] == 'none' and s['art'] == 'none' and s['logo'] and s['focus'] == 'sheets.0.0.0.name'
                  and _re.match(r'시험 가게-메뉴-\d{4}-\d\d-\d\d\.html$', r['save_name']) and r['saved_opens_direct'] and r['reopen_close']
                  and r['alps'] == [2, '알프스', True] and r.get('guide_up') and r.get('alps_no_guide') and r['undo_back'] == ['시험 가게', 1] and r['noname'][0] == '메뉴판' and r['noname'][1].startswith('메뉴판-') and not r['err'])
            return ok, f"첫 화면 {r['open_first']} · Esc {r['esc_stays']} · 바깥 누르기 처음/정하기 {r.get('backdrop_stays')}/{r.get('setup_backdrop_stays')} · 맨 위 글자는 상호명을 안 따라감(267번) {r['top_follows']} · 로고 · 뒤집기 {r['logo_mask_invert']} · 시작 {s} · 저장 이름 {r['save_name']} · 저장본 바로 {r['saved_opens_direct']} · 다시 열기 닫기 {r['reopen_close']} · 알프스 {r['alps']} · 되돌리기 {r['undo_back']} · 상호명 없음 {r['noname']} · 오류 {r['err'][:2]}"
        if t == 'tstatic': ok = r['css_comments'][0] == r['css_comments'][1] and r['html_comments'][0] == r['html_comments'][1] and r['node'] in (True, 'node 없음') and r['dialog_tags_ok']; return ok, f"주석 짝 CSS {r['css_comments']} · HTML {r['html_comments']} · JS {r['node']} · 안내창 태그 짝 {r['dialog_tags_ok']}"
    except Exception as e:
        return False, f'판정 실패: {e}'
    return None, ''

ALL = ['tstatic', 't02', 't03', 't04', 't04p', 't05', 't06', 't07', 't08', 't10', 't11', 't14', 't15', 't16', 't17', 't21', 't23', 't24',
       't25', 't27', 't28', 't30', 't31v', 't32', 't35', 't36', 't37', 't38', 't39', 't40', 't41', 't42', 't43', 't44', 't45', 't46', 't47', 't48', 't49', 't50', 't51', 't52', 't53', 't54', 't55']
IGNORE_SAME = {'_sec', 'err', 'rt_err', 'legacy_err'}

def worker(f, tests):
    with sync_playwright() as p:
        b = p.chromium.launch()
        for t in tests:
            t0 = time.time()
            try: r = globals()[t](b, f)
            except Exception:
                import traceback; r = {'EXCEPTION': traceback.format_exc()[-1500:]}
            r['_sec'] = round(time.time() - t0)
            json.dump(r, open(D + f'res/{t}_{f}.json', 'w'), ensure_ascii=False, default=str)
        b.close()

if __name__ == '__main__':
    import shutil, multiprocessing as mp
    args = [a for a in sys.argv[1:]]
    jobs = 3
    if '-j' in args: i = args.index('-j'); jobs = int(args[i + 1]); del args[i:i + 2]
    if len(args) < 2: print(__doc__); sys.exit(1)
    new, base, tests = args[0], args[1], (args[2:] or ALL)
    os.makedirs(D + 'res', exist_ok=True)
    shutil.copy(new, D + 'new.html'); shutil.copy(base, D + 'base.html')
    heavy = ['t02', 't37', 't25', 't05']
    groups = [[t] for t in tests if t in heavy] + [[t for t in tests if t not in heavy]]
    plan = [(f, g) for f in ('new.html', 'base.html') for g in groups if g]
    with mp.Pool(max(1, jobs)) as pool:
        pool.starmap(worker, plan)
    print(f"\n{'검사':8} {'판정':6} {'기준과':8} 요약")
    for t in tests:
        try:
            A = json.load(open(D + f'res/{t}_base.html.json')); B = json.load(open(D + f'res/{t}_new.html.json'))
        except FileNotFoundError:
            print(f'{t:8} 결과 없음'); continue
        if 'EXCEPTION' in B: print(f"{t:8} {'예외':6} {'':8} {B['EXCEPTION'][-300:]}"); continue
        ok, msg = judge(t, B)
        strip = lambda d: {k: v for k, v in d.items() if k not in IGNORE_SAME} if isinstance(d, dict) else d
        same = '같음' if strip(A) == strip(B) else '다름'
        print(f"{t:8} {('통과' if ok else '실패' if ok is False else '볼 것'):6} {same:8} {msg[:400]}")
    od = origdiff('new.html', 'base.html')
    print(f"\n원본 대조: 바뀐 덩어리 {od['blocks']} · 번호 주석 없는 덩어리 {len(od['missing'])} {od['missing'][:5]} · 인용 번호 {od['numbers']}")
    print("'다름'은 이번 수정에서 나온 것인지 확인할 것 — 결과 JSON 은 _check/res/ 에 있다")
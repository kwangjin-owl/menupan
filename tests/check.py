"""메뉴판 검사 — 인수인계 8장 목록을 새 파일과 기준 파일에 똑같이 돌리고 판정한다.
사용:  python3 check.py 새.html 기준.html [검사이름 ... | quick] [-j 동시실행수]
       검사이름을 안 주면 전부(47종, 한 파일에 1시간 안팎). quick 은 빠른 묶음(32종, 하나에 45초 이하 — 305번).
       quick 은 매 작업마다, 전부는 크기 · 배치 · 맞춤 규칙을 건드렸을 때와 동결 전에(인수인계 8장). 결과는 ./_check/ 에 쌓이고 마지막에 표로 나온다.
필요:  pip install playwright pillow --break-system-packages && playwright install chromium ;  poppler-utils(pdftotext · pdftoppm) ; node(있으면 문법 검사)
주의:  -j 를 크게 주면 전환 도중에 찍혀 헛차이가 난다(235번). 차이가 나면 그 검사만 -j 1 로 다시 돌릴 것"""
from playwright.sync_api import sync_playwright  # type: ignore  # 편집기 파이썬에 playwright 가 없어도 경고 안 뜨게(검사는 설치된 곳에서 돈다)
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
SEALS = ['none','tri','mtn','word','star','rtri','rword','rmtn','sstar','ring','rrword']   # 327번. 두 겹 동그라미 글자 도장
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
                fs.append([fo, se, c.js("([o,fo,se])=>{SETTINGS.orient=o; SETTINGS.font=fo; MENU.sheets.forEach((_,i)=>{P(i).seals = se==='none' ? [] : [{cell:5, seal:se}]; P(i).autofit=true;   /* 323번. 도장은 칸마다 */}); syncControls(); applyLook(); render(); fitNow(); applyScale(); return [...MENU.sheets.keys()].map(i=>overA4(i))}", [o, fo, se])])
        out['font_seal_' + o] = [x for x in fs if any(x[2])]
        out['font_seal_n_' + o] = len(fs)
        arts = []
        for a in ['none','horse','zebra','ibex','mountain','fir','cabin','night','bridge','highball','beer','soju','sake','wine','pasta','beerpasta','edelweiss','vine',
                  'ttuk','bapsujeo','bibim','jeon','coffee','croissant','cake','bingsu','teapot','tteok','gimbap','eomuk','ramyeon','chicken','fries','skewer','lantern']:   # 329번. 콘셉트별 그림 16
            c.pg.goto(url(f))
            r = c.js("""([o,a,sel])=>{SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>{ const p=P(i); if (typeof normArts==='function') p.arts = a==='none' ? [] : [0,1,2,3,4,5].map(c=>({cell:c, art:a})); else p.art=a; }); syncControls(); applyLook(); render(); fitNow(); applyScale();
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
            for bi in ((False, True, 'al') if W in (1600, 900, 430) else (False, True)):   # 309번. 'al' = 분류 줄 맞추기를 켠 구성(영문 병기 끔)
                c = Ctx(b, f, W, 900)
                c.js("([o,bi])=>{SETTINGS.orient=o; SETTINGS.bilingual=bi===true; if (bi==='al') MENU.sheets.forEach((_,i)=>P(i).alignRows=true); const s=MENU.sheets[0][0][0]; s.items[0].out=true; s.items[0].pick=true; s.items[1].name='아주 아주 긴 메뉴 이름을 넣어 두 줄로 접히는지 보는 줄입니다'; syncControls(); applyLook(); render(); applyScale();}", [o, bi])
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
def ink_bottom(p, bb):
    """296번. 아래 여백은 **잉크**로 잰다 — 파일의 넘침 판정(252번)이 캔버스로 잰 글자 모양이다. 글자 상자(pdftotext)는 글꼴의 아래 빈 공간까지라
    [한 장에 맞춤]이 여백선까지 채운 줄(잉크 11.09mm)이 상자로는 10.6mm 로 나왔다. 쪽마다 가장 아래 낱말 다섯의 잉크 아래 끝(mm)"""
    out = []
    for n, (W, H, body) in enumerate(re.findall(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', bb, re.S), 1):
        W, H = float(W), float(H)
        ws = sorted((tuple(map(float, w)) for w in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"', body)), key=lambda w: -w[3])[:5]
        pre = D + 'res/ink_' + os.path.basename(p)[:-4]
        subprocess.run(['pdftoppm', '-r', '300', '-f', str(n), '-l', str(n), '-gray', '-png', p, pre], check=True)
        f = sorted(x for x in os.listdir(D + 'res') if x.startswith(os.path.basename(pre) + '-'))[-1]
        im = Image.open(D + 'res/' + f).convert('L'); sx, sy = im.size[0] / W, im.size[1] / H; low = 0
        for x0, y0, x1, y1 in ws:
            X0, X1, Y0, Y1 = int(x0 * sx), int(x1 * sx), int(y0 * sy), min(im.size[1] - 1, int((y1 + 6) * sy))
            for y in range(Y1, Y0, -1):
                if any(im.getpixel((x, y)) < 90 for x in range(X0, X1, 2)): low = max(low, y); break
        out.append(round((im.size[1] - low) / sy * MM, 2))
        os.remove(D + 'res/' + f)
    return out
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
        ink1 = ink_bottom(p1, bb1)   # 296번
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
        out[o] = {'pages': len(m1), 'size': [x[3:] for x in m1], 'margins': [x[:3] for x in m1], 'inkBottom': ink1, 'multicol': multi,
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
    c.js("(s)=>{const it=MENU.sheets[0][0][0].items[0]; it.name=s; it.desc=s; F(0).notes.push(s); MENU.brand.sub=s; P(0).alignRows=true; render(); touch();}", SPECIAL)   # 309번. 분류 줄 맞추기 키도 왕복
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
    out['legacy_art'] = c.js("()=>JSON.stringify(P(0).arts ?? null)")   # 302번. 옛 맨 위 art:'horse' → [{cell:5, art:'horse'}]
    out['legacy_open'] = c.js("()=>({sheets:MENU.sheets.length, cols:MENU.sheets[0].length, columns:'columns' in MENU, notes:F(0).notes, origin:F(0).origin, hours:MENU.hours[1].time, noren:P(0).noren, ns:P(0).norenScale, orient:SETTINGS.orient, drawn:document.querySelectorAll('.sheet .row').length})")
    with c.pg.expect_download() as d: c.pg.click('#b-file'); c.pg.click('#b-save')
    p = D + 'res/legacy_saved_' + f; d.value.save_as(p)
    saved = open(p, encoding='utf-8').read(); md = re.search(r'\n<script id="menu-data">(.*?)</script>', saved, re.S).group(1)
    out['legacy_saved_oldkeys'] = [k for k in ['"columns"', '"legend"', '"unit"', '"address"', '"tel"', '"note"', '"footnotes"', '"footline"', '"layout"', '"norenTall"', '"sheetArt"', '"line"'] if k in md]
    top = re.search(r'const SETTINGS = (\{.*\});', md, re.S).group(1)
    S = json.loads(top); out['legacy_saved_toplevel_pagekeys'] = [k for k in ['noren','norenScale','scale','art','seal','showNotes','showOrigin','autofit'] if k in S]
    out['legacy_saved_pagekeys'] = sorted({k for pg in S.get('pages', []) for k in ('art', 'artColor', 'artOp') if k in pg})   # 302번
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
    c.js("()=>{panelTab='menu'; syncPageTabs(); syncPage();}")   # 333번 — 글자 크기는 [메뉴]
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
            c.js("()=>{document.querySelector('#b-edit').click(); panelTab='top'; panelPage=1; syncPageTabs(); syncPage(); document.querySelector('#b-edit').click();}")
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
            for w_ in range(4):   # 357번. 부하가 크면 ＋ 가 늦게 뜬다 — 마우스를 조금씩 움직이며 최대 1.2초까지 기다린다(한 번만 기다리면 이 환경에서 5~7번째에 놓쳤다. 제품이 아니라 시험의 시간 문제였다)
                if not btn.count() or btn.first.is_visible(): break
                pg.mouse.move(bb['x'] + bb['width'] + 60, bb['y'] + 4); pg.wait_for_timeout(60); pg.mouse.move(bb['x'] + 14 + w_, bb['y'] + [min(9, bb['height'] / 2), bb['height'] / 2, max(2, bb['height'] - 5), max(2, bb['height'] - 12)][w_], steps=4); pg.wait_for_timeout(300)   # 위쪽 줄이 칸 위를 덮는 만큼 찰 때는 칸의 가운데 · 아래쪽에서 가리킨다   # 한 번 밖으로 나갔다가 들어와야 :hover 가 다시 계산된다
            if btn.count() == 0 or not btn.first.is_visible(): break
            b2 = btn.first.bounding_box(); pg.mouse.move(b2['x'] + b2['width'] / 2, b2['y'] + b2['height'] / 2, steps=6)
            pg.mouse.click(b2['x'] + b2['width'] / 2, b2['y'] + b2['height'] / 2); pg.wait_for_timeout(80); pg.keyboard.type('x'); pg.wait_for_timeout(40); n += 1
        return n
    out = {}
    out['secnote'] = [press('.sheet section', '＋ 안내 추가', 8), c.js("()=>(MENU.sheets[0][0][0].notes||[]).length")]
    out['notes'] = [press('.sheet .foot .zone', '＋ 바닥 글 추가', 12), c.js("()=>F(0).notes.length")]
    out['hours'] = [press('.sheet .hours', '＋ 시간 추가', 8), c.js("()=>MENU.hours.length")]
    c.js("()=>{panelTab='menu'; panelPage=1; syncPageTabs(); syncPage(); document.querySelector('#panel').hidden=false; placePanel();}")   # 333 · 334번 — 병은 [메뉴] 맨 아래, 고칠 장이 와인 장일 때
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
    BI = "(v)=>{const l=document.getElementById('f-lang'); if(l){l.value=v?'en':''; l.dispatchEvent(new Event('change',{bubbles:true}));} else {const e=document.getElementById('f-bi'); e.checked=v; e.dispatchEvent(new Event('change',{bubbles:true}));}}"   # 306번
    chk('start')
    c.js(SEL, ['f-layout', 'landscape']); chk('landscape')
    c.js(SEL, ['f-layout', 'portrait']); chk('portrait')
    c.js(BI, True); chk('bilingual')
    c.js("()=>{panelTab='menu'; syncPageTabs(); syncPage();}")
    for k in range(3): c.js(CLK, 'b-plus'); pg.wait_for_timeout(60)
    chk('plus')
    c.js(CLK, 'b-minus'); chk('minus')
    c.js("()=>{const r=document.querySelector('#sz-range'); r.value=70; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change'));}"); chk('slider70')
    c.js("()=>{const r=document.querySelector('#sz-range'); r.value=120; r.dispatchEvent(new Event('input')); r.dispatchEvent(new Event('change'));}"); chk('slider120')
    c.js(CLK, 'b-fit'); chk('fit')
    c.js("()=>{panelPage=1; syncPageTabs(); syncPage();}"); c.js(CLK, 'b-plus'); c.js(CLK, 'b-plus'); chk('wine plus')
    c.js(BI, False); chk('bi off')
    c.js("()=>{panelPage=0; syncPageTabs(); syncPage(); const a=document.getElementById('f-align'); if(a){a.checked=true; a.dispatchEvent(new Event('change',{bubbles:true}));}}"); chk('align on')   # 309번. 분류 줄 맞추기 — 판정과 표시가 같은 답인지
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
    for tab in ('look', 'top', 'menu', 'foot', 'deco'):   # 333번 — 탭 다섯을 다 본다
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
                   MENU.sheets.forEach((_,i)=>{ if (typeof normArts==='function') P(i).arts=[]; else P(i).art='none'; P(i).autofit=true;}); syncControls(); applyLook(); render(); fitNow(); applyScale();}""", [o, fo, sh, KINDS])
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
    new = 'function normArts' in src   # 302번. 새 형식 파일은 칸 목록을 망가뜨린다(옛 키 art 가 있으면 그쪽이 먼저 옮겨지므로 넣지 않는다)
    for k, pg in enumerate(S.get('pages', [])):
        if new: pg.pop('art', None); pg.update({'arts': [{'cell': 9, 'art': 'dragon'}, {'cell': 2, 'art': 'horse', 'color': 'nope', 'op': 'x'}, {'cell': 2, 'art': 'zebra'}, 'junk', {'cell': 1.5, 'art': 'fir'}], 'seals': [{'cell': 9, 'seal': 'tri'}, {'cell': 2, 'seal': 'star', 'color': 'nope'}, {'cell': 2, 'seal': 'tri'}, 'junk', {'cell': 1.5, 'seal': 'tri'}, {'cell': 3, 'seal': 'bogus'}]})   # 303 → 323번. 칸마다 도장 목록(망가진 것 섞음)
        pg.update({'noren': 'bogus', 'seal': 7, **({} if new else {'art': 'dragon'}),
                   'norenScale': ['abc', None, 0, -1][k % 4], 'scale': ['big', -2, 0, None][k % 4], 'alignRows': ['yes', 1, False, None][k % 4]})   # 309번. 켜짐은 true 하나
    bad = src[:m.start(2)] + json.dumps(S, ensure_ascii=False, indent=2).replace('<', '\\u003C') + src[m.end(2):]
    open(D + 'res/bad_' + f, 'w', encoding='utf-8').write(bad)
    c = Ctx(b, 'res/bad_' + f)
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200)
    out = c.js("""()=>{const r={}; r.S={font:SETTINGS.font, theme:SETTINGS.theme, mark:SETTINGS.mark, pageno:SETTINGS.pageno, sec:SETTINGS.secAlign, wine:SETTINGS.wineAlign};
      r.pages=MENU.sheets.map((_,i)=>[P(i).noren, P(i).arts ? P(i).arts.map(x=>x.art).join(',') : P(i).art, JSON.stringify(P(i).seals), P(i).scale, P(i).norenScale]);
      r.arts=MENU.sheets.map((_,i)=>P(i).arts ? JSON.stringify(P(i).arts)+'|'+JSON.stringify(P(i).seals ?? null)+(['seal','sealCells','sealColor','sealPos'].some(k=>k in P(i)) ? '|옛 키 남음' : '') : null);   // 302 · 303 · 323번
      r.align=MENU.sheets.map((_,i)=>'alignRows' in P(i));   // 309번. 망가진 값은 키가 없어야(꺼짐)
      r.ui={font:document.querySelector('#f-font').value, theme:document.querySelector('#f-theme').value, mark:document.querySelector('#f-mark').value, pageno:document.querySelector('#f-pageno').value,
            sec:document.querySelector('#f-secalign').value, wine:document.querySelector('#f-winealign').value};
      r.pageui=[]; for (const i of [0,1]){ panelPage=i; panelTab='top'; syncPageTabs(); syncPage(); r.pageui.push([document.querySelector('#f-noren').value, document.querySelector('#f-art').value, document.querySelector('#f-seal').value, document.querySelector('#sz-val').textContent, document.querySelector('#nsz-val').textContent]); }
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
    out = {'base': base, 'steps': steps, 'allSame': all(s[1] for s in steps), 'err': c.errs}
    # 302 · 303번. 고른 칸에 선다 — 가운데점이 **상단 아래부터** 종이를 2 × 3 으로 나눈 그 칸에 있는지(두 방향 · 칸 여섯). 도장은 여러 칸을 한꺼번에 켜 본다
    out['pos'] = c.js("""()=>{ const o=[]; for (const or of ['portrait','landscape']){ SETTINGS.orient=or;
        for (let k=0;k<6;k++){ P(0).seals=[k, (k+3)%6].sort((a,b)=>a-b).map(x=>({cell:x, seal:'tri'}));   /* 323번 */ P(0).arts=[{cell:k, art:'horse'}]; render(); applyScale();
          const sh=document.querySelector('.sheet'), S=sh.getBoundingClientRect(), tb=sh.querySelector('.noren').getBoundingClientRect().bottom-S.top;
          const at=e=>{ const q=e.getBoundingClientRect(); const cx=(q.left+q.right)/2-S.left, cy=(q.top+q.bottom)/2-S.top; return Math.floor(cx/(S.width/2)) + 2*Math.floor((cy-tb)/((S.height-tb)/3)); };
          const seals=[...sh.querySelectorAll('.seal:not(.blank)')].map(at).sort((a,b)=>a-b);
          o.push([or, k, JSON.stringify(seals)===JSON.stringify(P(0).seals.map(x=>x.cell)) ? k : 'seal '+JSON.stringify(seals), at(sh.querySelector('.art'))]); } } return o; }""")
    out['sealPosMove'] = c.js("()=>{ if (typeof normSeals!=='function') return null; const p={seal:'tri', sealPos:0, sealColor:'band'}, q={seal:'none', sealCells:[1,2]}; normSeals(p, []); normSeals(q, []); return JSON.stringify(p.seals) + '|' + JSON.stringify(q.seals) + ((['seal','sealPos','sealColor'].some(k=>k in p)) ? ' 남음' : '') }")   # 302번 파일의 sealPos · 296번 색 → 323번 칸마다 · 없음 → 빈 목록
    out['posOk'] = all(x[1] == x[2] == x[3] for x in out['pos']) and out['sealPosMove'] == '[{"cell":0,"seal":"tri","color":"band"}]|[]'; c.close(); return out

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
    out = {'sheets': out, 'err': c.errs}; c.close()
    # 309번. 분류 줄 맞추기를 켠 구성 — 줄마다 k번째 분류 제목의 위끝이 같은가(그 줄에 분류가 있는 단만) · 분류 틈은 그대로 한 값 · 맞춤이 넘치지 않는가
    #        켜기 전(같은 구성 · 끔)과 나란히 잰다 — 끔은 어긋나 있어야 시험이 뜻이 있다. 기능이 없는 파일(308번)은 어긋난 채라 실패한다
    it = lambda n, k: [{'name': f'{n}{i}', 'price': 10000 + i * 1000} for i in range(k)]
    BADA = [[{'name': '회', 'items': it('회', 5)}, {'name': '식사', 'items': it('밥', 3)}], [{'name': '구이', 'items': it('구', 4)}, {'name': '안주', 'items': it('안', 3)}]]
    CASES = [('알프스 1쪽 세로 2단', None, False, 'portrait'),
             ('가로 3단 2·2·1', BADA + [[{'name': '주류', 'items': it('술', 9)}]], True, 'landscape'),
             ('가로 4단 2·2·3·1', [[{'name': 'A', 'items': it('a', 6)}, {'name': 'B', 'items': it('b', 2)}], [{'name': 'C', 'items': it('c', 3)}, {'name': 'D', 'items': it('d', 5)}],
                                  [{'name': 'E', 'items': it('e', 2)}, {'name': 'F', 'items': it('f', 2)}, {'name': 'G', 'items': it('g', 2)}], [{'name': 'H', 'items': it('h', 4)}]], True, 'landscape')]
    ROWS = """()=>{const sh=document.querySelector('.sheet[data-pi="0"]'); const L=[...sh.querySelectorAll('.body > .col')].map(c=>[...c.children].filter(n=>n.tagName==='SECTION'&&n.offsetHeight>0).map(n=>(n.querySelector(':scope > .sec-head')||n).getBoundingClientRect().top));
      const K=Math.max(...L.map(l=>l.length)); let d=0; for(let k=0;k<K;k++){const t=L.map(l=>l[k]).filter(v=>v!==undefined); if(t.length>1) d=Math.max(d, Math.max(...t)-Math.min(...t));}
      const sg=new Set(); sh.querySelectorAll('.col').forEach(col=>{const secs=[...col.querySelectorAll(':scope > section')]; for(let k=1;k<secs.length;k++) sg.add(+(secs[k].getBoundingClientRect().top-secs[k-1].getBoundingClientRect().bottom).toFixed(1));});
      return [+d.toFixed(2), sg.size, overWhy(0), P(0).scale]}"""
    out['align309'] = []
    for name, sheet, fit, o in CASES:
        row = [name]
        for on in (False, True):
            c = Ctx(b, f)
            c.js("""([sheet,fit,o,on])=>{ if (sheet){ MENU.sheets=[sheet]; SETTINGS.pages=[SETTINGS.pages[0]]; MENU.feet=[MENU.feet[0]]; }
              SETTINGS.orient=o; const pg=P(0); pg.autofit=fit; if(on) pg.alignRows=true; else delete pg.alignRows; syncControls(); applyLook(); render(); applyScale(); }""", [sheet, fit, o, on])
            c.pg.wait_for_timeout(150); row.append(c.js(ROWS)); out['err'] += c.errs; c.close()
        out['align309'].append(row)
    return out

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
    # 310번. 채운 단추(앞으로 가기)는 그 줄의 오른쪽 끝 — 인쇄 안내 · 넘침 경고 · 번역 창(309번까지 넘침 경고 · 번역 창은 채운 단추가 왼쪽)
    c = Ctx(b, f); pg = c.pg; LAST = "(sel)=>{const d=document.querySelector(sel); const f=[...d.querySelectorAll('.bt-fill')].find(e=>e.offsetParent); if(!f) return null; const row=[...f.parentElement.children].filter(e=>e.tagName==='BUTTON'&&e.offsetParent); return row[row.length-1]===f}"
    o = {}
    c.js("()=>{delete SETTINGS.printHint}"); pg.click('#b-print'); pg.wait_for_timeout(250); o['printhint'] = c.js(LAST, '#printhint'); pg.keyboard.press('Escape'); pg.wait_for_timeout(120)
    c.js("()=>{P(0).scale=1.3; P(0).autofit=false; render(); applyScale();}"); pg.click('#b-print'); pg.wait_for_timeout(250); o['overwarn'] = c.js(LAST, '#overwarn'); pg.keyboard.press('Escape'); pg.wait_for_timeout(120)
    c.js("()=>{P(0).scale=1; render(); applyScale();}"); pg.click('#b-edit'); pg.wait_for_timeout(200)
    c.js("()=>{const l=document.querySelector('#f-lang'); if(!l) return; l.value='en'; l.dispatchEvent(new Event('change',{bubbles:true})); document.querySelector('#f-tr').click();}"); pg.wait_for_timeout(250)
    o['trask'] = c.js(LAST, '#trask') if c.js("()=>!!document.querySelector('#trask')?.open") else 'no'
    out['order310'] = o; c.close()
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
        c.js("()=>{const d=document.querySelector('#overwarn'); if(d.open) d.close(); if(!editing) document.querySelector('#b-edit').click();}"); c.pg.wait_for_timeout(250)   # 쪽 탭 줄은 편집 중에만 보인다
        tab = c.js("()=>[...document.querySelectorAll('.pagebar .pstat')].map(e=>e.textContent+' | '+e.title).join(' / ')")   # 297번. 쪽 탭 줄 글자도 본다 — 없는 단추 이름이 여기 남아 있었는데 알림만 봐서 놓쳤다
        out[k] = {'why': why, 'warn': w, 'toast': t, 'tab': tab, 'err': c.errs}; c.close()
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
    # 394번. CSS 괄호 짝 — 393번에 남은 「}」 하나를 편집기(VS Code)가 잡았는데 이 검사는 주석 짝만 봐서 못 잡았다. 주석 · 문자열을 걷고 깊이가 0 밑으로 내려가는지 · 끝이 0인지
    c2 = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', '""', re.sub(r'/\*[\s\S]*?\*/', '', st)); dep, neg = 0, []
    for k, ch in enumerate(c2):
        if ch == '{': dep += 1
        elif ch == '}':
            dep -= 1
            if dep < 0: neg.append(c2[max(0, k - 60):k + 1].replace('\n', ' ')); dep = 0
    return {'css_braces': [dep, neg[:3]], 'css_comments': [st.count('/*'), st.count('*/')], 'html_comments': [body.count('<!--'), body.count('-->')], 'node': node,
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
      P(1).showNotes=false; P(1).showTitle=false; P(1).showSub=false;
      P(0).arts=[{cell:0, art:'horse', color:'#112233'}, {cell:3, art:'fir', op:'mid'}]; P(0).seals=[{cell:1, seal:'tri'}, {cell:2, seal:'star', color:'#123456'}]; P(1).seals=[];   /* 302 · 323번. 그림 칸 · 칸마다 도장(모양 · 색)도 옮겨 가는지 */
      P(0).alignRows=true; delete P(1).alignRows;   /* 309번. 분류 줄 맞추기도 옮겨 가는지 */
      syncPage(); document.querySelector('#b-copypage').click();
      return PAGE_KEYS.every(k=>JSON.stringify(P(0)[k])===JSON.stringify(P(1)[k])) && JSON.stringify(P(1).arts)==='[{"cell":0,"art":"horse","color":"#112233"},{"cell":3,"art":"fir","op":"mid"}]' && JSON.stringify(P(1).seals)==='[{"cell":1,"seal":"tri"},{"cell":2,"seal":"star","color":"#123456"}]' && P(1).alignRows===true }""")
    # 309번. 분류 줄 스위치 — 켜면 그 장만 true · 맞춘 여백이 생김 · 끄면 키가 없어지고 여백도 / 단이 하나인 장에서는 흐림
    out['align309'] = c.js("""()=>{ const a=document.querySelector('#f-align'); if(!a) return null; delete P(0).alignRows; delete P(1).alignRows; panelPage=0; panelTab='menu'; syncPageTabs(); syncPage(); render();
      a.checked=true; a.dispatchEvent(new Event('change',{bubbles:true})); const on=[P(0).alignRows===true, !('alignRows' in P(1)), document.querySelectorAll('.sheet[data-pi="0"] section[data-al]').length>0];
      a.checked=false; a.dispatchEvent(new Event('change',{bubbles:true})); const off=[!('alignRows' in P(0)), document.querySelectorAll('section[data-al]').length===0];
      const keep=MENU.sheets[0]; MENU.sheets[0]=[keep.flat()]; render(); syncPage(); const one=[a.disabled, getComputedStyle(a.closest('label')).opacity!=='1']; MENU.sheets[0]=keep; render(); syncPage();
      return [...on, ...off, ...one] }""")
    # 302번. [모든 그림에 같게] — 고른 칸의 색 · 진하기가 이 장의 다른 그림 전부에. 없으면(기준 파일) 실패
    out['artsame'] = c.js("""()=>{ const b=document.querySelector('#b-artsame'); if (!b) return null; panelPage=0;
      P(0).arts=[{cell:0, art:'horse', color:'#aa0000', op:'strong'}, {cell:1, art:'zebra'}, {cell:5, art:'fir', op:'mid'}]; panelCell=0; render(); syncPage(); b.click();
      return JSON.stringify(P(0).arts.map(x=>[x.color||'', x.op||''])) }""")
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
    out['winearts311'] = c.js("()=>{ const p=SETTINGS.pages[1]; return JSON.stringify(p.arts)+'|'+('art' in p) }")   # 311번. 새 와인 장은 포도나무 한 칸(새 형식) · 옛 키 art 없음 — 310번까지는 앞 장 그림 복사 + art:'vine' 이 같이 들어가 다시 열면 바뀌었다
    # (e) 상단 크기 ＋ㅡ 걸음 = 글자 크기 ＋ㅡ 걸음(4%)
    out['nstep'] = c.js("""()=>{ panelTab='top'; panelPage=0; syncPageTabs(); P(0).norenScale=0.8; document.querySelector('#b-nplus').click(); return P(0).norenScale }""")
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
#   그리고 가장자리 띠(.nogo)가 4mm 이고 완성본 · 미리보기 · 인쇄(편집 중 인쇄도)는 투명(색이 끝까지 간다, 401번), 편집은 빗금 + clip-path 인지
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
        vis = "()=>[...document.querySelectorAll('.nogo')].map(e=>{const c=getComputedStyle(e); return [c.display, +(parseFloat(c.borderTopWidth)/96*25.4).toFixed(1), c.borderTopColor, c.outlineStyle, c.backgroundImage.startsWith('repeating-linear-gradient'), c.clipPath !== 'none']})"
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
        out['254_line_' + seal] = c.js("""(off)=>{ if(off){ P(0).seals=[]; }
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
    out['started'] = c.js("()=>({open:document.querySelector('#start').open, editing:document.body.classList.contains('editing'), sheets:document.querySelectorAll('.sheet').length, title:document.title, flag:SETTINGS.startScreen===undefined, undo:undoStack.length, font:SETTINGS.font, seal:((P(0).seals||[]).map(x=>x.seal).join(',')||'none'), art:(P(0).arts ? (P(0).arts.map(x=>x.art).join(',')||'none') : P(0).art), logo:!!SETTINGS.logoImg, focus:document.activeElement?.dataset?.path||''})")
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
    pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_selector('.gd-block', timeout=4000); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)   # 334번 — 둘러보기가 뜬 뒤에 닫는다(시간으로 기다리면 뜨기 전에 누를 수 있다)
    with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
    out['noname'] = [c.js("()=>document.title"), d.value.suggested_filename]
    out['err'] += c.errs; c.close()
    # 330번 — 폰에서 창이 넓혀진 기준 폭(802px)의 가운데에 서서 오른쪽이 화면 밖으로 나갔다. t08 의 390px 은 PC 창이라 기준 폭이 안 넓어져 못 잡았다
    #          첫 화면 · 넓은 틀로 바뀐 첫 화면 · 옆으로 밀어 둔 뒤 연 인쇄 안내가 보이는 화면 안에 서는지, 닫으면 인라인 값이 걷히는지
    VIS = "(sel)=>{const d=document.querySelector(sel); if(!d||!d.open) return 'closed'; const r=d.getBoundingClientRect(), v=visualViewport; return r.left>=v.offsetLeft-0.5 && r.right<=v.offsetLeft+v.width+0.5}"
    m = {}
    for W, H in ((390, 844), (430, 932)):
        ctx = b.new_context(viewport={'width': W, 'height': H}, is_mobile=True, has_touch=True); pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(url('start_' + f)); pg.wait_for_timeout(400)
        r = {'wide': pg.evaluate("()=>innerWidth - document.documentElement.clientWidth > 40"), 'start': pg.evaluate(VIS, '#start')}
        pg.evaluate("()=>document.querySelector('#start').classList.add('wide')"); pg.wait_for_timeout(300); r['start_wide'] = pg.evaluate(VIS, '#start')
        pg.goto(url(f)); pg.wait_for_timeout(400)
        pg.evaluate("()=>{window.print=()=>{}; MENU.sheets.forEach((_,i)=>P(i).autofit=true); fitNow(); applyScale(); scrollTo(400, 300)}"); pg.wait_for_timeout(200)
        pg.evaluate("()=>document.querySelector('#b-print').click()"); pg.wait_for_timeout(300); r['print_scrolled'] = pg.evaluate(VIS, '#printhint')
        pg.evaluate("()=>document.querySelector('#printhint').close()"); pg.wait_for_timeout(100)
        r['closed_clean'] = pg.evaluate("()=>!(document.querySelector('#printhint').getAttribute('style')||'').trim()")
        r['err'] = errs; m[str(W)] = r; ctx.close()
    out['mobile330'] = m
    # 331번 — 와인 분류가 없으면 [분류 형식] 고르기 · 꾸미기 창 와인 묶음이 안 보인다. 와인 장을 넣으면 보이고, 되돌리면 다시 감춘다. 저장본에 감춤 표시가 안 남는다
    c = Ctx(b, 'start_' + f, dl=True); pg = c.pg
    pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_selector('.gd-block', timeout=4000); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)   # 334번 — 둘러보기가 뜬 뒤에 닫는다(시간으로 기다리면 뜨기 전에 누를 수 있다)
    V = "()=>[document.querySelectorAll('.winesel').length, document.querySelector('.panel .pblock[data-kind=\"wine\"]').hidden]"   # 창이 닫혀 있어도 재게 — 감춤 표시 자체를 본다
    w = {'blank': c.js(V)}
    c.js("()=>[...document.querySelectorAll('.pagebar button')].find(b=>b.textContent.includes('와인 장 추가')).click()"); pg.wait_for_timeout(400)
    c.js("()=>{panelPage=MENU.sheets.findIndex((_,i)=>sheetKind(i)!=='menu'); syncPageTabs(); syncPage();}"); pg.wait_for_timeout(150)
    w['wine_added'] = c.js(V)
    c.js("()=>{panelPage=0; syncPageTabs(); syncPage();}"); pg.wait_for_timeout(150)
    w['menu_page_hides'] = c.js(V)[1]   # 334번 — 고칠 장이 메뉴 장이면 와인 묶음을 감춘다
    with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
    w['saved_no_hidden'] = 'data-kind="wine" hidden' not in open(d.value.path(), encoding='utf-8').read()
    pg.keyboard.press('Escape'); c.js("()=>{ if(!editing) document.querySelector('#b-edit').click(); }"); pg.wait_for_timeout(300)
    c.js("()=>document.querySelector('#b-undo').click()"); pg.wait_for_timeout(400)
    w['undone'] = c.js(V) + c.js("()=>[MENU.sheets.length, editing]")   # 편집 중이어야 고르기 수가 뜻이 있다
    w['err'] = c.errs; c.close()
    out['wine331'] = w
    # 332번 — 꾸미기 창 탭을 하려는 일로: 이름 넷(와인 장이 있으면 다섯) · 한 줄에 셋(이름이 접히지 않음) · 아랫줄이 남은 폭을 다 채움 · 마우스를 올리면 안내(title)
    #          · 손잡이가 제 탭에 · 「이 장만」은 장별 묶음 탭에만 · 쪽 고르기와 [다른 장에도 똑같이]는 그런 탭에서만
    c = Ctx(b, 'start_' + f, dl=True); pg = c.pg
    pg.click('#st-blank'); pg.click('#st-go'); pg.wait_for_selector('.gd-block', timeout=4000); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)   # 334번 — 둘러보기가 뜬 뒤에 닫는다(시간으로 기다리면 뜨기 전에 누를 수 있다)
    c.js("()=>{ if(!editing) document.querySelector('#b-edit').click(); if(document.querySelector('#panel').hidden) document.querySelector('#b-style').click(); }"); pg.wait_for_timeout(300)
    TB = """()=>{ const bar=document.querySelector('#ptabs').getBoundingClientRect(), bs=[...document.querySelectorAll('#ptabs > button')], rs=bs.map(b=>b.getBoundingClientRect());
      const rows=[...new Set(rs.map(r=>Math.round(r.top)))]; const last=rs.filter(r=>Math.round(r.top)===rows[rows.length-1]);
      return {ids:bs.map(b=>b.dataset.tab), oneLine:bs.every(b=>{ const r=document.createRange(); r.selectNodeContents(b); return b.scrollWidth<=b.clientWidth+1 && new Set([...r.getClientRects()].map(q=>Math.round(q.top))).size===1; }), rows:rows.length, perRow1:rs.filter(r=>Math.round(r.top)===rows[0]).length,
        lastFill:Math.abs(last.reduce((a,r)=>a+r.width,0)-bar.width)<=1, titles:bs.every(b=>b.title.length>3)} }"""
    t = {'blank': c.js(TB)}
    HOME = {'f-font':'look','f-theme':'look','f-paper':'look','f-topmode':'top','f-title':'top','f-noren':'top','f-logo':'top','f-layout':'menu','sz-range':'menu','b-fit':'menu','f-secstyle':'menu','f-align':'menu','f-mark':'menu','f-leader':'menu','btpick':'menu','f-notes':'foot','f-pageno':'foot','g-art':'deco'}   # 333번
    t['home'] = c.js("(h)=>Object.entries(h).filter(([id,tab])=>(document.getElementById(id)?.closest('.ptab')||{dataset:{}}).dataset.tab!==tab).map(e=>e[0])", HOME)
    t['vis'] = {}
    for tab in ('look', 'top', 'menu', 'foot', 'deco'):
        c.js(f"()=>document.querySelector('#ptabs [data-tab=\"{tab}\"]').click()"); pg.wait_for_timeout(150)
        t['vis'][tab] = c.js("()=>[!document.querySelector('#pgbar').hidden, !!document.querySelector('#pgbar #b-copypage') && !document.querySelector('#pgbar').hidden, [...document.querySelectorAll('.ptab.on .pgonly')].length]")
    c.js("()=>[...document.querySelectorAll('.pagebar button')].find(b=>b.textContent.includes('와인 장 추가')).click()"); pg.wait_for_timeout(400)
    t['wine'] = c.js(TB)
    c.js("()=>{panelTab='menu'; panelPage=MENU.sheets.findIndex((_,i)=>sheetKind(i)!=='menu'); syncPageTabs(); syncPage(); const p=document.querySelector('#panel'); p.scrollTop=p.scrollHeight;}"); pg.wait_for_timeout(150)
    t['sticky'] = c.js("()=>{const p=document.querySelector('#panel').getBoundingClientRect(), a=document.querySelector('#ptabs').getBoundingClientRect(), g=document.querySelector('#pgbar').getBoundingClientRect(); return [a.top>=p.top-1 && a.bottom<=p.top+140, g.top>=a.bottom-1 && g.bottom<=p.top+240, !!document.querySelector('#pgbar #b-copypage')]}")   # 334번
    # 335번 — 부품 규칙: 나뉜 고르기는 바탕 하나(칸에 테두리 없음) · 묶음 제목 보통 글자 간격 · 굵게는 스위치 · [− | +] 한 덩어리 28px · 「고칠 장」 이름표가 고르기 위
    t['parts335'] = c.js("""()=>{ const seg=document.querySelector('#f-topmode'), bs=seg?[...seg.querySelectorAll('button')]:[], lb=document.querySelector('#pgbar .pglbl'), pk=document.querySelector('#pgpick');
      return [ bs.length===2 && bs.every(b=>parseFloat(getComputedStyle(b).borderTopWidth)===0) && parseFloat(getComputedStyle(seg).borderTopWidth)>0,
        [...document.querySelectorAll('#panel .pgrp')].every(h=>getComputedStyle(h).letterSpacing==='normal'),
        (document.querySelector('#b-bold')||{}).type==='checkbox',
        [...document.querySelectorAll('#panel .stepg > button')].length===4 && [...document.querySelectorAll('#panel .stepg > button')].filter(b=>b.offsetParent).every(b=>Math.round(b.closest('.stepg').getBoundingClientRect().height)===32),   // 389번. 묶음 바깥이 32(꾸미기 창 높이 단계)
        !!lb && !!pk && lb.getBoundingClientRect().bottom <= pk.getBoundingClientRect().top + 1,
        [...document.querySelectorAll('#panel .stepg > button')].every(b=>getComputedStyle(b).borderTopLeftRadius==='0px' && getComputedStyle(b).borderTopRightRadius==='0px') ] }""")   # 336번 — 한 덩어리 [− | +]의 칸은 안쪽 모서리 0(꾸미기 창 「단추 8px」이 이겨 + 칸이 따로 싸여 보였다)
    t['err'] = c.errs; c.close()
    out['tabs332'] = t
    return out

# ───────────────────────── 48. 글자가 바뀌는 막대 단추의 폭(규칙 I · 267번). 263번이 "편집"↔"편집 끝" 폭을 망가뜨렸는데 t25(종이 튐)는 못 잡았다
def t48(b, f):
    c = Ctx(b, f); w = lambda: c.js("()=>[...document.querySelectorAll('.bar button')].map(e=>[e.id, +e.getBoundingClientRect().width.toFixed(1)])")
    a = w(); c.pg.click('#b-edit'); c.pg.wait_for_timeout(200); e = w()
    c.js("(sel)=>{const e=document.querySelector(sel), t=e.closest('.ptab'); panelTab=t.dataset.tab; if (e.closest('.pblock[data-kind=wine]')) panelPage=Math.max(0, MENU.sheets.findIndex((_,i)=>sheetKind(i)!=='menu')); syncPageTabs(); syncPage();}", "#btpick"); c.pg.wait_for_timeout(150)   # 332번 — 병 단추는 [와인] 탭(손잡이가 든 탭을 찾아 연다)
    h = c.js("()=>[[...document.querySelectorAll('#btpick button')].map(b=>Math.round(b.getBoundingClientRect().height)), [...document.querySelectorAll('.wfrow button')].map(b=>Math.round(b.getBoundingClientRect().height - b.closest('.wfrow').getBoundingClientRect().height))]")   # 268번 — 병 단추 높이 · ▲▼ 는 (높이 − 그 줄 높이) — 336번: 숫자 대신 줄과 견준다
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200); z = w()
    # 308번 — ① 글자 크기 막대의 양 끝 = SCALE_MIN · SCALE_MAX(304번이 상한을 140% 로 올리며 막대만 120 에 남았다) · 140% 에서 막대 값도 140
    #         ② 줄 도구의 켜진 단추가 꺼진 단추와 달라 보일 것(300번부터 같았다) ③ 와인 카드 줄 도구가 한 줄(「추/천」으로 접혔다)
    c.pg.click('#b-edit'); c.pg.wait_for_timeout(200)
    c.js("(sel)=>{const e=document.querySelector(sel), t=e.closest('.ptab'); panelTab=t.dataset.tab; if (e.closest('.pblock[data-kind=wine]')) panelPage=Math.max(0, MENU.sheets.findIndex((_,i)=>sheetKind(i)!=='menu')); syncPageTabs(); syncPage();}", "#b-plus"); c.pg.wait_for_timeout(150)   # 332번 — 글자 크기가 든 탭(전에는 마지막 탭 = 장별)
    for _ in range(16): c.pg.click('#b-plus'); c.pg.wait_for_timeout(40)
    rng = c.js("()=>[+$('#sz-range').min, +$('#sz-range').max, Math.round(SCALE_MIN*100), Math.round(SCALE_MAX*100), +$('#sz-range').value, Math.round(P(panelPage).scale*100)]")
    c.js("()=>{const t=[...document.querySelectorAll('#ptabs button')]; t[0].click()}")
    c.js("()=>{P(0).scale=1; P(0).autofit=false; render(); applyScale();}"); c.pg.wait_for_timeout(150)
    def hover(sel):
        r = c.pg.query_selector(sel); r.scroll_into_view_if_needed(); bb = r.bounding_box()
        c.pg.mouse.move(bb['x'] + 40, bb['y'] + 8); c.pg.wait_for_timeout(250)
    STY = "(sel)=>[...document.querySelectorAll(sel)].filter(b=>b.getBoundingClientRect().width>0).map(b=>{const s=getComputedStyle(b);return [b.textContent, b.classList.contains('on'), s.backgroundColor+'|'+s.borderStyle+'|'+s.color+'|'+s.fontWeight, (()=>{const rg=document.createRange(); rg.selectNodeContents(b); const ys=new Set([...rg.getClientRects()].filter(q=>q.width>0).map(q=>Math.round(q.top))); return ys.size})()]})"   # 마지막 값 = 단추 안 글자 줄 수
    hover('.row:not(.wine):has(.pick)'); menu = c.js(STY, '.row .namewrap > .rowtools:not(.rowmove) button')
    c.js("()=>{const it=MENU.sheets.flatMap(p=>p.flat()).flatMap(s=>s.wine?s.items:[])[0]; if(it) it.pick=true; render(); applyScale();}"); c.pg.wait_for_timeout(150)
    hover('.row.wine'); wine = c.js(STY, '.row.wine .name > .rowtools:not(.rowmove) button')
    out = {'idle': a, 'edit': e, 'back': z, 'heights': h, 'range308': rng, 'menu308': menu, 'wine308': wine, 'err': c.errs}; c.close(); return out

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
    out['esc'] = c.js("()=>document.querySelectorAll('.gd-tip').length")
    # 310번. 닫기는 안내창과 같은 ✕(.gd-x) · 진행 점은 안내창과 같은 부품(.stepdots) · ✕ 를 누르면 끝(다시 저절로 안 뜸)
    c.js("()=>{delete SETTINGS.guideDone; guideStart();}"); pg.wait_for_timeout(450)
    has = c.js("()=>[!!document.querySelector('.gd-tip .gd-x'), !!document.querySelector('.gd-tip .stepdots'), !document.querySelector('.gd-tip button.skip')]")
    if has[0]: pg.click('.gd-tip .gd-x'); pg.wait_for_timeout(250)
    out['x310'] = has + [c.js("()=>[document.querySelectorAll('.gd-tip,.gd-hole,.gd-block').length, SETTINGS.guideDone === true]")]
    out['err'] = c.errs; c.close()
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
        c.js("()=>{ P(0).seals=[{cell:1, seal:'tri'}, {cell:3, seal:'star', color:'#123456'}]; P(0).arts=[{cell:0, art:'horse', color:'#123456'}]; P(0).art='horse'; document.querySelector('#f-presets').scrollIntoView(); }")   # 302번. 조합을 누르면 그림 칸 · 도장 자리가 처음 값으로
        pg.click(f'#f-presets [data-p="{k}"]'); pg.wait_for_timeout(200)   # 284번. 목록 → 타일
        out['apply'][k] = c.js("(k)=>{const q=PRESETS[k]; return [SETTINGS.font===q.font, SETTINGS.theme===q.theme, (SETTINGS.paper||'grain')===q.paper, (SETTINGS.secStyle||'line')===q.sec, SETTINGS.mark===q.mark, P(0).noren===q.noren, (P(0).seals||[]).every(x=>!('text' in x) && !('color' in x)),   /* 273 → 327번. 글자 도장은 이제 그 가게 상호명을 찍는다 — 조합이 글자 · 색을 박아 넣지 않는지만 본다 */ JSON.stringify((P(0).seals||[]).map(x=>[x.cell,x.seal]))===JSON.stringify(q.seal && q.seal!=='none' ? [[5, q.seal]] : []) && (!q.art || JSON.stringify(P(0).arts)===JSON.stringify(q.art==='none'?[]:[{cell:5, art:q.art}])), (document.querySelector('#f-presets .pl-tile.on')||{}).dataset?.p===k]}", k)
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
    out['check'] = c.js("()=>[!document.querySelector('#st-check').hidden, document.querySelectorAll('#st-ctab :is(input,textarea)').length, document.querySelectorAll('#st-ctab :is(input,textarea).un').length]")
    pg.click('#st-check-go'); pg.wait_for_timeout(150); pg.click('#st-go'); pg.wait_for_timeout(700); pg.keyboard.press('Escape'); pg.wait_for_timeout(150)
    out['menu'] = c.js("()=>MENU.sheets[0].map(col=>col.map(s=>[s.name, s.items.map(i=>i.name+'='+i.price)]))")
    out['err'] = list(c.errs); c.close()
    # 352번 — [이대로 시작] 화면: 사진에서 읽은 것 한 줄 + 점검(중복 · 가격 형식은 코드, 맞춤법은 AI 가 적은 「원문 → 제안」). 메뉴 이름은 안 고친다. 모양이 틀린 점검 줄은 버린다
    c = Ctx(b, 'p_' + f); pg = c.pg
    pg.route('**/api/read', lambda r: r.fulfill(status=200, content_type='application/json', body='{"enabled":false}'))
    ANS352 = "가게: 시험 식당\n콘셉트: 한식\n방향: 세로\n단: 2\n글꼴: 명조\n색: 종이 #f5ecd7 · 글자 #2b2218 · 띠 없음\n점검: 육계장 → 육개장\n점검: 엉터리 문장\n[식사] 1\n육계장 | 9000\n된장찌개 | 8000\n된장찌개 | 8000\n김치찌개 | 90000\n비빔밥 | 8000\n냉면 | 시가\n우동 | 얼마\n"
    pg.click('#st-photo'); pg.wait_for_timeout(400); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', ANS352); pg.click('#st-appgo'); pg.wait_for_timeout(250)
    out['p352c'] = c.js("()=>({hd:[...document.querySelectorAll('#st-cnotes .st-ck .tx')].map(x=>x.textContent).join(' / '), rows:[...document.querySelectorAll('#st-cnotes .st-cnr .go')].map(x=>x.textContent), btn:!!document.querySelector('#st-typo'), vis:document.querySelector('#st-cnotes').offsetHeight>0})")   # 382번. 점검은 이 화면에서
    pg.click('#st-check-go'); pg.wait_for_timeout(300)
    v = c.js("()=>({sum:document.querySelector('#st-readsum').textContent, shown:!document.querySelector('#st-readsum').hidden && !document.querySelector('#st-notes').hidden, hd:document.querySelector('#st-notes').textContent, names:stParsed[0].items.map(i=>i.name), typos:stTypos.length})")
    C = out['p352c']; L = ' / '.join(C['rows'])
    out['p352'] = [v['shown'], all(k in v['sum'] for k in ['한식 식당', '2단', '세로', '명조', '메뉴 7개']), '된장찌개' in L and '같은' in L, '김치찌개' in L and '우동' in L, '육계장' not in L, C['hd'] == '같은 이름: 2건 / 가격 형식: 2건' and len(C['rows']) == 4,
                   '냉면' not in L, v['hd'].startswith('점검할 곳이 4건 남아 있습니다') and '앞 화면' in v['hd'], v['typos'] == 1 and not C['btn'] and C['vis'], v['names'][0] == '육계장']   # 382번. 점검 목록은 읽은 메뉴 확인 화면, 다음 화면에는 남은 건수 한 줄 — 395번. 맞춤법 줄 · 단추는 확인 화면에서 뺐다(읽기의 점검 줄은 AI 창으로 넘어간다)
    out['p352v'] = v
    out['err352'] = list(c.errs); c.close()
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
    q = next((x for x in reqs if '"mode"' not in x['body']), {'url': '', 'body': '', 'hdr': {}})   # 315번. 앞에 방향 묻기(mode:orient)가 먼저 간다 — 읽기 요청을 골라 본다
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
    RULE318 = """(scope)=>{ const root=document.querySelector(scope); if(!root) return ['no '+scope]; const bad=[];   // 318번 · 389번. 규칙 I — 높이 세 단계(안내창 · 위쪽 막대 40 / 꾸미기 창 · AI 창 · 편집 막대 · 목록 줄 안 단추 32 / 종이 모형 안 26) · 8px 둥근 네모(아이콘 단추만 동그라미) · 켜진 칸은 옅은 색 · 글자 12 이상
      const H=(b,h,nm,r)=>{ if (Math.abs(r.height-h) > 0.5) bad.push(nm+' h'+Math.round(r.height)); };
      root.querySelectorAll('button, select').forEach(b=>{ const r=b.getBoundingClientRect(); if(!r.width||!r.height) return; const cs=getComputedStyle(b), nm=(b.getAttribute('aria-label')||b.textContent||'').trim().slice(0,12);
        if (root.matches('dialog')){
          if (b.closest('.st-cpaper, .st-opt, .st-row, .st-swb') || b.matches('.st-opt, .st-row, .st-swb')) return;   // 종이 모형(26 — 따로 잼) · 고르는 카드
          if (b.matches('.st-cnr .go')){ if (cs.textDecorationLine !== 'none') bad.push(nm+' 밑줄 글 단추'); return; }   // 389번. 목록 줄 — 줄 전체가 누르는 자리(글자만 있는 단추 아님)
          const rad=parseFloat(cs.borderTopLeftRadius), circle = cs.borderTopLeftRadius.endsWith('%') || rad >= r.height/2 - 0.5;
          const icon = b.matches('.dlg-x, .st-icon, .st-rot button'), shape = icon ? circle : (Math.abs(rad-8) <= 0.5 || (b.closest('.st-seg') && rad === 0));
          H(b, b.closest('.st-cnotes') ? 32 : 40, nm, r); if (!shape) bad.push(nm+' 모서리');   // 389번. 목록 줄 안 단추는 32 단계
          if (b.classList.contains('on') && cs.backgroundColor==='rgb(36, 28, 18)') bad.push(nm+' 켜짐 검정');
          if (!b.classList.contains('on') && !b.matches('.bt-fill') && cs.backgroundColor==='rgb(224, 207, 168)') bad.push(nm+' 켜지지 않았는데 옅은 색');
        } else if (root.matches('#barwrap')){   // 389번. 위쪽 막대 40 · 편집 막대 32 · 켜지지 않은 단추는 채우지 않는다
          if (b.closest('#filemenu')) return;
          H(b, b.closest('#editbar') ? 32 : 40, nm, r);
          const on = b.classList.contains('on') || b.getAttribute('aria-pressed')==='true', bg = cs.backgroundColor;
          if (!on && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') bad.push(nm+' 켜지지 않았는데 채움');
        } else {   // 꾸미기 창 · AI 창
          if (parseFloat(cs.fontSize) < 12 && !b.closest('.wfrow')) bad.push(nm+' '+cs.fontSize);
          if (b.matches('.ptab-btn')){ H(b, 40, nm, r); return; }   // 탭 40
          if (b.matches('.pl-tile, .aip-it, .tbtn') || b.closest('.pgrid, .pcells, .pl-presets, .bottles, .bpick') || b.tagName === 'SELECT' && b.closest('.wfrow')) return;   // 타일 · 칸 그림 · 병 고르기(카드) · 글자 단추(규칙 I 335번 ⑤)는 높이 규칙 밖
          const grp = b.closest('.st-pseg, #pgpick, .stepg');
          if (grp){ H(grp, 32, nm+'(묶음)', grp.getBoundingClientRect()); return; }   // 나뉜 고르기 · [− | +] 는 묶음 바깥이 32
          H(b, 32, nm, r);
        }
      }); return [...new Set(bad)]; }"""
    # 312번 — 가게 이름이 없는 답(알프스 원래 사진처럼): 칸 안내 · 영업시간 칸(? 는 노랗게) · 이름 없는 분류(노랗게) · 추천 ★ · 분류 안내 · 바닥 글 ·
    #         [다음] 뒤 「사진처럼」이 골라져 있고 미리보기가 읽은 종이색 · 시작 뒤 메뉴판에 고친 값이 그대로 · 많은 메뉴가 확인 화면 종이에 스크롤 없이
    ANSB = ("영업: 점심 12:00 - 14:00 · 저녁 17:00 - 24:00? (가끔 변동)\n방향: 가로\n단: 2\n글꼴: 궁서\n색: 종이 #f3ecd9 · 글자 #222222 · 띠 없음\n"
            "[] 1\n알프스 카레파스타 | 11000 | 추천\n깻잎새우 파스타 | 11000\n※ *곱빼기 가능?\n[하이볼(280ml)] 2\n블론드 하이볼 | 8000\n버번 하이볼 | 가격문의\n바닥: 모든 메뉴 포장 가능합니다")
    orients = []
    def route_b(text):
        def h(r):
            if r.request.method == 'GET': r.fulfill(status=200, content_type='application/json', body='{"enabled":true}'); return
            if '"mode"' in (r.request.post_data or ''): orients.append(1)
            r.fulfill(status=200, content_type='application/json', body=json.dumps({'text': text, 'model': 'test'}))
        return h
    c = Ctx(b, 'p_' + f, 1600, 1000); pg = c.pg; pg.route('**/api/read', route_b(ANSB))
    try:
        pg.click('#st-photo'); pg.wait_for_timeout(300)
        with pg.expect_file_chooser() as fc: pg.click('#st-pic')
        fc.value.set_files(png); pg.wait_for_timeout(500)
        nfc = []; pg.on('filechooser', lambda x: nfc.append(1))   # 313번. 돌리기는 사진 고르기 창을 안 연다 · 돌린 사진이 가로로(600 × 800 → 800 × 600)
        r318 = {'사진': c.js(RULE318, '#start')}
        BP = "()=>{const r=document.querySelector('#st-rotr').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top)]}"; bp0 = c.js(BP)
        pg.click('#st-rotr'); pg.wait_for_timeout(300)
        stay314 = c.js(BP) == bp0   # 314번. 돌려도 단추가 제자리(180° 는 같은 단추를 두 번)
        rot = c.js("async()=>{ const i=new Image(); i.src=stPic; await i.decode(); return [i.naturalWidth, i.naturalHeight] }")
        q313 = [len(nfc) == 0, rot == [800, 600]]
        col315 = c.js("()=>{ const a=document.querySelector('#st-rot').getBoundingClientRect(), b=document.querySelector('#st-pic').getBoundingClientRect(); return Math.abs((a.left+a.right)/2-(b.left+b.right)/2) <= 3 && b.top >= a.bottom - 1 }")   # 315 → 316번. 사진 바꾸기는 돌리기 밑에 혼자 가운데
        POS325 = "(q)=>{ const R=s=>{const e=document.querySelector(s); if(!e||!e.offsetParent) return null; const r=e.getBoundingClientRect(); return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]}; return [R(q[0]), R(q[1]), R(q[2])] }"   # 325번. [←, 제목, 주 단추]
        q317 = c.js("""()=>{ const a=document.querySelector('#st-rotl').getBoundingClientRect(), b=document.querySelector('#st-rotr').getBoundingClientRect(), i=document.querySelector('.st-picwrap').getBoundingClientRect();
          return [ Math.abs(a.top-b.top) < 1 && a.width <= 44 && a.height <= 44, b.right - a.left <= i.width, Math.abs((a.left+b.right)/2 - (i.left+i.right)/2) <= 2 ] }""")   # 317번. 동그란 아이콘 단추 한 쌍 · 사진 폭 안 · 사진 가운데
        pos325 = [c.js(POS325, ['#st-read-back', '#st-read .st-head h3', '#st-gemgo'])]   # 325번. ① 사진
        top317 = c.js("()=>Math.round(document.querySelector('#start').getBoundingClientRect().top)")
        q314 = [stay314] + c.js("""()=>{ const im=document.querySelector('#st-picimg').getBoundingClientRect(), r=document.querySelector('#st-rot').getBoundingClientRect(), t=document.querySelector('#st-rot').textContent;
          return [ r.top >= im.bottom - 1 && Math.abs((r.left + r.right) / 2 - (im.left + im.right) / 2) <= 3, !/[↺↻]/.test(t) && document.querySelector('#st-rotl').getAttribute('aria-label')==='왼쪽으로 돌리기' && document.querySelector('#st-rotr').getAttribute('aria-label')==='오른쪽으로 돌리기' && !!document.querySelector('#st-rotl').title, !!document.querySelector('#st-rotl svg') ] }""")   # 314번 → 316번. 돌리기는 사진 바로 밑 가운데 · 그린 그림 + 글자(읽어 주는 이름은 「왼쪽으로 돌리기」)
        pg.click('#st-rotl'); pg.wait_for_timeout(200)
        pg.click('#st-gemgo'); pg.wait_for_timeout(800)
        q314 += c.js("""()=>{ const h=document.querySelectorAll('#st-chours input')[3], n=document.querySelector('#st-ctab :is(input,textarea).st-cnl');
          return [ !!h && h.value==='17:00 - 24:00 (가끔 변동)', !!n && n.value==='곱빼기 가능' && n.classList.contains('un') ] }""")
        q314 += c.js("()=>{ const r=parseMenuText('[a]\\nx | 1\\n바닥: *포장 가능?'); return [ r.foot[0]==='*포장 가능' && r.footUn[0]===true ] }")
        c.js("()=>{ stTypos.push({from:'카레파스타',to:'카레 파스타'}); drawCkNotes(); }"); pg.wait_for_timeout(100)   # 389번. 점검 줄([적용] [무시])이 있는 화면으로 잰다 — 없는 화면만 재서 30px 단추를 못 잡았다
        r318['확인'] = c.js(RULE318, '#start')
        c.js("()=>{ stTypos.pop(); drawCkNotes(); }"); pg.wait_for_timeout(100)
        q317 += [c.js("()=>Math.round(document.querySelector('#start').getBoundingClientRect().top)") == top317]
        pos325.append(c.js(POS325, ['#st-check-back', '#st-check .st-head h3', '#st-check-go']))   # 325번. ② 확인
        seg319 = c.js("()=>[...document.querySelectorAll('#st-ccount .st-seg button')].every(b=>{ const r=b.getBoundingClientRect(); return r.width <= 84 && Math.abs(r.height-40) < 1 })")   # 319번. 고르기는 높이 40 · 폭은 글자만큼   # 317번. 확인 화면도 사진 창과 같은 높이에서 연다
        q313 += c.js("""()=>{ const w=document.querySelector('#st-ccount .st-warn'), u=document.querySelector('#st-chours input.un');
          return [ !!w && /찾지 못했/.test(w.textContent) && getComputedStyle(w).color==='rgb(163, 50, 31)', !!u && getComputedStyle(u).backgroundColor==='rgb(255, 225, 122)' ] }""")
        pg.click('#st-check-go'); pg.wait_for_timeout(300)   # 313번. 이름 빈 분류가 남으면 한 번 알리고 머문다
        q313 += c.js("()=>[ !document.querySelector('#st-check').hidden, /이름이 빈 분류/.test(document.querySelector('#undo .t').textContent) ]")
        q = c.js("""()=>{ const H=document.querySelector('#st-chours'), F=document.querySelector('#st-cfoot'), T=document.querySelector('#st-ctab');
          const sec=T.querySelector('.st-csec'), k=T.querySelector('button.st-cpk');
          return [ document.querySelector('#st-cshop').placeholder==='가게 이름',   /* 313번. 못 찾은 안내는 칸 밖 붉은 줄로 옮겼다 */ !!H && H.querySelectorAll('input').length === 4, !!H && H.querySelectorAll('input.un').length === 4,
                   !!sec && sec.value==='' && sec.classList.contains('un'), !!k && k.classList.contains('on'), [...T.querySelectorAll('.st-cnl')].map(x=>x.value).join('|')==='곱빼기 가능',
                   F ? [...F.querySelectorAll('textarea')].map(x=>x.value).join('|')==='모든 메뉴 포장 가능합니다' : false ] }""")
        c.js("""()=>{ const t=document.querySelectorAll('#st-chours input')[3]; t.value='17:00 - 24:00 (가끔 변동)'; const s=document.querySelector('#st-ctab :is(input,textarea).st-csec'); s.value='식사'; }""")
        pg.click('#st-check-go'); pg.wait_for_timeout(300)
        q315 = [col315, len(orients) == 0]   # 315번. 직접 돌렸으면 방향을 묻지 않는다
        q315 += c.js("()=>{ const r=parseMenuText('[a]\\nx | 1\\n※ 가\\\\n나\\n바닥: 다\\\\n라'); return [ JSON.stringify(r[0].notes)==='[\"가\",\"나\"]' && JSON.stringify(r.foot)==='[\"다\",\"라\"]' ] }")
        r318['정하기'] = c.js(RULE318, '#start')
        pos325.append(c.js(POS325, ['#st-back', '#st-setup .st-head h3', '#st-go']))   # 325번. ③ 정하기
        same = lambda k, f: len({tuple(f(x[k])) for x in pos325 if x[k]}) == 1 and all(x[k] for x in pos325)
        out['p325'] = [same(0, lambda v: v), same(1, lambda v: v[:2]), same(2, lambda v: [v[1], v[2], v[3]]), c.js("()=>[...document.querySelectorAll('#st-setup input[type=file]')].every(e=>!e.offsetParent)")]   # ← 같은 자리 · 제목 같은 자리 · 주 단추 위 · 오른쪽 · 아래 같음 · 숨긴 파일 칸 안 보임
        q313 += c.js("()=>{ const t=document.querySelector('#st-topfrom'); return [ t.classList.contains('warn') && getComputedStyle(t).color==='rgb(163, 50, 31)' ] }")
        q += c.js("""()=>[ !!document.querySelector('#st-sw .st-swb[data-p="photo"].on'), /찾지 못했/.test(document.querySelector('#st-topfrom').textContent) && !document.querySelector('#st-topfrom').hidden,
                       getComputedStyle(document.querySelector('#st-prev')).backgroundColor==='rgb(243, 236, 217)' ]""")
        pg.click('#st-go'); pg.wait_for_timeout(700); pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
        q += c.js("""()=>{ const all=MENU.sheets[0].flat(), s0=all.find(x=>x.name==='식사')||{}, it=(s0.items||[])[0]||{};
          return [ MENU.hours.length===2 && MENU.hours[1].time==='17:00 - 24:00 (가끔 변동)' && !('un' in MENU.hours[1]), it.pick===true && !('un' in it),
                   JSON.stringify(s0.notes||null)==='["곱빼기 가능"]', F(0).notes.includes('모든 메뉴 포장 가능합니다'), SETTINGS.font==='gungseo' ] }""")
        r318['꾸미기 창'] = []
        for k in range(c.js("()=>document.querySelectorAll('#ptabs .ptab-btn').length")):   # 389번. 탭마다(감춘 탭의 단추는 크기가 0이라 안 잡힌다)
            c.js("(k)=>document.querySelectorAll('#ptabs .ptab-btn')[k].click()", k); pg.wait_for_timeout(150); r318['꾸미기 창'] += c.js(RULE318, '#panel')
        r318['꾸미기 창'] = sorted(set(r318['꾸미기 창']))
        pg.mouse.move(2, 990); pg.wait_for_timeout(100); r318['위쪽 막대'] = c.js(RULE318, '#barwrap')   # 389번. 올림 색을 채움으로 읽지 않게
        pg.mouse.move(2, 990); c.js("()=>document.querySelector('#b-ai').click()"); pg.wait_for_timeout(300); r318['AI 창'] = c.js(RULE318, '#aipanel'); c.js("()=>document.querySelector('#b-ai').click()"); pg.wait_for_timeout(200)
        out['rule318'] = r318
        c.js("(sel)=>{const e=document.querySelector(sel), t=e.closest('.ptab'); panelTab=t.dataset.tab; if (e.closest('.pblock[data-kind=wine]')) panelPage=Math.max(0, MENU.sheets.findIndex((_,i)=>sheetKind(i)!=='menu')); syncPageTabs(); syncPage();}", '#g-art'); pg.wait_for_timeout(300)   # 332번 — 꾸밈이 든 탭을 찾아 연다 · 319번. 그림 · 도장 격자 — 빈 칸에 ＋ · 흐린 [모든 그림에 같게]에 까닭
        out['p319'] = c.js("()=>{ const bs=[...document.querySelectorAll('#g-art .pcells > button')]; return [ bs.length===6 && bs.every(b=>!getComputedStyle(b,'::before').content.includes('＋')), document.querySelector('#b-artsame').disabled ? /두 칸/.test(document.querySelector('#b-artsame').title) : true ] }")   # 319 → 321 → 323번. 격자에 ＋ 없음(누르면 칸을 고를 뿐) · 흐린 [모든 칸에 같게]에 까닭
        out['p320'] = c.js("""()=>{ const fit=document.querySelector('#b-fit'), cp=document.querySelector('#b-copypage'), g=document.querySelector('#g-art');
          return [ !!fit && fit.type==='checkbox' && fit.classList.contains('m3sw'), !document.querySelector('#g-seal') && !document.querySelector('#f-sealhere'), !!cp && !!cp.closest('#pgbar') ] }""")   # 320 → 323 → 334번. [한 장에 맞춤] 스위치 · 격자 하나(도장 격자 · 칸 스위치 없음) · [모든 장에 같게]는 고칠 장 줄 안(334번에 격자 밑에서 옮김)
        out['p329'] = c.js("""()=>{ const sel=document.querySelector('#f-art'), gs=[...sel.querySelectorAll('optgroup')], vals=[...sel.options].map(o=>o.value).filter(v=>v!=='none');
          const keys=Object.keys(ART).filter(k=>k!=='none'), NEW=['ttuk','bapsujeo','bibim','jeon','coffee','croissant','cake','bingsu','teapot','tteok','gimbap','eomuk','ramyeon','chicken','fries','skewer','lantern'];
          const P0=P(panelPage), keep=JSON.stringify(P0.arts); let drawn=0;
          for (const k of NEW){ P0.arts=[{cell:5, art:k}]; render(); const a=document.querySelector('.sheet[data-pi="'+panelPage+'"] .art[data-cell="5"] svg') || document.querySelector('.sheet[data-pi="'+panelPage+'"] .art svg'); const r=a && a.getBBox ? a.getBBox() : {width:0}; if (r.width > 100) drawn++; }
          P0.arts=JSON.parse(keep); render();
          return [ gs.length===6 && gs.every(g=>g.children.length>=4), vals.length===keys.length && keys.every(k=>vals.includes(k)), drawn===NEW.length ] }""")   # 329번. 그림 묶음 여섯(넷 이상씩) · 목록 = 그림 정의 · 새 그림 16 이 종이에 그려짐
        out['p327'] = c.js("""()=>{ const P0=P(panelPage), cells=[...document.querySelectorAll('#g-art .pcells > button')], fs=document.querySelector('#f-seal'), tx=document.querySelector('#f-sealtx'), set=v=>{ fs.value=v; fs.dispatchEvent(new Event('change')); };
          const T=k=>{ const d=document.querySelector('.sheet[data-pi="'+panelPage+'"] .seal[data-cell="'+k+'"]'); return d ? [...d.querySelectorAll('text')].map(t=>t.textContent).join('') : null };
          MENU.brand.shop='솔밭식당'; cells[3].click(); set('word'); const dflt=T(3)==='솔밭식당' && tx.placeholder.startsWith('솔밭식당') && !tx.disabled;
          tx.value='福 '; tx.dispatchEvent(new Event('input')); const own=T(3)==='福' && P0.seals.find(x=>x.cell===3).text==='福';
          set('star'); const sym=tx.disabled && !('text' in P0.seals.find(x=>x.cell===3)) && T(3)==='';
          const q={seals:[{cell:1,seal:'rword',text:'가 나 다 라 마'},{cell:2,seal:'tri',text:'x'}]}; normSeals(q,[]); const norm=JSON.stringify(q.seals)==='[{"cell":1,"seal":"rword","text":"가나다라"},{"cell":2,"seal":"tri"}]';
          const lat=sealSvg('sq','CAFE').includes('>CA<') && sealSvg('sq','CAFE').includes('>FE<'), ko4=(()=>{ const d=document.createElement('div'); d.innerHTML=sealSvg('sq','솔밭식당'); const ts=[...d.querySelectorAll('text')].map(t=>[+t.getAttribute('x'),+t.getAttribute('y'),t.textContent]); return ts[0][2]==='솔' && ts[1][2]==='밭' && ts[0][1]===ts[1][1] && ts[0][0]<ts[1][0] && ts[2][2]==='식' && ts[2][1]>ts[0][1] })(),   /* 328번. 넉 자 가로 차례 */ noAlps=!JSON.stringify(SEALS).includes('알프스');
          set('none'); return [dflt, own, sym, norm, lat && ko4, noAlps] }""")   # 327번. 글자 도장 — 비우면 상호명 · 적은 글자 · 기호 도장엔 글자 없음 · 정리(4자 · 빈칸 · 기호 도장 글자 버림) · 영문 가로 · 「알프스」가 박힌 도장 없음
        out['p326'] = c.js("""()=>{ const hid=[...document.querySelectorAll('#art-cell .cellblk[hidden]')]; hid.forEach(x=>x.hidden=false);   /* 340번 — 도장 · QR 은 한 줄로 고르고 안 고른 묶음은 숨는다 · 재는 동안만 펼친다 */
          const b=[...document.querySelectorAll('#art-cell .cellblk')].filter(x=>!x.classList.contains('qrblk') && !x.classList.contains('cornerblk')), h=b.map(x=>(x.querySelector('.blkhd')||{}).textContent);   /* 337번 — QR 묶음은 t58 */
          const r=[ b.length===2 && h[0]==='그림' && h[1]==='도장', b.length===2 && b[1].getBoundingClientRect().top >= b[0].getBoundingClientRect().bottom && getComputedStyle(b[1]).borderTopWidth==='1px' /* 403번 — 도장 묶음도 상자(구분선이 아니라 테두리). 모퉁이 아래에 이어 붙으면 점선 */, !!b[0] && b[0].contains(document.querySelector('#f-art')) && !!b[1] && b[1].contains(document.querySelector('#f-seal')) && b[1].contains(document.querySelector('#c-seal')) ]; hid.forEach(x=>x.hidden=true); return r }""")   # 326번. 칸 안 그림 · 도장 두 묶음(제목 · 구분선)
        out['p323'] = c.js("""()=>{ const P0=P(panelPage), cells=[...document.querySelectorAll('#g-art .pcells > button')], fs=document.querySelector('#f-seal'), set=v=>{ fs.value=v; fs.dispatchEvent(new Event('change')); };
          P0.seals=[]; render(); syncPage(); cells[0].click(); set('tri'); cells[5].click(); set('star'); const two=JSON.stringify(P0.seals.map(x=>[x.cell,x.seal]))==='[[0,"tri"],[5,"star"]]';
          const gridShows=!!cells[0].querySelector('.psl') && !!cells[5].querySelector('.psl') && !cells[2].querySelector('.psl');
          const paper=[...document.querySelectorAll('.sheet[data-pi="'+panelPage+'"] .seal:not(.blank)')].map(d=>+d.dataset.cell).join(',')==='0,5';
          cells[0].click(); const cs=document.querySelector('#c-seal'); cs.value='#1155cc'; cs.dispatchEvent(new Event('input')); cs.dispatchEvent(new Event('change'));
          const col=P0.seals.find(x=>x.cell===0).color==='#1155cc' && !('color' in P0.seals.find(x=>x.cell===5));
          set('none'); const one=JSON.stringify(P0.seals.map(x=>x.cell))==='[5]' && fs.value==='none' && document.querySelector('#c-seal').disabled;
          const H=()=>document.querySelector('.panel').scrollHeight; cells[2].click(); const h1=H(); cells[1].click(); const h2=H();
          return [ two, gridShows, paper, col, one, h1===h2 /* 344번 — 위 · 가운데 칸끼리는 같다(아래 두 칸은 모퉁이 줄이 더 있다) */, document.querySelector('#art-cellname').textContent===CELL_NAMES[1]+' 칸' ] }""")   # 323번. 도장도 칸마다 — 두 칸에 다른 모양 · 격자에 보임 · 종이에 그 칸만 · 색은 그 칸만 · 없음이면 그 칸만 빠지고 색 흐림 · 칸을 바꿔도 창 길이 같음 · 칸 이름
        out['p322'] = c.js("""()=>{ const P0=P(panelPage), H=()=>document.querySelector('.panel').scrollHeight, cells=[...document.querySelectorAll('#g-art .pcells > button')];
          if (!(P0.arts||[]).length){ cells[0].click(); const fa=document.querySelector('#f-art'); fa.value='horse'; fa.dispatchEvent(new Event('change')); }
          const withArt=cells.findIndex((b,k)=>artAt(P0,k)), empty=cells.findIndex((b,k)=>!artAt(P0,k)); if (withArt<0||empty<0) return ['no cells'];
          cells[withArt].click(); const h1=H(); cells[empty].click(); const h2=H(); const dis=document.querySelector('#c-art').disabled && document.querySelector('#f-artop').disabled && !document.querySelector('#art-opts').hidden;
          return [ h1===h2, dis ] }""")   # 322번. 그림 있는 칸 ↔ 빈 칸에서 꾸미기 창 길이가 같다 · 딸린 손잡이는 접지 않고 흐리게
        out['p312'] = q; out['p313'] = q313; out['p314'] = q314; out['p315'] = q315; out['p317'] = q317; out['seg319'] = seg319
    except Exception as e:
        out['p312'] = 'fail: ' + str(e)[:200]
    out['err'] += c.errs; c.close()
    # 315번. 돌리지 않은 사진 → 먼저 방향 묻기(작은 사진) → 답 90 → 돌린 사진(800 × 600)으로 읽기 · 확인 화면 사진도 · 알림
    sent = []
    def route_o(r):
        if r.request.method == 'GET': r.fulfill(status=200, content_type='application/json', body='{"enabled":true}'); return
        bd = json.loads(r.request.post_data or '{}'); sent.append(bd)
        r.fulfill(status=200, content_type='application/json', body=json.dumps({'rot': 90} if bd.get('mode') == 'orient' else {'text': ANS54}))
    c = Ctx(b, 'p_' + f, 1600, 1000); pg = c.pg; pg.route('**/api/read', route_o)
    try:
        pg.click('#st-photo'); pg.wait_for_timeout(300)
        with pg.expect_file_chooser() as fc: pg.click('#st-pic')
        fc.value.set_files(png); pg.wait_for_timeout(500)
        c.js("()=>{ window.__busy=[]; const t=document.querySelector('#st-busytx'); new MutationObserver(()=>{ if (t.textContent) __busy.push(t.textContent.replace(/ \\d+초$/, '')) }).observe(t, {childList:true, characterData:true, subtree:true}) }")
        pg.click('#st-gemgo'); pg.wait_for_timeout(2600)
        SZ = "async(u)=>{ const i=new Image(); i.src=u; await i.decode(); return [i.naturalWidth, i.naturalHeight] }"
        o = [b2 for b2 in sent if b2.get('mode') == 'orient']; rd = [b2 for b2 in sent if not b2.get('mode')]
        dims = [c.js(SZ, x) for x in o[0].get('images', [])] if o else []
        out['orient315'] = [len(o) == 1, len(dims) == 4 and max(max(d) for d in dims) <= 384 and [d[0] > d[1] for d in dims] == [False, True, False, True], bool(rd) and c.js(SZ, rd[0]['image']) == [800, 600],
                            c.js("async()=>{ const i=document.querySelector('#st-cimg'); await i.decode(); return [i.naturalWidth, i.naturalHeight] }") == [800, 600],
                            '돌려서 읽었습니다' in c.js("()=>document.querySelector('#undo .t').textContent")]
        bz = c.js("()=>[...new Set(__busy)]")   # 316번. 사진 위 막의 단계 글 — 방향 → 돌렸습니다 → 읽는 중, 끝나면 막이 사라진다
        out['busy316'] = [bz[:1] == ['사진 방향을 보는 중…'] and '오른쪽으로 90° 돌렸습니다' in bz and bz[-1] == '메뉴를 읽는 중…', c.js("()=>document.querySelector('#st-busy').hidden")]
    except Exception as e:
        out['orient315'] = 'fail: ' + str(e)[:200]
    out['err'] += c.errs; c.close()
    big = "방향: 가로\n단: 2\n" + "".join(f"[분류{k}] {1 + (k >= 2)}\n" + "".join(f"메뉴 이름 {k}-{i} | {9000 + i * 1000}\n" for i in range(9)) for k in range(4))
    c = Ctx(b, 'p_' + f, 1600, 1000); pg = c.pg; pg.route('**/api/read', route_b(big))
    try:
        pg.click('#st-photo'); pg.wait_for_timeout(300)
        with pg.expect_file_chooser() as fc: pg.click('#st-pic')
        fc.value.set_files(png); pg.wait_for_timeout(500); pg.click('#st-gemgo'); pg.wait_for_timeout(900)
        fit = c.js("()=>{ const p=document.querySelector('.st-cpaper'), t=document.querySelector('#st-ctab'); return [p.scrollHeight - p.clientHeight <= 1, +(t.style.zoom||1), document.querySelectorAll('#st-ctab :is(input,textarea)').length] }")
        out['fit312'] = fit
        # 313번. 방향 · 단 손잡이 — 세로를 누르면 종이가 세로, 1단을 누르면 한 단 · 그때도 창 자체에는 스크롤 없음(사진 칸 높이 여유)
        pw0 = c.js("()=>Math.round(document.querySelector('.st-cphoto').getBoundingClientRect().width)")
        pg.click('.st-cform [data-o="portrait"]'); pg.wait_for_timeout(300)
        o1 = c.js("()=>[ !document.querySelector('.st-cpaper').classList.contains('land'), document.querySelector('#start').scrollHeight - document.querySelector('#start').clientHeight <= 1, document.querySelector('.st-cform [data-o=\"portrait\"]').classList.contains('on') ]")
        pg.click('.st-cform [data-c="1"]'); pg.wait_for_timeout(300)
        o1 += c.js("()=>[ document.querySelector('#st-ctab').style.gridTemplateColumns.startsWith('repeat(1'), document.querySelectorAll('#st-ctab :is(input,textarea)').length === 76 ]")
        out['form313'] = o1
        pw1 = c.js("()=>Math.round(document.querySelector('.st-cphoto').getBoundingClientRect().width)")
        pg.click('.st-cform [data-c="4"]'); pg.wait_for_timeout(300)
        out['form314'] = [abs(pw0 - pw1) <= 1 and pw0 > 0, c.js("()=>document.querySelector('#st-ctab').classList.contains('tight')")]   # 314번. 사진 칸 폭은 방향과 상관없이 · 4단이면 가격 칸 좁게
    except Exception as e:
        out['fit312'] = out.get('fit312') or 'fail: ' + str(e)[:200]; out['form313'] = 'fail: ' + str(e)[:200]
    out['err'] += c.errs; c.close()
    # 276번 — 메뉴판의 요청 글(READ_PROMPT)과 서버 함수의 요청 글(PROMPT)이 같은가. 서버 함수 파일을 찾으면 본다
    here = os.path.dirname(os.path.abspath(__file__)); cand = [os.path.join(here, 'api', 'read.js'), os.path.join(here, '..', 'api', 'read.js')]
    fn = next((p for p in cand if os.path.exists(p)), None); out['prompt_same'] = None
    if fn:
        def arr(t, head):
            i = t.find(head); j = t.find('].join', i); return json.loads(t[i + len(head):j + 1]) if i >= 0 else None
        out['prompt_same'] = arr(src, 'const READ_PROMPT = ') == arr(open(fn, encoding='utf-8').read(), 'const PROMPT = ')
    return out

# ───────────────────────── 56. 가로 모드(304번) — 맨 위 글자 크기 · 알약이 여백선 안 · 좁은 단의 분류 도구 · 빈 영업시간 선 · 영업시간 읽기
L56 = [["회 · 모둠", 5], ["식사", 3], ["구이 · 튀김", 4], ["안주", 3], ["주류", 4], ["음료", 3]]
def t56(b, f):
    out = {}
    for o in ('portrait', 'landscape'):
        c = Ctx(b, f, W=1700)
        out['top_px_' + o] = c.js("""(o)=>{SETTINGS.orient=o; SETTINGS.topMode='text'; MENU.brand.top='바다향 횟집'; syncControls(); applyLook(); render(); applyScale();
          return +parseFloat(getComputedStyle(document.querySelector('.sheet .noren .logo.txt')).fontSize).toFixed(1)}""", o)
        c.close()
    for o in ('portrait', 'landscape'):
        for al in ('left', 'right'):   # 알약 — 칠한 폭(그림자 .72em)까지 여백선 안
            c = Ctx(b, f, W=1700)
            out[f'pill_{o}_{al}'] = c.js("""([o,al])=>{SETTINGS.orient=o; applyPresetTo(SETTINGS, MENU, 'bunsik'); SETTINGS.secAlign=al; syncControls(); applyLook(); render(); applyScale(); toggleEdit();   // 여백선은 편집 중에만 그려진다(종이 자리는 같다)
              const sh=document.querySelector('.sheet'), g=sh.querySelector('.guide').getBoundingClientRect(); let w=0;
              sh.querySelectorAll('section > .sec-head h2 .hv').forEach(h=>{const r=h.getBoundingClientRect(), em=parseFloat(getComputedStyle(h).fontSize)*.72;
                w=Math.max(w, g.left-(r.left-em), (r.right+em)-g.right)}); return +w.toFixed(1)}""", [o, al])
            c.close()
    c = Ctx(b, f, W=1700)   # 가로 4단 — 분류 도구가 칸 안
    c.js("""(L)=>{const cols=[[],[],[],[]]; L.forEach((s,i)=>cols[Math.floor(i*4/L.length)].push({name:s[0], items:Array.from({length:s[1]},(_,k)=>({name:'메뉴'+k, price:1000}))}));
      MENU.sheets=[cols]; MENU.feet=[{notes:[],origin:''}]; SETTINGS.pages=[pageDefaults(0)]; SETTINGS.orient='landscape'; syncControls(); applyLook(); render(); applyScale(); toggleEdit();}""", L56)
    c.pg.wait_for_timeout(300); outs = []
    for i, hd in enumerate(c.pg.query_selector_all('.sheet section > .sec-head')):
        hd.scroll_into_view_if_needed(); bb = hd.bounding_box(); c.pg.mouse.move(bb['x'] + 4, bb['y'] + bb['height'] / 2); c.pg.wait_for_timeout(50)
        outs.append(c.js("""(i)=>{const hd=document.querySelectorAll('.sheet section > .sec-head')[i], s=hd.closest('section').getBoundingClientRect();
          const bs=[...hd.querySelectorAll('.rowtools button, .rowtools select')].filter(x=>x.offsetWidth).map(x=>x.getBoundingClientRect());
          return Math.round(Math.max(0, ...bs.map(r=>Math.max(s.left-r.left, r.right-s.right))))}""", i))
    out['tools_out_4col'] = max(outs or [0]); out['err'] = list(c.errs); c.close()
    c = Ctx(b, f)   # 빈 영업시간 — 완성본에 선이 안 찍힌다
    out['empty_hours_border'] = c.js("""()=>{MENU.hours=[]; render(); applyScale(); const h=document.querySelector('.sheet .hours'); const cs=getComputedStyle(h);
      return [cs.borderTopColor, cs.borderBottomColor].every(x=>x==='rgba(0, 0, 0, 0)' || x==='transparent')}""")
    out['hours_parse'] = c.js("""()=>{const r=parseMenuText('가게: 바다향\\n영업: 점심 11:00 - 15:00 · 저녁 17:00 - 23:00\\n[회] 1\\n광어회 | 35000'); return r.hours || null}""")
    out['err'] += c.errs; c.close()
    return out

# ───────────────────────── 57. 번역(306 · 307번) — 가짜 서버로: 언어 고르기 · 빈 칸만 채움 · 적힌 칸이 있으면 묻기(빈 칸만 · 전부 다시) · 고친 칸 안 덮음 · 와인 카드 뺌 · 되돌리기 · 옛 영문 병기 · 저장 왕복 · 서버 함수
NODE57 = r"""
const h = require(process.argv[2]); let next = null; global.fetch = async (u, o) => next(JSON.parse(o.body));
const ok = a => ({ status:200, ok:true, json:async()=>({ candidates:[{content:{parts:[{text:JSON.stringify(a)}]}}] }), text:async()=>'' });
const run = req => new Promise(d => { const res = { c:0, setHeader(){}, status(x){this.c=x; return this}, json(j){d([this.c,j])}, end(){d([this.c])} }; h(req,res); });
const P = (b, o='null') => ({ method:'POST', headers:{origin:o}, body:b });
console.log = (l => (...a) => { if (!String(a[0]).startsWith('{"route"')) l(...a); })(console.log);
(async () => { process.env.GEMINI_API_KEY='k'; const R = {};
  next = () => ok(['Kimchi stew']); R.ok = (await run(P({lang:'en', texts:['김치찌개']})))[0];
  R.origin = (await run(P({lang:'en', texts:['a']}, 'https://x.example')))[0];
  R.lang = (await run(P({lang:'fr', texts:['a']})))[0];
  R.many = (await run(P({lang:'en', texts:Array(151).fill('a')})))[0];
  R.long = (await run(P({lang:'en', texts:['가'.repeat(121)]})))[0];
  next = () => ok(['a']); R.count = (await run(P({lang:'zh', texts:['a','b']})))[0];
  next = () => ok(['x'.repeat(9000)]); R.clip = (await run(P({lang:'ja', texts:['소주']})))[1].texts[0].length;
  process.env.READ_ENABLED = 'off'; R.off = (await run(P({lang:'en', texts:['a']})))[0];
  process.stdout.write(JSON.stringify(R));
})();"""
def t57(b, f):
    out = {'err': []}
    sent = []
    def fake(route):
        if route.request.method == 'GET': route.fulfill(status=200, content_type='application/json', body='{"enabled":true}'); return
        bd = json.loads(route.request.post_data); sent.append(bd)
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'texts': [bd['lang'].upper() + ':' + t for t in bd['texts']]}))
    c = Ctx(b, f, dl=True); pg = c.pg; pg.route('**/api/translate', fake)
    try:
        has = c.js("()=>!!document.querySelector('#f-lang')"); out['control'] = has
        if not has: raise RuntimeError('언어 고르기 없음')
        EN = "()=>JSON.stringify(MENU.sheets.map(s=>s.map(c=>c.map(x=>[x.en,(x.items||[]).map(i=>i.en)]))))"
        en0 = c.js(EN)
        pg.click('#b-edit'); pg.wait_for_timeout(200)
        out['start'] = c.js("()=>[L2(), document.querySelector('#f-tr').disabled]")
        pg.evaluate("()=>{const l=document.querySelector('#f-lang'); l.value='zh'; l.dispatchEvent(new Event('change',{bubbles:true}));}"); pg.wait_for_timeout(200)   # 332번 — 외국어는 [넣을 것]   # 354번 — 번역은 [AI] 창 안(꾸미기 창 탭이 아니다). 창을 열지 않고 값을 바꿔 본다
        out['zh'] = c.js("()=>[SETTINGS.lang2, 'bilingual' in SETTINGS, document.querySelector('#f-tr').disabled, document.querySelectorAll('.sheet .en[lang=zh-Hans]').length > 0, document.querySelector('#font-link').href.includes('SC')]")
        c.js("()=>document.querySelector('#f-tr').click()"); pg.wait_for_timeout(1500)   # 339번 — 500ms 는 검사를 여럿 동시에 돌릴 때(부하) 번역이 화면에 반영되기 전에 쟀다(단독으로는 통과)
        out['sent'] = [len(sent), sent[0]['lang'] if sent else None, len(sent[0]['texts']) == len(set(sent[0]['texts'])) if sent else None]
        out['filled'] = c.js("""()=>{let miss=0,wine=0,ds=0; MENU.sheets.forEach(s=>s.forEach(c=>c.forEach(x=>{ if(String(x.name||'').trim() && !x.zh) miss++;
            (x.items||[]).forEach(i=>{ if(x.wine){ if(i.zh) wine++; return; } if(String(i.name||'').trim() && !i.zh) miss++; if(String(i.desc||'').trim() && !i.desc_zh) miss++; if(i.desc_zh) ds++; }); }))); return [miss, wine, ds > 0]}""")
        out['en_same'] = c.js(EN) == en0
        # 307번 — 다 차 있으면 묻는다(부르지 않고), 빈 칸만은 흐림
        n = len(sent); c.js("()=>document.querySelector('#f-tr').click()"); pg.wait_for_timeout(300)
        out['ask_full'] = [c.js("()=>document.querySelector('#trask').open"), c.js("()=>document.querySelector('#ta-empty').disabled"), len(sent) == n]
        c.js("()=>document.querySelector('#trask').close()")
        c.js("()=>{const s=MENU.sheets[0][0][0]; s.items[0].zh='사람이 고침'; delete s.items[1].zh; render(); touch();}")
        c.js("()=>document.querySelector('#f-tr').click()"); pg.wait_for_timeout(300); pg.click('#ta-empty'); pg.wait_for_timeout(400)
        out['keep'] = [len(sent[-1]['texts']), c.js("()=>[MENU.sheets[0][0][0].items[0].zh, !!MENU.sheets[0][0][0].items[1].zh]")]
        pg.click('#b-undo'); pg.wait_for_timeout(300); out['undo'] = c.js("()=>!MENU.sheets[0][0][0].items[1].zh")
        pg.click('#b-redo'); pg.wait_for_timeout(300)
        total = c.js("()=>trTargets('zh', true).length")
        c.js("()=>document.querySelector('#f-tr').click()"); pg.wait_for_timeout(300); pg.click('#ta-all'); pg.wait_for_timeout(400)
        out['all'] = [len(sent[-1]['texts']) == len(set(j for j in sent[-1]['texts'])), c.js("()=>MENU.sheets[0][0][0].items[0].zh") != '사람이 고침', total > 1]
        pg.click('#b-undo'); pg.wait_for_timeout(300); out['all_undo'] = c.js("()=>MENU.sheets[0][0][0].items[0].zh") == '사람이 고침'
        out['final_lines'] = c.js("()=>{toggleEdit(); return [document.querySelectorAll('.sheet .en[lang=zh-Hans]:empty').length, document.querySelectorAll('.sheet .en[lang=zh-Hans]').length > 0]}")
        with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
        p = D + 'res/tr_' + f; d.value.save_as(p)
        out['err'] += c.errs; c.close()
        c = Ctx(b, 'res/tr_' + f)
        out['reopen'] = c.js("()=>[L2(), document.querySelector('#f-lang').value, !!MENU.sheets[0][0][0].items[1].zh, document.querySelectorAll('.sheet .en[lang=zh-Hans]').length > 0]")
        out['err'] += c.errs; c.close()
        c = Ctx(b, f)   # 옛 저장본 — bilingual:true 는 영어
        out['legacy'] = c.js("()=>{delete SETTINGS.lang2; SETTINGS.bilingual=true; syncControls(); render(); return [L2(), document.querySelector('#f-lang').value, document.querySelectorAll('.sheet .en[lang=en]').length > 0]}")
        out['err'] += c.errs; c.close()
    except Exception as e:
        out['fail'] = str(e)[:300]
        try: c.close()
        except Exception: pass
    # 310번. 번역 중은 「로딩」 — 단추가 막히지 않고(흐리지 않음) 지난 초를 센다 · 아래 알림에도 / 궁서체의 일본어 줄은 일본어 글꼴이 먼저(한자 · 가나가 한 글꼴로)
    try:
        c = Ctx(b, f); pg = c.pg; pg.click('#b-edit'); pg.wait_for_timeout(200)
        c.js("()=>{SETTINGS.font='gungseo'; MENU.sheets[0][0][0].items[0].ja='塩昆布海老パスタ'; const l=document.querySelector('#f-lang'); l.value='ja'; l.dispatchEvent(new Event('change',{bubbles:true})); applyLook(); render(); trCall=(L,t)=>new Promise(r=>setTimeout(()=>r(t.map(_=>'テスト')),4000));}")
        pg.wait_for_timeout(200)
        out['ja310'] = c.js("()=>{const e=document.querySelector('.sheet .en:lang(ja)'); return e ? getComputedStyle(e).fontFamily : null}")
        c.js("()=>{document.querySelector('#f-tr').click(); const d=document.querySelector('#trask'); if (d && d.open) document.querySelector('#ta-empty').click();}"); pg.wait_for_timeout(1400)   # 일본어 칸 하나를 채워 두어 묻는 창이 뜬다 — 빈 칸만
        out['busy310'] = c.js("()=>{const b=document.querySelector('#f-tr'), u=document.querySelector('#undo'); return [b.disabled, getComputedStyle(b).opacity, /초/.test(b.textContent), !u.hidden && /초/.test(u.textContent)]}")
        out['err'] += c.errs; c.close()
    except Exception as e:
        out['busy310'] = str(e)[:200]
    here = os.path.dirname(os.path.abspath(__file__))
    fn = next((p for p in [os.path.join(here, 'api', 'translate.js'), os.path.join(here, '..', 'api', 'translate.js')] if os.path.exists(p)), None)
    out['server'] = None
    if fn:
        open(D + 'res/t57.js', 'w').write(NODE57)
        r = subprocess.run(['node', D + 'res/t57.js', os.path.abspath(fn)], capture_output=True, text=True, timeout=60)
        try: out['server'] = json.loads(r.stdout)
        except Exception: out['server'] = {'stderr': r.stderr[-300:]}
    return out

# ───────────────────────── 55. 자동 저장 · 불러오기(277번) — 이 폴더를 작은 웹 서버로 띄워 버셀 주소처럼(http) 연다
def t66(b, f):
    """380번 — 사진의 바닥 글 중 원산지 문구(…(국내산) · 원산지)는 확인 화면에서 따로 모여 이름이 붙고, 시작하면 원산지 칸으로 들어가 칸이 켜진다(없으면 칸은 꺼진 채).
    QR 이 있어도 원산지 윗선이 마지막 바닥 글 줄을 가르지 않는다(.footmain 의 틈)"""
    import json as _j
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p66_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    T1 = "가게: 행복한 그릇\n콘셉트: 기타\n방향: 세로\n단: 1\n글꼴: 둥근\n색: 종이 #ffffff · 글자 #2b2218 · 띠 없음\n[덮밥]\n가츠동 | 8000\n[우동]\n새우튀김 우동 | 7500\n바닥: •돼지고기(국내산) 소고기(미국산) 닭고기(태국산)\n바닥: •연어(노르웨이산) 쌀(국내산)\n바닥: 매주 월요일 휴무\n"
    T2 = T1.replace("바닥: •돼지고기(국내산) 소고기(미국산) 닭고기(태국산)\n", "").replace("바닥: •연어(노르웨이산) 쌀(국내산)\n", "")
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    pg.route('**/api/read', lambda r: r.fulfill(status=200, content_type='application/json', body='{"enabled":false}'))
    try:
        for key, T in (('with', T1), ('none', T2)):
            pg.goto(url('p66_' + f)); pg.wait_for_timeout(500)
            pg.click('#st-photo'); pg.wait_for_timeout(400); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', T); pg.click('#st-appgo'); pg.wait_for_timeout(400)
            if pg.is_visible('#st-check-go'): pg.click('#st-check-go')
            pg.wait_for_timeout(300)
            conf = pg.evaluate("()=>[...document.querySelectorAll('#st-cfoot > *')].map(e=>e.tagName+':'+(e.getAttribute('aria-label')||e.className))")
            pg.click('#st-go'); pg.wait_for_timeout(900)
            out[key] = {'conf': conf, 'feet': pg.evaluate("()=>MENU.feet"), 'show': pg.evaluate("()=>SETTINGS.pages[0].showOrigin")}
        pg.goto(url('p66_' + f)); pg.wait_for_timeout(500)
        pg.click('#st-photo'); pg.wait_for_timeout(400); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', T1); pg.click('#st-appgo'); pg.wait_for_timeout(400)
        if pg.is_visible('#st-check-go'): pg.click('#st-check-go')
        pg.click('#st-go'); pg.wait_for_timeout(900)
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{ guideEnd() }catch(e){} const P0=SETTINGS.pages[0]; P0.qrs=[{cell:4,kind:'url',url:'https://example.com'}]; P0.seals=[]; syncControls(); applyLook(); render(); }")
        pg.wait_for_timeout(300)
        out['qr'] = pg.evaluate("()=>{ const r=e=>e.getBoundingClientRect(); const row=document.querySelector('.sheet .foot .footrow'), o=document.querySelector('.sheet .foot .origin'); return [!!document.querySelector('.sheet .foot.hasqr'), Math.round(r(row).bottom), Math.round(r(o).top)] }")
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t65(b, f):
    """379번 — 도장은 QR 과 같은 취급: 바닥 글 칸은 아래 칸에 도장이 있는 쪽만 비우고(왼쪽 · 오른쪽 · 둘 다) 아무것도 없으면 좌우 끝까지. 바닥 높이는 그대로.
    띠 없는 상단의 빈 칸 점선은 흰색이 아니고, 구역 틀은 마우스가 없을 때 숨는다"""
    import json as _j
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p65_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    ctx = b.new_context(viewport={'width': 1400, 'height': 900}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    try:
        pg.goto(url('p65_' + f)); pg.wait_for_timeout(500); pg.click('#st-alps'); pg.wait_for_timeout(800); pg.keyboard.press('Escape')
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{ guideEnd() }catch(e){} }")
        if not pg.evaluate("()=>document.body.classList.contains('editing')"): pg.click('#b-edit')
        pg.wait_for_timeout(300)
        M = """(cells)=>{ const P0=SETTINGS.pages[0]; P0.seals=cells.map(c=>({cell:c,seal:'word'})); P0.showNotes=true; P0.showOrigin=true; MENU.feet=MENU.feet||[{}]; MENU.feet[0].notes=['돼지고기(국내산) 소고기(미국산) 닭고기(태국산) 연어(노르웨이산) 쌀(국내산) 김치(중국산) 고춧가루(국내산, 중국산)']; MENU.feet[0].origin='돼지고기 국내산 · 쌀 국내산'; syncControls(); applyLook(); render();
          const sh=document.querySelector('.sheet'), sr=sh.getBoundingClientRect(), R=e=>{ if(!e) return null; const r=e.getBoundingClientRect(); return [Math.round(r.left-sr.left),Math.round(r.right-sr.left),Math.round(r.top-sr.top),Math.round(r.bottom-sr.top)] };
          const seals={}; sh.querySelectorAll('.seal:not(.blank)').forEach(e=>{ seals[e.dataset.cell]=R(e) });
          const o=sh.querySelector('.foot .origin'), cs=getComputedStyle(o), fr=R(sh.querySelector('.foot .footrow'));
          return {seals, left:R(sh.querySelector('.foot .left')), row:fr, footH:R(sh.querySelector('.foot')), op:[parseFloat(cs.marginLeft)>0, parseFloat(cs.marginRight)>0], origin:R(o)} }"""
        res = {}
        for cells in ([], [5], [4], [4, 5]):
            res[''.join(map(str, cells)) or 'none'] = pg.evaluate(M, cells); pg.wait_for_timeout(150)
        out['res'] = res
        pg.mouse.move(2, 2)
        out['zone'] = pg.evaluate("()=>{ const z=document.querySelector('.sheet .foot .zone'), h=document.querySelector('.sheet > .zone'); return [getComputedStyle(h).outlineColor, getComputedStyle(z,'::after').borderTopColor] }")
        pg.evaluate("()=>{ const P0=SETTINGS.pages[0]; P0.noren='plain'; P0.showTitle=true; P0.showSub=true; MENU.brand.title=''; MENU.brand.sub=''; render(); }"); pg.wait_for_timeout(200)
        out['dash'] = pg.evaluate("()=>[...document.querySelector('.sheet').querySelectorAll('.noren [contenteditable]:empty')].map(e=>getComputedStyle(e).outlineColor)")
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t64(b, f):
    """376번 · 395번 — 읽은 메뉴 확인 화면에는 맞춤법 줄 · 단추가 없고(같은 이름 · 가격 형식 두 줄), 맞춤법은 편집 화면 AI 창의 [맞춤법 보기]로 본다. 제목 상자 폭(제목 위치)에 맞춰 상단 크기가 정해진다(0~1000 으로 답해도 같다). 「없음」 미리보기에는 아래 선이 없다"""
    import json as _j
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p64_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    T = "가게: 행복한 그릇\n제목 위치: 30 3 · 70 9\n콘셉트: 기타\n방향: 세로\n단: 1\n글꼴: 둥근\n색: 종이 #ffffff · 글자 #2b2218 · 띠 없음\n[덮밥]\n네이가츠동 | 9000\n에비동 | 9500\n"
    ctx = b.new_context(viewport={'width': 1400, 'height': 900}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    cur = [T]
    def h(r):
        if r.request.method == 'GET': return r.fulfill(status=200, content_type='application/json', body='{"enabled":false}')
        if (_j.loads(r.request.post_data or '{}')).get('mode') == 'typo': return r.fulfill(status=200, content_type='application/json', body=_j.dumps({'text': '네이가츠동 → 네기가츠동'}))
        r.fulfill(status=200, content_type='application/json', body='{"enabled":false}')
    try:
        pg.goto(url('p64_' + f)); pg.wait_for_timeout(500); pg.route('**/api/read', h)
        G = "()=>({chips:[...document.querySelectorAll('#st-readsum .chip')].map(x=>x.textContent), why:(document.querySelector('#st-readsum .why')||{}).textContent, hd:[...document.querySelectorAll('#st-cnotes .st-ck .tx')].map(x=>x.textContent).join(' / '), btn:!!document.querySelector('#st-typo'), nl:[...document.querySelectorAll('#st-cnotes .st-cnr .go')].map(x=>x.textContent), note:document.querySelector('#st-notes').textContent})"
        def run(txt):
            pg.click('#st-photo'); pg.wait_for_timeout(400); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', txt); pg.click('#st-appgo'); pg.wait_for_timeout(300)
            pg.wait_for_timeout(300)
        run(T)
        out['before'] = pg.evaluate(G)
        pg.click('#st-check-go'); pg.wait_for_timeout(300)   # 382번. 점검 · 맞춤법은 읽은 메뉴 확인 화면에서, 칩 · 남은 건수 한 줄은 다음 화면에서
        out['setup'] = pg.evaluate(G)
        out['shadow'] = pg.evaluate("()=>getComputedStyle(document.querySelector('#st-prev')).boxShadow")
        pg.click('#st-go'); pg.wait_for_timeout(900)
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{guideEnd()}catch(e){} }"); pg.wait_for_timeout(200)
        pg.click('#b-ai'); pg.wait_for_timeout(300); pg.click('#ai-typo'); pg.wait_for_timeout(700)   # 395번. 맞춤법은 편집 화면 AI 창에서 본다
        out['after'] = pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-it:not(.done)')].map(x=>[...x.querySelectorAll('.ln .v')].map(v=>v.textContent))")
        out['scale'] = pg.evaluate("()=>[SETTINGS.pages[0].norenScale, aiTypoRan, aiTypos.length]")
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t67(b, f):
    """381번 — 사진에서 시작: 맨 위 색 띠는 「띠 위치」가 맨 위 · 둘 다 일 때만 채운다(줄이 없거나 분류 제목 · 없음이면 맨 위는 띠 없이). 칩 · 점검 박스는 두 줄(같은 이름 · 가격 형식 — 395번. 맞춤법 줄은 AI 창으로)."""
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p67_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    base = "가게: 행복한 그릇\n제목 위치: 30 3 · 70 9\n콘셉트: 기타\n방향: 세로\n단: 1\n글꼴: 둥근\n색: 종이 #ffffff · 글자 #2b2218 · 띠 #8a3b2a\n"
    body = "[덮밥]\n네이가츠동 | 9000\n에비동 | 9500\n"
    ctx = b.new_context(viewport={'width': 1400, 'height': 900}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    def h(r):
        r.fulfill(status=200, content_type='application/json', body='{"enabled":false}')
    try:
        pg.goto(url('p67_' + f)); pg.wait_for_timeout(500); pg.route('**/api/read', h)
        for name, extra in [('none_line', ''), ('top', '띠 위치: 맨 위\n'), ('both', '띠 위치: 둘 다\n'), ('sec', '띠 위치: 분류 제목\n'), ('no', '띠 위치: 없음\n')]:
            pg.goto(url('p67_' + f)); pg.wait_for_timeout(400); pg.route('**/api/read', h)
            pg.click('#st-photo'); pg.wait_for_timeout(300); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', base + extra + body); pg.click('#st-appgo'); pg.wait_for_timeout(300)
            if pg.is_visible('#st-check-go'): pg.click('#st-check-go')
            pg.wait_for_timeout(300)
            chips = pg.evaluate("()=>[...document.querySelectorAll('#st-readsum .chip')].map(x=>x.textContent).filter(t=>t.includes('맨 위'))")
            hasband = pg.evaluate("()=>document.querySelector('.st-cpaper').classList.contains('hasband')")
            pg.click('#st-go'); pg.wait_for_timeout(700)
            out[name] = [chips, hasband, pg.evaluate("()=>SETTINGS.pages[0].noren")]
        pg.goto(url('p67_' + f)); pg.wait_for_timeout(400); pg.route('**/api/read', h)
        pg.click('#st-photo'); pg.wait_for_timeout(300); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', base + body); pg.click('#st-appgo'); pg.wait_for_timeout(300)
        out['rows'] = pg.evaluate("()=>{const r=[...document.querySelectorAll('#st-cnotes .st-ck')]; return [r.length, !document.querySelector('#st-typo'), r.map(x=>x.querySelector('.tx').textContent).join(' / ')]}")   # 395번. 두 줄(같은 이름 · 가격 형식) — 맞춤법 줄 · 단추 없음
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t68(b, f):
    """383번 — 사진으로 시작: 바닥 글이 없으면 바닥 글 칸이 꺼져 있고, 원산지 줄이 있으면 본문 마지막 줄이 원산지 줄 위에서 끝난다(원산지도 맞춤이 재는 장애물). 원산지 없는 같은 메뉴는 전처럼 더 크게 들어간다."""
    import json as _j
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p68_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    items = "".join(f"메뉴 이름 {i} 설명이 조금 긴 덮밥 #Pork | {8000 + i * 500}\n" for i in range(12))
    base = "가게: 행복한 그릇\n콘셉트: 기타\n방향: 세로\n단: 1\n글꼴: 둥근\n색: 종이 #ffffff · 글자 #2b2218 · 띠 #c8b560\n띠 위치: 분류 제목\n[덮밥]\n" + items + "[우동]\n새우튀김 우동 | 7500\n김치우동 | 7500\n[사이드]\n에비후라이 | 3500\n마지막 줄 메뉴 | 15000\n"
    ori = "바닥: •돼지고기(국내산) 소고기(미국산) 닭고기(태국산) •연어(노르웨이산) 쌀(국내산) 김치(중국산) •고춧가루(국내산,중국산)\n"
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    def h(r): r.fulfill(status=200, content_type='application/json', body='{"enabled":false}')
    R = "()=>{const s=document.querySelector('.sheet'), o=s.querySelector('.origin'), sr=s.getBoundingClientRect(); const e=[...s.querySelectorAll('*')].filter(x=>x.children.length===0 && x.textContent.trim().startsWith('마지막 줄 메뉴')).pop(); return {last:e?Math.round(e.getBoundingClientRect().bottom-sr.top):null, origin:o&&o.getBoundingClientRect().height>0?Math.round(o.getBoundingClientRect().top-sr.top):null, notes:SETTINGS.pages[0].showNotes, show:SETTINGS.pages[0].showOrigin, scale:SETTINGS.pages[0].scale}}"
    try:
        for name, txt in [('with', base + ori), ('none', base)]:
            pg.goto(url('p68_' + f)); pg.wait_for_timeout(400); pg.route('**/api/read', h)
            pg.click('#st-photo'); pg.wait_for_timeout(300); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', txt); pg.click('#st-appgo'); pg.wait_for_timeout(400)
            pg.click('#st-check-go'); pg.wait_for_timeout(300); pg.click('#st-go'); pg.wait_for_timeout(1200)
            pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{guideEnd()}catch(e){} }"); pg.wait_for_timeout(400)
            out[name] = pg.evaluate(R)
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t69(b, f):
    """384번 — ① 첫 화면 창은 늘 뒤를 가린다(뒷배경 불투명) ② 영업시간을 켜면 빈 줄이 생기고 커서가 간다 · 이름표가 시간 줄 높이 가운데 ③ 원산지 이름 ④ 와인 장에서 글을 치면 넘침 표시가 뜬다(커서 유지) ⑤ 확인 화면 점검은 세 줄 체크 목록."""
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p69_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    BD = "()=>getComputedStyle(document.querySelector('#start'),'::backdrop').backgroundColor"
    try:
        pg.goto(url('p69_' + f)); pg.wait_for_timeout(500)
        out['bd_first'] = pg.evaluate(BD)
        pg.click('#st-alps'); pg.wait_for_timeout(1200)
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{guideEnd()}catch(e){} }"); pg.wait_for_timeout(300)
        pg.evaluate("()=>{ openStart() }"); pg.wait_for_timeout(300)
        out['bd_again'] = pg.evaluate(BD) ; out['bd_first_cls'] = pg.evaluate("()=>document.querySelector('#start').classList.contains('first')")
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()) }"); pg.wait_for_timeout(200)
        out['origin_label'] = pg.evaluate("()=>document.querySelector('#f-origin').parentElement.textContent.trim()")
        # 영업시간: 끄고 · 다 지우고 · 켜기
        pg.click('#b-style'); pg.wait_for_timeout(300)
        pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(300)   # 끈다
        pg.evaluate("()=>{ MENU.hours = []; render(); }"); pg.wait_for_timeout(300)
        pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(400)   # 켠다
        out['hours_on'] = pg.evaluate("()=>({n:MENU.hours.length, rows:document.querySelectorAll('.sheet[data-pi=\"0\"] .hours > div').length, focus:!!(document.activeElement && document.activeElement.closest && document.activeElement.closest('.hours')), show:SETTINGS.pages[0].showHours})")
        out['hours_geo'] = pg.evaluate("""()=>{ const z=document.querySelector('.sheet[data-pi="0"] .zone:has(> .hours)'), h=z.querySelector('.hours'), zr=z.getBoundingClientRect(), hr=h.getBoundingClientRect(); const t=getComputedStyle(z,'::before'); return {zoneTop:Math.round(zr.top), hoursTop:Math.round(hr.top), zoneH:Math.round(zr.height), hoursH:Math.round(hr.height), tagTop:t.top, tf:t.transform} }""")
        # 껐다 켜도 이미 시간이 있으면 줄을 더 만들지 않는다
        pg.evaluate("()=>{ MENU.hours[0].label='평일'; MENU.hours[0].time='11:00~21:00'; render(); }"); pg.wait_for_timeout(200)
        pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(200); pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(300)
        out['hours_keep'] = pg.evaluate("()=>MENU.hours.length")
        # 와인 장 — 쳐서 넘치게
        pg.evaluate("()=>{ MENU.feet[1].origin='•돼지고기(국내산) 소고기(미국산) 닭고기(태국산) •연어(노르웨이산) 쌀(국내산) 김치(중국산)'; SETTINGS.pages[1].showOrigin=true; SETTINGS.pages[1].showNotes=true; MENU.feet[1].notes=['* 와인 주문 시 안내']; render(); }"); pg.wait_for_timeout(700)
        S = "()=>[...document.querySelectorAll('.sheet')].map(s=>[s.className.includes('over'), (s.querySelector('.pstat')||{}).textContent||'', s.dataset.overnote||''])"
        out['typ0'] = pg.evaluate(S)
        sel = '.sheet[data-pi="1"] [data-path="sheets.1.0.0.items.2.taste"]'
        pg.click(sel); pg.keyboard.press('End')
        for i in range(14): pg.keyboard.type('자두와 익은 체리, 지속적인 여운 ', delay=1)
        pg.wait_for_timeout(1300)
        out['typ1'] = pg.evaluate(S); out['typ_focus'] = pg.evaluate("(s)=>document.activeElement===document.querySelector(s)", sel)
        out['typ_sc'] = pg.evaluate("()=>P(1).scale")
        # 줄이면 표시가 사라진다
        pg.evaluate("(s)=>{ const n=document.querySelector(s); n.textContent='짧게'; n.dispatchEvent(new Event('input',{bubbles:true})) }", sel); pg.wait_for_timeout(1300)
        out['typ2'] = pg.evaluate(S)
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t70(b, f):
    """390번 · 395번 — 확인 화면 점검은 같은 이름 · 가격 형식 두 줄(맞춤법은 AI 창만) · 점검 박스 스크롤 없음 · AI 창 맞춤법은 같은 고침을 한 카드로(메뉴 N곳 · 밑줄 · 모두 적용 · 묶음 되돌림 · 묶음 무시) · 다른 말로 바꾼 것 거름 · 안내창 테두리 단추 크림 바탕 · 회색 제목 색 버림 · 오른쪽 창 머리 탭 [꾸미기 | AI] · 켜짐 한 가지."""
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p70_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    body = "가게: 행복한 그릇\n방향: 세로\n단: 1\n[덮밥]\n가츠동 | 8000\n네기가츠동 | 8500\n김치가츠동 | 9000\n[사이드]\n타코야끼 | 3500\n오코노미야끼 | 7500\n"
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    def h(r): r.fulfill(status=200, content_type='application/json', body='{"enabled":false}')
    try:
        pg.goto(url('p70_' + f)); pg.wait_for_timeout(400); pg.route('**/api/read', h)
        out['title'] = pg.evaluate("""()=>{ const a=readLook({'색':'종이 #ffffff · 글자 #222222 · 띠 #c8b560 · 제목 #c7c5c3'}, null), b=readLook({'색':'종이 #ffffff · 글자 #222222 · 띠 #c8b560 · 제목 #8f8a2e'}, null); return [a.title||null, /회색/.test(a.titleWhy||''), b.title||null] }""")
        pg.click('#st-photo'); pg.wait_for_timeout(300); pg.click('#st-way button[data-w="app"]'); pg.fill('#st-ans', body); pg.click('#st-appgo'); pg.wait_for_timeout(500)
        out['clean'] = pg.evaluate("()=>typoClean([{from:'가츠동 (돈가츠 덮밥) #Pork',to:'가쓰동 (돈가스 덮밥)'},{from:'에비후라이 (새우튀김 두마리) #Shrimp',to:'에비후라이 (새우튀김 두 마리)'},{from:'김치찌게 #Kimchi',to:'김치찌개'},{from:'타코야끼 (여섯개)',to:'타코야키 (여섯 개)',kind:'외래어 표기'},{from:'Salmon',to:'Salman'}]).map(t=>[t.from,t.to,t.kind])")   # 394번. 해시태그 · 영문만 거르고 맞춤법 · 외래어 표기 · 띄어쓰기는 다 — 바뀐 부분만, 띄어쓰기는 묶어서
        out['aikind'] = pg.evaluate("async()=>{ const f=window.fetch; window.fetch=async()=>({status:200, ok:true, json:async()=>({text:'돈까스 → 돈가스 (외래어 표기)'})}); try { const r=await typoAsk(['돈까스 #Pork']); return r.length===1 ? [r[0].from, r[0].to, r[0].kind] : r } finally { window.fetch=f } }")   # 394번. AI 답의 갈래
        out['parts'] = pg.evaluate("()=>[typoLabel('가츠동 (돈가츠 덮밥) #Pork','가쓰동 (돈가스 덮밥) #Pork'), typoLabel('타코야끼','타코야키'), typoLabel('김치 우동','김치우동')]")   # 392번. 바뀐 낱말만
        out['far'] = pg.evaluate("()=>typoClean([{from:'사케동',to:'생연어덮밥'},{from:'가라아게동',to:'가라아게덮밥'},{from:'오뎅',to:'어묵'},{from:'케익',to:'케이크'},{from:'함박스텍',to:'함박스테이크'},{from:'육계장',to:'육개장'}]).map(t=>t.from)")   # 395번. 다른 말로 바꾼 것은 뺀다
        pg.evaluate("()=>{ stTypos.push({from:'가츠동',to:'가쓰동'}); drawCkNotes(); }"); pg.wait_for_timeout(150)
        out['ck395'] = pg.evaluate("()=>[!!document.querySelector('#st-ck-typo'), !!document.querySelector('#st-cl-typo'), !!document.querySelector('#st-typo'), document.querySelectorAll('#st-cnotes .st-ck').length, /맞춤법/.test(document.querySelector('#st-cnotes').textContent)]")   # 395번. 확인 화면에는 같은 이름 · 가격 형식 두 줄만
        out['box'] = pg.evaluate("()=>{ const b=document.querySelector('#st-cnotes'); return [getComputedStyle(b).overflowY, b.scrollHeight - b.clientHeight] }")
        out['notag'] = pg.evaluate("()=>['오코노미야끼 #Japanese Style #Pancake', '가츠동 (돈가츠 덮밥) #Pork', '김치우동'].map(aiNoTag)")   # 397번. 첫 #부터 끝까지
        out['fill396'] = pg.evaluate("()=>{ const p=document.querySelector('.st-cpaper'), h=document.querySelector('.st-chead'), b=h.querySelector('.st-cadd'), t=h.querySelector('.st-csec'), R=e=>e.getBoundingClientRect(); return [p.scrollHeight <= p.clientHeight && getComputedStyle(p).overflowY === 'hidden', +(document.querySelector('#st-ctab').style.zoom||1) > 1, R(b).top >= R(t).top - 0.5 && R(b).bottom <= R(t).bottom + 0.5 && R(b).right <= R(t).right + 0.5] }")   # 396번. 메뉴가 적으면 키워 종이를 채우고(스크롤 없음) · [＋ 메뉴]는 분류 띠 안
        out['btbg'] = pg.evaluate("()=>getComputedStyle(document.querySelector('#st-copy')).backgroundColor")
        pg.click('#st-check-go'); pg.wait_for_timeout(300); pg.click('#st-go'); pg.wait_for_timeout(1200)
        pg.evaluate("()=>{ document.querySelectorAll('dialog[open]').forEach(d=>d.close()); try{guideEnd()}catch(e){} }"); pg.wait_for_timeout(300)
        if not pg.evaluate("()=>editing"): pg.click('#b-edit'); pg.wait_for_timeout(300)
        if pg.evaluate("()=>document.querySelector('#panel').hidden"): pg.click('#b-style'); pg.wait_for_timeout(300)
        ST = "()=>({panel:!document.querySelector('#panel').hidden, ai:!document.querySelector('#aipanel').hidden, bs:document.querySelector('#b-style').classList.contains('on'), ba:document.querySelector('#b-ai').classList.contains('on'), ed:editing})"
        pg.evaluate("()=>document.querySelector('#b-ai').click()"); pg.wait_for_timeout(300); out['toAI'] = pg.evaluate(ST)   # 392번. 창 머리 탭을 걷고 위쪽 막대 [꾸미기] · [AI]로
        out['bar392'] = pg.evaluate("()=>{ const s=document.querySelector('#b-style'); return [!!s.closest('#editbar'), s.closest('.tb-right') === document.querySelector('#b-ai').closest('.tb-right'), document.querySelectorAll('.pwtab').length, Math.round(document.querySelector('#aipanel').getBoundingClientRect().width)] }")
        pg.mouse.move(2, 990); pg.wait_for_timeout(100)
        out['onbg'] = pg.evaluate("()=>[getComputedStyle(document.querySelector('#b-ai')).backgroundColor, getComputedStyle(document.querySelector('#b-edit')).backgroundColor]")
        NM = "()=>MENU.sheets[0].flat().flatMap(s=>s.items.map(i=>i.name))"
        pg.evaluate("()=>{ aiTypos = [{from:'가츠동',to:'가쓰동',kind:'외래어 표기'},{from:'네기가츠동',to:'네기가쓰동',kind:'외래어 표기'},{from:'타코야끼',to:'타코야키',kind:'외래어 표기'}]; aiDraw(); }")   # 396번. 네기가츠동 → 네기가쓰동은 가츠동 → 가쓰동에 덮여 빠진다; pg.wait_for_timeout(200)
        C = "()=>[...document.querySelectorAll('#ai-list .aip-it:not(.done)')].map(x=>[x.querySelector('.ln.fr .v').textContent, x.querySelector('.ln.to .v').textContent, x.querySelector('.ln.nmline b').textContent, [...x.querySelectorAll('.ln.nmline .nmi')].map(n=>n.textContent).join('|'), [...x.querySelectorAll('.ln.nmline u')].map(u=>u.textContent).join(',')])"
        out['cards'] = [pg.evaluate(C), pg.evaluate("()=>document.querySelector('#ai-count').textContent")]   # 395번. 같은 고침은 한 카드 — 「메뉴 3곳」 + 틀린 부분 밑줄
        out['frto'] = pg.evaluate("()=>{ const it=document.querySelector('#ai-list .aip-it'); return [getComputedStyle(it.querySelector('.ln.fr .v')).textDecorationLine, getComputedStyle(it.querySelector('.ln.to .v')).fontWeight, getComputedStyle(it.querySelector('.ln.to .v')).color] }")
        pg.evaluate("()=>{ [...document.querySelectorAll('#ai-list .aip-it')].find(x=>/가츠동/.test(x.textContent)).click() }"); pg.wait_for_timeout(200)
        out['allbtn'] = pg.evaluate("()=>document.querySelector('#ai-list .aip-it.on .aip-btns button.ap').textContent")
        out['flash'] = pg.evaluate("()=>document.querySelectorAll('.aiflash').length")   # 396번. 묶은 카드를 고르면 해당 칸이 다 칠해진다
        pg.evaluate("()=>{ document.querySelector('#ai-list .aip-it.on .aip-btns button.ap').click() }"); pg.wait_for_timeout(300)
        out['aidone'] = [pg.evaluate("()=>document.querySelectorAll('#ai-list .aip-it.done').length"), pg.evaluate(NM)[:3], pg.evaluate("()=>document.querySelector('#ai-list .aip-it.done .ln.nmline b').textContent")]
        pg.evaluate("()=>{ document.querySelector('#ai-list .aip-it.done button').click() }"); pg.wait_for_timeout(300)
        out['aiundo'] = [pg.evaluate("()=>document.querySelectorAll('#ai-list .aip-it.done').length"), pg.evaluate(NM)[:3]]
        pg.evaluate("()=>{ [...document.querySelectorAll('#ai-list .aip-it')].find(x=>/가츠동/.test(x.textContent)).click() }"); pg.wait_for_timeout(200)
        pg.evaluate("()=>{ [...document.querySelectorAll('#ai-list .aip-it.on .aip-btns button')].find(b=>b.textContent==='무시').click() }"); pg.wait_for_timeout(200)
        out['aiign'] = [pg.evaluate("()=>aiIgnore.size"), pg.evaluate("()=>document.querySelector('#ai-count').textContent")]   # 395번. [무시]도 묶음 전체
        pg.evaluate("()=>{ aiIgnore = new Set(); aiTypos = []; aiDraw(); }")
        out['aist'] = pg.evaluate("()=>{ aiIgnore = new Set(aiList().L.map(f=>f.key)); aiDraw(); const r=[...document.querySelectorAll('#ai-list .aip-st')].map(x=>[x.dataset.s, x.textContent]); aiIgnore = new Set(); aiDraw(); return r }")   # 391번. 점검할 것이 없으면 줄글 대신 세 줄
        pg.evaluate("()=>document.querySelector('#b-edit').click()"); pg.wait_for_timeout(300); out['toStyle'] = pg.evaluate(ST)   # 393번. 편집을 켜면 AI 창이 닫히고 꾸미기 창
        out['pw392'] = pg.evaluate("()=>Math.round(document.querySelector('#panel').getBoundingClientRect().width)")
        pg.click('#b-edit'); pg.wait_for_timeout(300); pg.click('#b-ai'); pg.wait_for_timeout(300)
        pg.evaluate("()=>document.querySelector('#b-edit').click()"); pg.wait_for_timeout(400); out['fromView'] = pg.evaluate(ST)   # 393번
        pg.evaluate("()=>document.querySelectorAll('#ptabs button')[4].click()"); pg.wait_for_timeout(250)
        out['qrph'] = [pg.evaluate("(k)=>{ document.querySelector('#f-qrkind button[data-k=\"'+k+'\"]').click(); return document.querySelector('#f-qrlabel').placeholder }", k) for k in ('url', 'wifi')]   # 400번. QR 이름 예시는 종류에 맞게
    except Exception as e:
        out['fail'] = str(e)[:200]
    finally:
        ctx.close()
    return out

def t63(b, f):
    """366번 — 위쪽 단추 [편집 · AI · 꾸미기 · 미리보기]는 이름이 안 바뀌고 색으로만 켜짐을 알린다(편집이 꺼진 때 붉지 않음 · 편집과 AI 동시 켜짐).
    색 칸 나누기: 맨 위 띠 색 · 맨 위 글자색 · 분류 제목 띠 색 · 분류 제목 글자색 · 메뉴 이름 글자색이 따로 먹고 · 기본으로 돌리고 · 추천 조합을 고르면 지워지고 · 저장해 다시 열면 남는다"""
    out = {'err': []}
    ctx = b.new_context(viewport={'width': 1500, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    try:
        pg.goto(url(f)); pg.wait_for_timeout(600)
        B = "()=>['#b-edit','#b-ai','#b-style','#b-preview'].map(s=>{const e=document.querySelector(s); return [e.textContent.trim(), e.classList.contains('on'), getComputedStyle(e).backgroundColor]})"
        a0 = pg.evaluate(B)
        pg.click('#b-edit'); pg.wait_for_timeout(250); pg.click('#b-ai'); pg.wait_for_timeout(250)
        a1 = pg.evaluate(B); a1p = pg.evaluate("()=>[document.querySelector('#b-edit').getAttribute('aria-pressed'), document.querySelector('#b-ai').getAttribute('aria-pressed')]")
        out['onbg'] = a1[0][2] + '|' + a1[1][2]
        out['btn'] = [[x[0] for x in a0], [x[1] for x in a0], [x[0] for x in a1][:2], [x[1] for x in a1][:2], a1p, a1[0][2] == a1[1][2] and a1[0][2] != a0[0][2], a0[0][2] == a0[1][2]]
        pg.click('#b-ai'); pg.wait_for_timeout(250)
        pg.click('#b-edit'); pg.wait_for_timeout(300)   # 393번. AI 를 켜면 편집이 꺼진다 — 편집을 다시 켜면 꾸미기 창이 같이 열린다
        P = "()=>{const sh=document.querySelector('.sheet'), r=document.documentElement; return [sh.style.getPropertyValue('--nband'), r.style.getPropertyValue('--sband'), r.style.getPropertyValue('--stx'), r.style.getPropertyValue('--ntx')]}"
        out['def'] = pg.evaluate(P)
        pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(200)
        h1 = pg.evaluate("()=>[SETTINGS.pages[0].showHours, !!document.querySelector('.sheet .hours')]")
        pg.evaluate("()=>document.querySelector('#f-hours').click()"); pg.wait_for_timeout(200)
        out['hours'] = [h1, pg.evaluate("()=>[SETTINGS.pages[0].showHours, !!document.querySelector('.sheet .hours')]")]   # 367번. 영업시간 켜고 끄기
        pg.evaluate("()=>{const e=document.querySelector('#f-noren'); e.value='twin'; e.dispatchEvent(new Event('change',{bubbles:true})); const c=document.querySelector('#f-nfill'); if(c.checked) c.click()}"); pg.wait_for_timeout(300)   # 385번. 채우기를 끈 두 줄 = 예전의 「가는 두 줄」
        out['pcn2'] = pg.evaluate("()=>['nband','sband','stx','ntx'].map(i=>document.querySelector('#n-'+i).textContent)")
        pg.evaluate("()=>{const e=document.querySelector('#f-noren'); e.value='flat'; e.dispatchEvent(new Event('change',{bubbles:true})); const c=document.querySelector('#f-nfill'); if(!c.checked) c.click()}"); pg.wait_for_timeout(200)
        out['nfill374'] = pg.evaluate("""()=>{ const sel=document.querySelector('#f-noren'), chk=document.querySelector('#f-nfill'), P0=SETTINGS.pages[0]; const set=v=>{ sel.value=v; sel.dispatchEvent(new Event('change',{bubbles:true})) }, tog=on=>{ if(chk.checked!==on) chk.click() };
          const st=()=>({n:P0.noren, f:P0.norenFill, cls:document.querySelector('.sheet .noren').className, chk:chk.checked, dis:chk.disabled, lg:document.querySelector('.sheet').style.getPropertyValue('--logo').trim()});
          const r={}; set('flat'); r.flat=st(); tog(false); r.flatOff=st(); tog(true); r.flatOn=st(); set('wave'); tog(false); r.waveOff=st(); set('ridge'); r.ridgeKeep=st(); set('flat'); r.none=st(); tog(true); set('rule'); r.rule=st(); tog(false); r.ruleOff=st(); set('ripple'); tog(true); r.stair=st(); set('frame'); tog(false); r.frame=st(); tog(true); r.frameOn=st(); set('flat'); tog(true); r.opts=[...sel.options].map(o=>o.value).length; const tl=[...document.querySelectorAll('#g-noren button')]; r.tiles=[tl.length, tl.filter(b=>b.classList.contains('on')).map(b=>b.dataset.k), tl.every(b=>b.querySelector('svg'))]; tl.find(b=>b.dataset.k==='arch').click(); r.tileClick=[P0.noren, document.querySelectorAll('#g-noren button.on').length]; set('flat'); return r }""")   # 374번. 상단 모양 + 채우기
        # 368번. 이미 메뉴판이 있을 때 새로 만들기 → 되돌리기가 켜지고 까닭을 말한다 · 되돌리면 이전 메뉴판 + 안내
        nm0 = pg.evaluate("()=>$('#b-undo').disabled")
        pg.evaluate("()=>{const d=JSON.parse(JSON.stringify(ALPS_EXAMPLE)); d.menu.brand.shop='새가게'; startWith(d.menu, d.settings, '새 메뉴판으로 바꿨습니다')}"); pg.wait_for_timeout(500)
        t1 = pg.evaluate("()=>[$('#undo').hidden, $('#undo .t').textContent, $('#b-undo').disabled, MENU.brand.shop]")
        pg.evaluate("()=>$('#undo-btn').click()"); pg.wait_for_timeout(400)
        t2 = pg.evaluate("()=>[$('#undo .t').textContent, MENU.brand.shop]")
        out['newmenu'] = [nm0, (not t1[0]), '이전 메뉴판은 [되돌리기]' in t1[1], (not t1[2]), '새로 만들기 전의 메뉴판으로 돌아왔습니다' in t2[0], t1[3] == '새가게' and t2[1] != '새가게', False]
        out['txt'] = pg.evaluate("()=>[!/Enter 를 누르면 줄이 바뀝니다/.test(document.querySelector('#panel').textContent), document.querySelector('#panel').lastElementChild.classList.contains('pzoom'), document.querySelector('#f-shop').placeholder, /상호명/.test(document.body.innerText), /메뉴명과/.test(document.querySelector('#panel').textContent)]")   # 368번
        out['pcn'] = pg.evaluate("()=>['nband','sband','stx','ntx'].map(i=>document.querySelector('#n-'+i).textContent)")   # 368번. 색 칸 아래 안내는 흐린 칸에만
        pg.evaluate("()=>{const e=document.querySelector('#f-secstyle'); e.value='band'; e.dispatchEvent(new Event('change',{bubbles:true}))}"); pg.wait_for_timeout(300)
        n0 = pg.evaluate("()=>getComputedStyle(document.querySelector('.sheet .row .name')).color")
        def setc(i, v): pg.evaluate("([i,v])=>{const e=document.querySelector('#c-'+i); e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}))}", [i, v])
        for i, v in (('nband', '#2a6f3a'), ('sband', '#8a1c1c'), ('stx', '#ffee99'), ('ntx', '#1b3fa0')): setc(i, v)
        pg.wait_for_timeout(300)
        out['set'] = pg.evaluate("()=>[getComputedStyle(document.querySelector('.sheet .sec-head')).backgroundColor, getComputedStyle(document.querySelector('.sheet .sec-head h2')).color, getComputedStyle(document.querySelector('.sheet .row .name')).color, SETTINGS.pages[0].topBand, SETTINGS.secBand, SETTINGS.secText, SETTINGS.nameText]")
        out['dis'] = pg.evaluate("()=>['nband','sband','stx','ntx'].map(i=>document.querySelector('#b-'+i+'-r').disabled)")
        pg.evaluate("()=>{['nband','sband','stx','ntx'].forEach(i=>document.querySelector('#b-'+i+'-r').click())}"); pg.wait_for_timeout(300)
        out['n0'] = n0
        out['reset'] = pg.evaluate("()=>[SETTINGS.pages[0].topBand, SETTINGS.secBand, SETTINGS.secText, SETTINGS.nameText, getComputedStyle(document.querySelector('.sheet .row .name')).color]")
        for i, v in (('sband', '#8a1c1c'), ('ntx', '#1b3fa0'), ('nband', '#2a6f3a')): setc(i, v)
        pg.wait_for_timeout(200)
        pg.evaluate("()=>pickLook('p:'+visPresets()[1])"); pg.wait_for_timeout(500)
        out['preset'] = pg.evaluate("()=>[SETTINGS.pages[0].topBand, SETTINGS.secBand, SETTINGS.secText, SETTINGS.nameText]")
        for i, v in (('sband', '#8a1c1c'), ('ntx', '#1b3fa0'), ('nband', '#2a6f3a')): setc(i, v)
        pg.wait_for_timeout(200)
        st = pg.evaluate("()=>JSON.stringify({menu:MENU,settings:SETTINGS})")
        pg.evaluate("(s)=>applyState(s)", st); pg.wait_for_timeout(400)
        out['round'] = pg.evaluate("()=>[SETTINGS.pages[0].topBand, SETTINGS.secBand, SETTINGS.nameText, document.querySelector('#c-ntx').value]")
        src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
        open(D + 'p63_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "secBand": "red;x", "nameText": "url(x)", "secText": "#ABCDEF",\n', 1))
        pg.goto(url('p63_' + f)); pg.wait_for_timeout(600)
        out['bad'] = pg.evaluate("()=>[SETTINGS.secBand, SETTINGS.nameText, SETTINGS.secText]")   # 망가진 값은 버리고 · 올바른 값은 남긴다
    except Exception as e: out['fail'] = str(e)[:300]
    ctx.close(); return out

def t62(b, f):
    """362번 — 사진을 닮게: 읽기 글의 [분류 제목 · 띠 위치 · 그림]이 확인 화면 미리보기와 편집 화면의 띠 · 그림에 같이 반영되고, 줄이 없으면 기존 동작 그대로.
    사진 끌어놓기: 창 어디서나 끌면 안내 막이 뜨고 · 멈추면 사라지고 · 놓으면 기본 동작(새 탭)이 막히고 사진이 올라온다"""
    import json as _j, base64 as _b
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p62_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    T = "가게: 행복한 그릇\n콘셉트: 기타\n방향: 세로\n단: 1\n글꼴: 둥근\n색: 종이 #ffffff · 글자 #2b2218 · 띠 #c8c860 · 제목 #8a8a1e\n분류 제목: 띠\n띠 위치: 분류 제목\n그림: 라면\n[덮밥 Rice Bowl] 1\n가츠동 | 8000\n[우동 Udon] 1\n새우튀김 우동 | 7500\n"
    T0 = T.replace("분류 제목: 띠\n", "").replace("띠 위치: 분류 제목\n", "").replace("그림: 라면\n", "")
    png = open(D + 'tests_img.jpg', 'rb').read() if os.path.exists(D + 'tests_img.jpg') else None
    ctx = b.new_context(viewport={'width': 1400, 'height': 900}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    cur = [T]
    pg.route('**/api/read', lambda r: r.fulfill(status=200, content_type='application/json', body='{"enabled":true}') if r.request.method == 'GET' else r.fulfill(status=200, content_type='application/json', body=_j.dumps({'text': cur[0]})))
    try:
        pg.goto(url('p62_' + f)); pg.wait_for_timeout(500); pg.click('#st-photo'); pg.wait_for_timeout(200)
        jpg = pg.evaluate("()=>{const c=document.createElement('canvas'); c.width=40; c.height=40; c.getContext('2d').fillRect(0,0,20,20); return c.toDataURL('image/jpeg').split(',')[1]}")
        pg.evaluate("(d)=>{window.__dt=new DataTransfer(); const b=Uint8Array.from(atob(d),c=>c.charCodeAt(0)); __dt.items.add(new File([b],'m.jpg',{type:'image/jpeg'}));}", jpg)
        pg.evaluate("()=>document.querySelector('.st-head').dispatchEvent(new DragEvent('dragover',{dataTransfer:__dt,bubbles:true,cancelable:true}))"); pg.wait_for_timeout(100)
        o1 = pg.evaluate("()=>{const e=document.querySelector('#st-dropall'); return !e.hidden && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width >= innerWidth * 0.9}")
        pg.wait_for_timeout(500); o2 = pg.evaluate("()=>document.querySelector('#st-dropall').hidden")
        o3 = pg.evaluate("()=>{const e=new DragEvent('drop',{dataTransfer:__dt,bubbles:true,cancelable:true}); document.querySelector('.st-head').dispatchEvent(e); return e.defaultPrevented}"); pg.wait_for_timeout(900)
        o4 = pg.evaluate("()=>{const i=document.querySelector('#st-picimg'); return i.src.slice(0,10) === 'data:image' && !i.hidden}")
        out['drag'] = [o1, o2, o3, o4]
        pg.evaluate("(t)=>toCheck(t, document.querySelector('#st-appmsg'))", T); pg.wait_for_timeout(300)
        out['look'] = pg.evaluate("()=>[stLook.sec, stLook.bandAt, stLook.art, document.querySelector('.st-cpaper').classList.contains('secband'), document.querySelector('.st-cpaper').classList.contains('hasband')]")
        out['sectx'] = pg.evaluate("()=>{const e=document.querySelector('.st-cpaper.secband .st-cin.st-csec'); return e ? getComputedStyle(e).color : null}")   # 371번. 확인 화면 분류 띠 글자 = 편집 화면과 같게 종이색
        out['pix'] = pg.evaluate("""async()=>{ const c=document.createElement('canvas'); c.width=600; c.height=800; const g=c.getContext('2d'); g.fillStyle='#f4f0e0'; g.fillRect(0,0,600,800); g.fillStyle='#6c6740'; g.font='bold 60px sans-serif'; g.fillText('행복한 그릇',150,80);
          const px=await pixOf(c.toDataURL('image/png')), t='색: 종이 #f4f0e0 · 글자 #222222 · 띠 없음\\n제목 위치: 20 3 · 80 13\\n[덮밥] 1\\n가츠동 | 8000';
          return [titlePix(px,[20,3,80,13]), titlePix(px,[0,50,100,60]), parseMenuText(t,px).look.title, parseMenuText(t).look.title||null, parseMenuText('색: 종이 #f4f0e0 · 글자 #222222 · 띠 없음\\n제목 위치: 20 3 · 80 13\\n[덮밥] 1\\n가츠동 | 8000',px).look.colors.paper] }""")   # 371번
        out['band372'] = pg.evaluate("""()=>{ const f=(col,pos)=>parseMenuText('색: 종이 #ffffff · 글자 #333333 · '+col+(pos?'\\n띠 위치: '+pos:'')+'\\n[덮밥] 1\\n가츠동 | 8000').look.band; return [f('띠 #c8b858 · 띠 없음','분류 제목'), f('띠 #c8b858','맨 위'), f('띠 #c8b858','없음'), f('띠 #c8b858 · 띠 없음',''), f('띠 #c8b858','')] }""")   # 372번
        pg.evaluate("()=>{const t=document.querySelector('[data-k=name]'); t.value='김치믹스동 (돈가츠 새우튀김 김치나베 덮밥) #Pork #Shrimp #Kimchi #Natto #Beef #Salmon #SliceRawFish'; t.dispatchEvent(new Event('input',{bubbles:true}))}"); pg.wait_for_timeout(200)
        pg.locator('[data-k=name]').first.click(); pg.keyboard.press('Enter'); pg.wait_for_timeout(100)
        out['wrap'] = pg.evaluate("()=>{const t=document.querySelector('[data-k=name]'); return [t.tagName === 'TEXTAREA', t.clientHeight > 30, t.scrollWidth <= t.clientWidth + 1, !/\\n/.test(t.value)]}")   # 363번. 긴 줄은 줄이 바뀌고 가로로 밀리지 않고 엔터는 막힌다
        out['ckt'] = pg.evaluate("()=>getComputedStyle(document.querySelector('#st-cshop')).color")   # 364번. 확인 화면 가게 이름에도 읽은 색
        pg.click('#st-check-go'); pg.wait_for_timeout(300)
        out['prev'] = pg.evaluate("()=>[getComputedStyle(document.querySelector('#st-prev')).color, document.querySelector('label[for=st-shop]').textContent.trim().slice(0, 5)]")   # 368번. 정하기 미리보기도 읽은 제목 색 · 칸 이름은 「파일 이름」
        out['fn373'] = pg.evaluate("""()=>{ const sh=document.querySelector('#st-shop'), p=document.querySelector('#st-fnprev'), d=new Date(), z=n=>String(n).padStart(2,'0'), ymd=d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate()), r=[]; const set=v=>{ sh.value=v; sh.dispatchEvent(new Event('input',{bubbles:true})); return p.textContent }; r.push(set('행복한 그릇')===('저장되는 파일: 행복한 그릇-메뉴-'+ymd+'.html')); r.push(set('')===('저장되는 파일: 메뉴판-'+ymd+'.html')); r.push(set('a/b:c?')===('저장되는 파일: abc-메뉴-'+ymd+'.html')); r.push(p.getBoundingClientRect().height>0); return r }""")   # 373번. 정하기 화면에 실제로 저장되는 파일 이름
        out['preset'] = pg.evaluate("()=>[PRESETS.photo.sec, PRESETS.photo.art, PRESETS.photo.noren]")
        pg.click('#st-go'); pg.wait_for_timeout(900); pg.evaluate("()=>document.querySelectorAll('.gd-x,.gd-skip').forEach(x=>x.click())"); pg.wait_for_timeout(300)
        out['final'] = pg.evaluate("()=>[SETTINGS.secStyle, JSON.stringify(SETTINGS.pages[0].arts)]")
        out['start'] = pg.evaluate("()=>[SETTINGS.pages[0].showSub, SETTINGS.pages[0].showHours, !!document.querySelector('.sheet .hours')]")   # 367번. 사진에 없던 한 줄 소개 · 영업시간은 꺼서 시작
        out['title'] = pg.evaluate("()=>[SETTINGS.pages[0].logoColor, SETTINGS.custom.logo, getComputedStyle(document.querySelector('.sheet .logo.txt')).color]")   # 364번. 읽은 가게 이름 색이 로고 색(직접)으로
        out['artin'] = pg.evaluate("()=>{const a=document.querySelector('.sheet .art').getBoundingClientRect(), g=document.querySelector('.sheet .guide').getBoundingClientRect(); return [a.bottom <= g.bottom + 1, a.right <= g.right + 1, a.left >= g.left - 1]}")   # 364번. 그림은 여백선 안
        pg.goto(url('p62_' + f)); pg.wait_for_timeout(400); pg.click('#st-photo'); pg.wait_for_timeout(200); cur[0] = T0
        pg.evaluate("(t)=>toCheck(t, document.querySelector('#st-appmsg'))", T0); pg.wait_for_timeout(300)
        out['none'] = pg.evaluate("()=>[stLook.sec || '', stLook.bandAt || '', stLook.art || '']")
    except Exception as e: out['fail'] = str(e)[:300]
    ctx.close(); return out

def t61(b, f):
    """354번 — 위쪽 [AI] 단추와 창: 점검 목록(중복 · 가격 · 맞춤법)을 누르면 종이의 그 줄로 가고 · [적용]으로 바로 고쳐지고(되돌리기) · [무시]가 되고 · 번역이 꾸미기 창이 아니라 이 창에 있고 ·
    [AI로 맞춤법 보기]가 이름 목록만 서버에 보내고(mode:typo) 종이에 있는 이름만 목록에 넣고 · 첫 화면에서 무시한 것이 넘어오고 · 서버가 맞춤법 모드를 갖는다. 353번 — PDF 여러 쪽(pdf.js 가 있을 때)이 쪽 탭 · 쪽마다 한 장으로"""
    import json as _j
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'p61_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))
    T = "가게: 시험 식당\n콘셉트: 한식\n방향: 세로\n단: 2\n글꼴: 명조\n색: 종이 #f5ecd7 · 글자 #2b2218 · 띠 없음\n점검: 육계장 → 육개장\n[식사] 1\n육계장 | 9000\n된장찌개 | 8000\n된장찌개 | 8000\n김치찌개 | 90000\n비빔밥 | 8000\n냉면 | 시가\n우동 | 얼마\n"
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000}); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e))); sent = []
    def rd(r):
        if r.request.method == 'GET': r.fulfill(status=200, content_type='application/json', body='{"enabled":true}'); return
        d = _j.loads(r.request.post_data); sent.append(d)
        if d.get('mode') == 'typo': r.fulfill(status=200, content_type='application/json', body=_j.dumps({'text': '- 비빔밥 → 비빈밥\n김치찌게 → 김치찌개\n없는이름 → 뭔가\n'})); return
        r.fulfill(status=200, content_type='application/json', body=_j.dumps({'text': T}))
    pg.route('**/api/read', rd)
    try:
        pg.goto(url('p61_' + f)); pg.wait_for_timeout(500); pg.click('#st-photo'); pg.wait_for_timeout(200)
        pg.evaluate("(t)=>toCheck(t, document.querySelector('#st-appmsg'))", T); pg.wait_for_timeout(300)
        out['ck_rows'] = pg.evaluate("()=>[...document.querySelectorAll('#st-cnotes .st-cnr .go')].length"); out['ck_h'] = pg.evaluate("()=>Math.round(document.querySelector('#st-cnotes').clientHeight)")   # 356번. 5건이 3줄 넘게 보이는 높이
        out['look'] = pg.evaluate("()=>{const p=document.querySelector('.st-cpaper'), g=document.querySelector('#st-stage'); return [p.classList.contains('looked'), p.classList.contains('hasband'), getComputedStyle(p).backgroundColor, g&&g.offsetHeight>0&&/단계입니다/.test(g.textContent)]}")   # 361번. 읽은 종이색을 비추고(띠 없음이면 띠 없이) · 이 화면이 확인 단계라는 안내
        pg.evaluate("()=>document.querySelector('#st-cnotes .st-cnr .go').click()"); pg.wait_for_timeout(200)
        out['ck_go'] = pg.evaluate("()=>document.querySelectorAll('#st-ctab .flash').length")
        pg.evaluate("()=>[...document.querySelectorAll('#st-cnotes .st-cnr')].find(r=>/우동/.test(r.textContent)).querySelector('.ab:not(.ap)').click()"); pg.wait_for_timeout(100)
        out['ck_ign'] = pg.evaluate("()=>[...document.querySelectorAll('#st-cnotes .st-cnr .go')].length")
        pg.click('#st-check-go'); pg.wait_for_timeout(300)
        out['sum'] = pg.evaluate("()=>[document.querySelector('#st-notes').textContent, []]")
        pg.click('#st-go'); pg.wait_for_timeout(900)
        pg.evaluate("()=>document.querySelectorAll('.gd-x,.gd-skip').forEach(x=>x.click())"); pg.wait_for_timeout(200)
        out['place'] = pg.evaluate("()=>[!!document.querySelector('#panel #f-lang'), !!document.querySelector('#aipanel #f-lang'), !!document.querySelector('#aipanel #f-tr'), !!document.querySelector('#b-ai'), document.querySelector('#b-ai').closest('.tb-right')!==null, !document.querySelector('#ai'), !document.querySelector('#aibar')]")   # 357번. 번역은 [AI] 창 · 안내창과 막대는 없다
        pg.click('#b-ai'); pg.wait_for_timeout(300)
        rows = lambda: pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-it')].map(x=>x.textContent)")
        out['open'] = pg.evaluate("()=>[document.querySelector('#aipanel').hidden, document.querySelector('#panel').hidden, document.querySelector('#aipanel').classList.contains('panel'), document.querySelectorAll('dialog[open]').length, document.querySelectorAll('#ai-list .aip-btns').length, document.querySelector('#b-ai').classList.contains('on')]")
        out['rows'] = rows()
        out['gh'] = pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-gh')].map(x=>x.textContent)")
        out['note'] = pg.evaluate("()=>[[...document.querySelectorAll('#ai-list .aip-note')].filter(x=>/AI 의견/.test(x.textContent)).length, [...document.querySelectorAll('#ai-list .aip-it')].filter(x=>/AI 의견/.test(x.textContent)).length]")
        # 종이는 그대로 스크롤된다 — 창이 뜬 채로 휠
        out['scroll'] = pg.evaluate("()=>{const d=document.scrollingElement; const o=d.scrollTop; d.scrollTop=o+120; return [d.scrollHeight>innerHeight ? d.scrollTop>o : true, getComputedStyle(document.body).overflow!=='hidden']}")
        pg.evaluate("()=>document.querySelectorAll('#ai-list .aip-it')[0].click()"); pg.wait_for_timeout(150)
        out['sel'] = pg.evaluate("()=>[document.querySelectorAll('#ai-list .aip-btns').length, document.querySelectorAll('#ai-list .aip-it.on').length, document.querySelectorAll('.aiflash').length, document.querySelectorAll('#ai-list .aip-btns button').length]")
        pg.click('#ai-typo'); pg.wait_for_timeout(600)
        out['sent'] = sent[-1]; out['rows2'] = rows(); out['sub'] = pg.inner_text('#ai-sub')
        # 적용(육계장) — 393번. 돈까스 → 돈가스는 외래어 표기라 걸러진다 — 그 줄을 고르면 [적용] [무시]가 거기에만 뜬다
        pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-it')].find(r=>/육계장/.test(r.textContent)).click()"); pg.wait_for_timeout(150)
        out['btn_only'] = pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-btns')].map(b=>b.closest('.aip-it').textContent.includes('육계장'))")
        pg.evaluate("()=>document.querySelector('#ai-list .aip-btns .ap').click()"); pg.wait_for_timeout(300)
        out['applied'] = pg.evaluate("()=>[MENU.sheets[0][0][0].items[0].name, [...document.querySelectorAll('.sheet [data-path$=\"items.0.name\"]')].map(x=>x.textContent)[0], undoStack.length>0, document.querySelectorAll('#ai-list .aip-it.on').length]")
        pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-it.done button')].find(b=>b.textContent==='되돌리기').click()"); pg.wait_for_timeout(300)   # 390번. 적용한 줄의 [되돌리기]
        out['undone'] = pg.evaluate("()=>MENU.sheets[0][0][0].items[0].name")
        # 무시 — 고른 줄만 빠지고 다음 줄이 골라진다
        n0 = len(rows()); pg.evaluate("()=>document.querySelectorAll('#ai-list .aip-it')[1].click()"); pg.wait_for_timeout(100)
        pg.evaluate("()=>document.querySelector('#ai-list .aip-btns button:last-child').click()"); pg.wait_for_timeout(200)
        out['ign'] = [n0, len(rows()), pg.evaluate("()=>document.querySelectorAll('#ai-list .aip-it.on').length")]
        # 꾸미기 창과 한자리 — 서로 열면 다른 쪽이 닫힌다 · 닫은 뒤 표시도 없다
        pg.click('#b-edit'); pg.wait_for_timeout(150); st1 = pg.evaluate("()=>[document.querySelector('#aipanel').hidden, document.querySelector('#panel').hidden, document.querySelectorAll('.aiflash').length]")
        pg.click('#b-ai'); pg.wait_for_timeout(150); st2 = pg.evaluate("()=>[document.querySelector('#aipanel').hidden, document.querySelector('#panel').hidden]")
        pg.click('#ai-close'); pg.wait_for_timeout(150); st3 = pg.evaluate("()=>[document.querySelector('#aipanel').hidden, document.querySelectorAll('.aiflash').length, document.querySelector('#b-ai').classList.contains('on')]")
        out['swap'] = [st1, st2, st3]
        pg.click('#b-ai'); pg.wait_for_timeout(200)
        pg.emulate_media(media='print'); out['print'] = pg.evaluate("()=>getComputedStyle(document.querySelector('#aipanel')).display"); pg.emulate_media(media='screen')
        out['save'] = pg.evaluate("()=>{const c=cleanForSave(document.documentElement.cloneNode(true)); const b=c.querySelector('#aipanel'); return [b.hasAttribute('hidden'), c.querySelector('#ai-list').textContent, c.querySelectorAll('.aiflash').length]}")
        # 번역은 창 안에서
        pg.select_option('#aipanel #f-lang', 'en'); pg.wait_for_timeout(200)
        out['lang'] = pg.evaluate("()=>[SETTINGS.lang2, document.querySelector('#f-tr').disabled]")
        # 359번 — 한글 이름 끝에 붙은 영문자는 AI 없이도 잡고(단위 ml 은 안 잡고) · 빈 목록은 맞춤법을 아직 안 봤다고 말하고 · 줄에는 이름표(틀린 곳/이렇게/이유)가 있다
        out['stray'] = pg.evaluate("""()=>{const pg=[{n:1,secs:[{name:'식사',items:[{name:'야끼소바dd',price:9000},{name:'하이볼 280ml',price:9000},{name:'생맥주L',price:9000},{name:'우동',price:9000}]}],typos:[]}];
          const L=menuFindings(pg).filter(f=>f.kind==='typo'); return [L.length, L[0]&&L[0].from, L[0]&&L[0].to, !!(L[0]&&L[0].why)]}""")
        pg.evaluate("()=>{aiTypoRan=false; aiSel='x'; MENU.sheets.forEach((s,si)=>s.forEach((c,ci)=>c.forEach((sec,k)=>{sec.items=(si+ci+k===0)?[{name:'우동',price:9000}]:[]})));render(); aiDraw();}")
        out['empty'] = pg.inner_text('#ai-list')
        pg.evaluate("()=>{MENU.sheets[0][0][0].items=[{name:'야끼소바dd',price:9000},{name:'우동',price:9000}]; render(); aiDraw(); document.querySelector('#ai-list .aip-it').click()}"); pg.wait_for_timeout(100)
        out['labels'] = pg.evaluate("()=>[...document.querySelectorAll('#ai-list .aip-it.on .ln b')].map(b=>b.textContent)")
        # 360번 — 상호명 · 도장: 읽은 맨 위 글이 가게 이름이면 상호명에 · 「메뉴」 · 「안주」 면 비워 두고 · 상호명도 글자도 없으면 도장은 「메뉴」 글자 대신 기호
        out['shoplike'] = pg.evaluate("()=>['행복한 그릇','솔밭식당','바다향 횟집','메뉴','안주','메뉴판','밥','사이드 메뉴','주류 · 음료','안주류'].map(stShopLike)")
        out['sealsym'] = pg.evaluate("()=>{const keep=MENU.brand.shop; delete MENU.brand.shop; const a=sealHTML({seal:'word'}), b=sealHTML({seal:'word',text:'알프스'}); MENU.brand.shop='솔밭식당'; const c=sealHTML({seal:'word'}); if(keep) MENU.brand.shop=keep; else delete MENU.brand.shop; return [a.includes('<text')||a.includes('메'), b.includes('알'), c.includes('솔')]}")
        pg.click('#ai-close')
        out['mem'] = pg.evaluate("()=>[aiTypos.length, aiIgnore.size]")
    except Exception as e:
        out['fail'] = str(e)[:300]
    # 356번 — 폰 폭(360 · 390 · 430): 위쪽 막대 단추가 화면 안에 다 들어오고, 점검 줄 글이 줄끼리 겹치지 않는다
    out['narrow'] = {}
    for W in (360, 390, 430):
        try:
            pg2 = ctx.new_page(); pg2.set_viewport_size({'width': W, 'height': 844}); pg2.on('pageerror', lambda e: out['err'].append(str(e)))
            pg2.goto(url(f)); pg2.wait_for_timeout(500)
            pg2.evaluate("()=>{MENU.sheets[0][0][0].items[0].price=''; MENU.sheets[0][0][0].items[1].price='abc'; MENU.sheets[0][0][0].items[2].price=1; MENU.sheets[0][0][0].items[3].price=900000; render(); document.querySelector('#b-ai').click()}"); pg2.wait_for_timeout(300)
            out['narrow'][W] = pg2.evaluate("""()=>{const r=document.querySelector('#aipanel').getBoundingClientRect(); return [['#b-file','#b-style','#b-ai','#b-edit','#b-print','#b-help'].map(s=>Math.round(document.querySelector(s).getBoundingClientRect().right)).every(x=>x<=innerWidth),
              [...document.querySelectorAll('#ai-list .aip-it')].every(g=>g.scrollWidth<=g.clientWidth+1), document.querySelectorAll('#ai-list .aip-it').length, r.left>=0 && r.right<=innerWidth && r.top>=0]}""")
            pg2.close()
        except Exception as e: out['narrow'][W] = str(e)[:100]
    ctx.close()
    try: sv = open('api/read.js', encoding='utf-8').read(); out['server'] = ['mode === "typo"' in sv, 'TYPO' in sv and 'maxOutputTokens: typo' in sv, 'MAX_NAMES' in sv]
    except Exception: out['server'] = None
    return out

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

# ───────────────────────── 71. 402번 — 자유 배치(그림 · 도장 · QR) · QR 이름 위 · 아래 · 원산지 줄
#   ① 꾸미기 창 「종이 위 자리」 탭을 열면 물건마다 손잡이 ② 손잡이를 마우스로 끌면 pos 가 생기고 갈색 점선 안에 머문다(밖으로 끌어도)
#   ③ 화면과 인쇄의 자리가 같고 손잡이는 인쇄에 안 나온다 ④ [칸] 은 pos 를 지우고 [자유 배치] 는 제자리 그대로 pos 를 만든다
#   ⑤ 가로로 바꿔도 점선 안 ⑥ 망가진 pos 는 버리거나 0 ~ 1 로 ⑦ QR 이름 위 = 이름이 코드보다 먼저 ⑧ 원산지: 투명도 1 · 편집 윗선 폭 = 미리보기 · 비어도 높이 그대로
T71_IN = """()=>{const s=document.querySelector('.sheet[data-pi="0"]'),g=s.querySelector('.guide').getBoundingClientRect();
  return [...s.querySelectorAll('.free')].map(n=>{const r=visRect(n) /* 403번 — 그림은 그려진 부분이 점선 안(도화지 빈 곳은 밖으로 나가도 된다) */; return [n.classList.contains('art')?'art':n.classList.contains('seal')?'seal':'qr', r.left>=g.left-1 && r.right<=g.right+1 && r.top>=g.top-1 && r.bottom<=g.bottom+1]})}"""
T71_MM = """()=>{const s=document.querySelector('.sheet[data-pi="0"]'),S=s.getBoundingClientRect(),k=S.width/(s.classList.contains('land')?297:210);
  return [...s.querySelectorAll('.free')].map(n=>{const r=n.getBoundingClientRect(); return [+((r.left-S.left)/k).toFixed(1), +((r.top-S.top)/k).toFixed(1)]})}"""
def t71(b, f):
    out = {}
    c = Ctx(b, f, W=1600, H=1100); pg = c.pg
    c.js("()=>{ P(0).qrs=[{cell:4,kind:'url',url:'naver.me/abcd',label:'와이파이'}]; MENU.feet[0].origin='돼지고기 국내산'; P(0).showOrigin=true; render(); }")
    pg.click('#b-edit'); pg.wait_for_timeout(250)
    c.js("()=>{ panelTab='deco'; syncPageTabs(); syncPage(); }"); pg.wait_for_timeout(250)
    out['handles'] = c.js("""()=>[...document.querySelectorAll('.sheet[data-pi="0"] .mvh')].filter(h=>getComputedStyle(h).display!=='none').map(h=>h.dataset.kind).sort()""")
    c.js("()=>{ panelTab='look'; syncPageTabs(); syncPage(); }"); out['hidden_other_tab'] = c.js("""()=>[...document.querySelectorAll('.sheet[data-pi="0"] .mvh')].every(h=>getComputedStyle(h).display==='none')""")
    c.js("()=>{ panelTab='deco'; syncPageTabs(); syncPage(); }"); pg.wait_for_timeout(200)
    def drag(kind, cell, dx, dy):
        h = pg.query_selector(f'.sheet[data-pi="0"] .mvh[data-kind="{kind}"][data-cell="{cell}"]'); h.scroll_into_view_if_needed(); bx = h.bounding_box()
        x, y = bx['x'] + bx['width'] / 2, bx['y'] + bx['height'] / 2
        pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x + dx / 2, y + dy / 2, steps=4); pg.mouse.move(x + dx, y + dy, steps=4); pg.mouse.up(); pg.wait_for_timeout(250)
    ac, sc = c.js("()=>P(0).arts[0].cell"), c.js("()=>P(0).seals[0].cell")
    drag('art', ac, -250, -300); drag('seal', sc, -3000, 3000); drag('qr', 4, 200, -400)   # 도장은 점선 밖(왼쪽 아래 멀리)으로 끈다
    out['pos'] = c.js("()=>[!!P(0).arts[0].pos, !!P(0).seals[0].pos, !!P(0).qrs[0].pos, P(0).seals[0].pos]")
    out['inbox'] = c.js(T71_IN)
    out['sel'] = c.js("()=>[panelCell, panelTop, [...document.querySelectorAll('#f-qrpos button.on')].map(b=>b.dataset.k)]")
    scr = c.js(T71_MM); pg.emulate_media(media='print'); prt = c.js(T71_MM)
    out['print'] = [scr == prt, c.js("""()=>[...document.querySelectorAll('.mvh')].every(h=>getComputedStyle(h).display==='none')""")]; pg.emulate_media(media='screen')
    pg.click('#f-qrlabpos button[data-k="top"]'); pg.wait_for_timeout(200)
    out['labtop'] = c.js("""()=>{const q=document.querySelector('.sheet[data-pi="0"] .qr'); return [P(0).qrs[0].lab, q.firstElementChild.className]}""")
    c.js("()=>{ panelCell=P(0).arts[0].cell; panelTop=null; syncPage(); }")
    pg.click('#f-artpos button[data-k="cell"]'); pg.wait_for_timeout(200); out['back_cell'] = c.js("()=>'pos' in P(0).arts[0]")
    r0 = c.js("""()=>{const r=document.querySelector('.sheet[data-pi="0"] .art').getBoundingClientRect(); return [r.left, r.top]}""")
    pg.click('#f-artpos button[data-k="free"]'); pg.wait_for_timeout(200)
    r1 = c.js("""()=>{const r=document.querySelector('.sheet[data-pi="0"] .art').getBoundingClientRect(); return [r.left, r.top]}""")
    out['free_here'] = [c.js("()=>!!P(0).arts[0].pos"), abs(r0[0] - r1[0]) < 1 and abs(r0[1] - r1[1]) < 1]
    c.js("()=>{ SETTINGS.orient='landscape'; render(); }"); pg.wait_for_timeout(250); out['land_inbox'] = c.js(T71_IN)
    out['norm'] = c.js("""()=>{ const a={arts:[{cell:0,art:'beer',pos:{x:'a',y:2}},{cell:1,art:'beer',pos:{x:3,y:-1}}],seals:[{cell:2,seal:'word',pos:null}],qrs:[{cell:5,kind:'url',url:'a.b',lab:'top',pos:{x:.25,y:.5}},{cell:4,kind:'url',url:'a.b',lab:'left'}]};
      normArts(a,[]); normSeals(a,[]); normQrs(a); return JSON.stringify([a.arts,a.seals,a.qrs]) }""")
    out['err'] = list(c.errs); c.close()
    # 원산지 — 투명도 · 윗선 폭 · 빈 칸 높이
    c = Ctx(b, f, W=1600, H=1000); pg = c.pg
    M = """()=>{const f=document.querySelector('.sheet .foot'),o=f.querySelector('.origin'); return [+f.getBoundingClientRect().height.toFixed(1), +o.getBoundingClientRect().width.toFixed(1), getComputedStyle(o).opacity, getComputedStyle(o.querySelector('b')).opacity]}"""
    c.js("()=>{ P(0).showOrigin=true; MENU.feet[0].origin=''; render(); }"); pg.click('#b-edit'); pg.wait_for_timeout(250); e0 = c.js(M)
    c.js("()=>{ MENU.feet[0].origin='돼지고기 국내산'; render(); }"); pg.wait_for_timeout(200); e1 = c.js(M)
    pg.click('#b-preview'); pg.wait_for_timeout(200); p1 = c.js(M)
    out['origin'] = [e0, e1, p1]
    out['err'] += c.errs; c.close()
    return out

# ───────────────────────── 72. 403번 — 자유 배치에서 그림은 **실제로 그려진 부분**이 갈색 점선에 닿는다 · 꾸미기 창 상자
#   ① `ART_VIS` 표 = 그림마다 다시 잰 값(알파 8 넘는 화소, 오차 2) ② 구석(0,0 · 1,0 · 0,1 · 1,1)에서 그려진 부분이 점선 안이고 그 변에 닿는다(세로 · 가로)
#   ③ 손잡이 가운데 = 그려진 부분 가운데 ④ 칸에 있던 그림을 손잡이로 점선 모서리까지 끌면 닿는다 ⑤ 칸 배치의 그림 상자는 그대로(상자 폭 = 여백선 안쪽의 반)
#   ⑥ 꾸미기 창: 칸 이름표 · 그림 / 모퉁이+도장 · QR 이 상자 · 이름 「그림 자리」 「도장 자리」 「QR 자리」 · 모퉁이 아래 설정이 한 상자로 이어짐
T72_RECT = """(keys)=>{ const res=[]; for (const o of ['portrait','landscape']){ SETTINGS.orient=o;
    for (const k of keys.slice(0, o==='portrait' ? 99 : 3)) for (const [x,y] of [[0,0],[1,0],[0,1],[1,1]]){
      P(0).arts=[{cell:2,art:k,pos:{x,y}}]; render();
      const sh=document.querySelector('.sheet[data-pi="0"]'), g=sh.querySelector('.guide').getBoundingClientRect(), n=sh.querySelector('.art'), r=visRect(n), e=1.5;
      res.push([o,k,x,y, r.left>=g.left-e && r.right<=g.right+e && r.top>=g.top-e && r.bottom<=g.bottom+e,
        Math.abs((x?r.right-g.right:r.left-g.left))<=e, Math.abs((y?r.bottom-g.bottom:r.top-g.top))<=e]); } }
  SETTINGS.orient='portrait'; return res }"""
def t72(b, f):
    out = {}
    c = Ctx(b, f, W=1600, H=1100); pg = c.pg
    out['table'] = c.js("""async()=>{ const bad=[]; for (const k of Object.keys(ART)){ let s=ART[k]; if (typeof s!=='string' || k==='none') continue;
        s=s.replace('<svg ','<svg width="880" height="520" color="#000" ').replace(/currentColor/g,'#000'); const img=new Image(); img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s);
        try { await img.decode() } catch(e){ bad.push([k,'decode']); continue }
        const cv=document.createElement('canvas'); cv.width=880; cv.height=520; const x=cv.getContext('2d'); x.drawImage(img,0,0); const d=x.getImageData(0,0,880,520).data; let x0=880,y0=520,x1=-1,y1=-1;
        for (let y=0;y<520;y++) for (let xx=0;xx<880;xx++) if (d[(y*880+xx)*4+3]>8){ if(xx<x0)x0=xx; if(xx>x1)x1=xx; if(y<y0)y0=y; if(y>y1)y1=y }
        const v=ART_VIS[k], m=[x0,y0,x1+1,y1+1]; if (!v || v.some((a,i)=>Math.abs(a-m[i])>2)) bad.push([k,v,m]) }
      const miss=Object.keys(ART_VIS).filter(k=>!(k in ART)); return [bad, miss, Object.keys(ART).filter(k=>k!=='none').length, Object.keys(ART_VIS).length] }""")
    pg.click('#b-edit'); pg.wait_for_timeout(250)   # 점선(.guide)은 편집 중에만 그려진다
    out['rect'] = c.js(T72_RECT, ['bridge', 'cake', 'horse', 'ibex', 'cabin', 'soju', 'mountain', 'bingsu'])
    out['box'] = c.js("""()=>{ SETTINGS.orient='portrait'; P(0).arts=[{cell:2,art:'bridge'},{cell:3,art:'beer'}]; render(); const sh=document.querySelector('.sheet[data-pi="0"]'), S=sh.getBoundingClientRect(), k=S.width/210;
        return [...sh.querySelectorAll('.art')].map(n=>{const r=n.getBoundingClientRect(); return [+((r.right-r.left)/k).toFixed(1), +((r.left-S.left)/k).toFixed(1)]}) }""")   # 칸 배치: 폭 91mm · 왼쪽 칸 14mm · 오른쪽 칸 105mm
    c.js("()=>{ P(0).arts=[{cell:2,art:'bridge'},{cell:3,art:'cake'}]; P(0).seals=[]; delete P(0).qrs; render(); }")
    c.js("()=>{ panelTab='deco'; panelPage=0; panelTop=null; panelCell=2; syncPageTabs(); syncPage(); }"); pg.wait_for_timeout(250)
    out['handle'] = c.js("""()=>[...document.querySelectorAll('.sheet[data-pi="0"] .mvh[data-kind="art"]')].map(h=>{ const n=document.querySelector('.sheet[data-pi="0"] .art[data-cell="'+h.dataset.cell+'"]'), r=visRect(n), b=h.getBoundingClientRect();
        return Math.abs(b.left+b.width/2-(r.left+r.width/2))<1.2 && Math.abs(b.top+b.height/2-(r.top+r.height/2))<1.2 })""")
    h = pg.query_selector('.sheet[data-pi="0"] .mvh[data-kind="art"][data-cell="2"]'); h.scroll_into_view_if_needed(); bx = h.bounding_box(); x, y = bx['x'] + bx['width'] / 2, bx['y'] + bx['height'] / 2
    pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x - 400, y - 400, steps=5); pg.mouse.move(x - 3000, y - 3000, steps=5); pg.mouse.up(); pg.wait_for_timeout(250)
    out['drag'] = c.js("""()=>{ const sh=document.querySelector('.sheet[data-pi="0"]'), g=sh.querySelector('.guide').getBoundingClientRect(), r=visRect(sh.querySelector('.art[data-cell="2"]')); return [P(0).arts[0].pos, Math.abs(r.left-g.left)<=1.5, Math.abs(r.top-g.top)<=1.5] }""")
    out['panel'] = c.js("""()=>{ panelCell=5; panelTop=null; P(0).qrs=[{cell:5,kind:'url',url:'naver.me/abcd'}]; P(0).seals=P(0).seals.filter(k=>k.cell!==5); render(); syncPage();
        const A=document.querySelector('#art-cell'), bx=[...A.querySelectorAll('.cellblk')].filter(x=>!x.hidden), bd=x=>getComputedStyle(x).borderTopWidth==='1px' && parseFloat(getComputedStyle(x).paddingLeft)>=10, T=id=>document.querySelector(id).textContent.trim(),
          cor=A.querySelector('#corner-row').getBoundingClientRect(), nxt=bx[bx.length-1].getBoundingClientRect(), nm=A.querySelector('#art-cellname');
        return [bx.length, bx.every(bd), T('#l-gart').startsWith('칸 고르기'), T('#l-artpos'), T('#l-sealpos'), T('#l-qrpos'), Math.abs(nxt.top-cor.bottom)<=1.5, getComputedStyle(nm).backgroundColor!=='rgba(0, 0, 0, 0)', nm.textContent,
          getComputedStyle(A.querySelector('#h-qr small')).display, T('#h-qrt')] }""")
    out['err'] = list(c.errs); c.close()
    return out

def near(x, y, t): return abs(x - y) <= t
# ───────────────────────── 58. QR (337 · 340번)
def t58(b, f):
    """만든 QR 을 읽는 도구(zxing-cpp)로 **다시 읽어** 넣은 값 그대로인지 · **자리**(위 칸 = 그 단 맨 위 · 아래 칸 = 바닥 글 옆 · 가운데 칸은 못 둔다) · 글자와 안 겹침 ·
    「한 장에 맞춤」이 QR 자리를 피함 · 20 ~ 30mm · 한 칸에 도장과 QR 하나만 · 꾸미기 창(도장 · QR 한 줄) · 저장했다 열어도 남는지 · 망가진 값 정리"""
    out = {'err': []}
    try: import zxingcpp  # type: ignore
    except Exception: out['no_reader'] = True; return out
    ctx = b.new_context(viewport={'width': 1400, 'height': 1300}, device_scale_factor=3, accept_downloads=True); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    def read(sel):
        png = pg.query_selector(sel).screenshot(); return [x.text for x in zxingcpp.read_barcodes(Image.open(io.BytesIO(png)).convert('RGB'))]
    def esc(v): return re.sub(r'([\\;,:"])', r'\\\1', v)
    def wifi(ssid, pw, enc): return 'WIFI:T:%s;S:%s;%s;' % ('nopass' if enc == 'nopass' else 'WPA', esc(ssid), '' if enc == 'nopass' else 'P:' + esc(pw) + ';')
    try:
        pg.goto(url(f)); pg.wait_for_timeout(300)
        cases = [({'kind': 'url', 'url': 'naver.me/abcd'}, 'https://naver.me/abcd'),
                 ({'kind': 'url', 'url': 'https://map.naver.com/p/search/알프스 흑석'}, 'https://map.naver.com/p/search/알프스 흑석'),
                 ({'kind': 'url', 'url': 'tel:01012345678'}, 'tel:01012345678'),
                 ({'kind': 'wifi', 'ssid': '알프스 5G', 'pass': 'a;b:c,d"e\\f', 'enc': 'WPA'}, wifi('알프스 5G', 'a;b:c,d"e\\f', 'WPA')),
                 ({'kind': 'wifi', 'ssid': 'cafe', 'pass': '', 'enc': 'nopass'}, wifi('cafe', '', 'nopass'))]
        out['read'] = []
        for q, want in cases:
            q = dict(q, cell=5, label='러닝 코스')
            pg.evaluate("(q)=>{P(0).qrs=[q]; render(); topBands();}", q); pg.wait_for_timeout(150)
            out['read'].append(read('.sheet[data-pi="0"] .qr svg') == [want])
        out['none_drawn'] = [pg.evaluate("()=>{P(0).qrs=[{cell:1,kind:'url',url:'ftp://x'},{cell:4,kind:'wifi',ssid:''},{cell:5,kind:'url',url:''}]; render(); return document.querySelectorAll('.sheet[data-pi=\"0\"] .qr').length}"),
                             pg.evaluate("()=>{P(0).qrs=[{cell:1,kind:'url',url:'x'.repeat(300)}]; render(); return document.querySelectorAll('.sheet[data-pi=\"0\"] .qr').length}")]   # 못 읽는 주소 · 빈 칸은 안 그린다 · 300자도 그려진다
        bad = []
        for o in ('portrait', 'landscape'):
            pg.evaluate("(o)=>{SETTINGS.orient=o; applyLook(); P(0).scale=0.55; render(); topBands();}", o); pg.wait_for_timeout(150)   # 알프스 1쪽은 빽빽해 QR 자리가 생기면 넘친다 · 글자를 줄여 놓고 자리만 본다
            for c in (0, 1, 4, 5):
                r = pg.evaluate("""(c)=>{ P(0).qrs=[{cell:c,kind:'url',url:'naver.me/abcd',label:'네이버 지도'}]; P(0).seals=[0,1,2,3,4,5].filter(k=>k!==c).map(k=>({cell:k,seal:'word'})); normQrs(P(0)); render(); topBands();
                  const sh=document.querySelector('.sheet[data-pi="0"]'), q=sh.querySelector('.qr'), s=sh.getBoundingClientRect(), b=q.getBoundingClientRect(), fo=sh.querySelector('.foot');
                  const sl=[...sh.querySelectorAll('.seal:not(.blank)')].map(e=>e.getBoundingClientRect()).filter(e=>Math.min(e.right,b.right)-Math.max(e.left,b.left)>1 && Math.min(e.bottom,b.bottom)-Math.max(e.top,b.top)>1).length;
                  const tx=[...sh.querySelectorAll('[data-path], .noren .logo')].filter(t=>!q.contains(t)&&(t.textContent.trim()||t.classList.contains('logo'))&&t.offsetParent).filter(t=>{const e=t.getBoundingClientRect(); return e.width>0&&Math.min(b.right,e.right)-Math.max(b.left,e.left)>2&&Math.min(b.bottom,e.bottom)-Math.max(b.top,e.top)>2}).length;
                  return {inside:b.left>=s.left-.5&&b.right<=s.right+.5&&b.top>=s.top-.5&&b.bottom<=s.bottom+.5, inHeader:!!q.closest('.noren'), inFoot:!!(fo&&fo.contains(q)), mm:b.width/96*25.4, want:Math.min(30,Math.max(20,(+q.dataset.n)*0.5)), seal:sl, text:tx, sealInCell:(P(0).seals||[]).some(x=>x.cell===c)}}""", c)
                place = (r['inHeader'] and not r['inFoot']) if c < 4 else r['inFoot']
                if not (r['inside'] and place and r['seal'] == 0 and r['text'] == 0 and abs(r['mm'] - r['want']) < 0.3 and not r['sealInCell']): bad.append((o, c, r))
        out['layout_bad'] = bad
        pg.evaluate("()=>{SETTINGS.orient='portrait'; applyLook(); P(0).scale=1; P(0).seals=[]; delete P(0).qrs; render(); topBands();}")
        # 「한 장에 맞춤」이 QR 자리를 피하는지(완성본) — 338번 판은 아래 칸에서 글자가 QR 에 닿았다
        fit_bad = []
        for cells in ([0], [1], [0, 1], [4], [5], [4, 5], [0, 5]):
            r = pg.evaluate("""(cells)=>{ P(0).qrs=cells.map(c=>({cell:c,kind:'url',url:'naver.me/abcd',label:'네이버 지도'})); P(0).autofit=true; syncControls(); applyLook(); render(); fitNow(); applyScale(); topBands();
              document.body.classList.add('preview'); const sh=document.querySelector('.sheet[data-pi="0"]'); let n=0;
              sh.querySelectorAll('.qr').forEach(q=>{const b=q.getBoundingClientRect(); sh.querySelectorAll('[data-path], .noren .logo').forEach(t=>{ if(q.contains(t)||!(t.textContent.trim()||t.classList.contains('logo'))||!t.offsetParent) return; const e=t.getBoundingClientRect(); if(e.width>0&&Math.min(b.right,e.right)-Math.max(b.left,e.left)>2&&Math.min(b.bottom,e.bottom)-Math.max(b.top,e.top)>2) n++; }); });
              const o=overA4(0); document.body.classList.remove('preview'); return {n, over:o, scale:P(0).scale}}""", cells)
            if r['n'] or r['over']: fit_bad.append((cells, r))
        out['fit_bad'] = fit_bad
        out['mid'] = pg.evaluate("()=>{const g={qrs:[{cell:2,kind:'url',url:'a.kr'},{cell:3,kind:'url',url:'a.kr'},{cell:1,kind:'url',url:'a.kr'}]}; normQrs(g); return (g.qrs||[]).map(x=>x.cell)}")   # 가운데 칸 QR 은 버린다
        # 꾸미기 창 — 격자 한 그림(344번): 맨 위 좌우 끝 = QR 만 · 칸 = 그림 + 도장 · 아래 두 칸 = 그림 + 모퉁이(없음 | 도장 | QR 중 하나)
        pg.evaluate("()=>{P(0).autofit=false; delete P(0).qrs; P(0).seals=[]; render(); document.querySelector('#b-edit').click(); panelPage=0; panelTab='deco'; panelTop=null; panelCell=2; syncPageTabs(); syncPage();}"); pg.wait_for_timeout(250)
        V = "()=>({art:!document.querySelector('[aria-labelledby=h-cart]').hidden, corner:!document.querySelector('#corner-row').hidden, seal:!document.querySelector('.sealblk').hidden, qr:!document.querySelector('.qrblk').hidden, slot:qrSlot, on:(document.querySelector('#f-corner .on')||{dataset:{}}).dataset.k||null, name:document.querySelector('#art-cellname').textContent})"
        cell = lambda n: pg.evaluate("(c)=>{document.querySelectorAll('#g-art .pcells > button')[c].click()}", n)
        topk = lambda k: pg.evaluate("(k)=>{document.querySelectorAll('#g-art .pband .qs')[k].click()}", k)
        pn = []
        tabs = pg.evaluate("()=>[[...document.querySelectorAll('#ptabs button')].map(b=>b.textContent), document.querySelector('#ptabs').scrollWidth <= document.querySelector('#ptabs').clientWidth + 1, [...document.querySelectorAll('#ptabs .ptab-btn + .ptab-btn')].every(b=>getComputedStyle(b,'::before').borderLeftWidth==='1px')]")
        pn.append(tabs[0] == ['색 · 글꼴', '맨 위', '메뉴', '바닥', '그림·도장·QR'] and tabs[1] is True and tabs[2] is True)   # 탭 다섯이 한 줄 · 사이마다 구분선
        v = pg.evaluate(V); pn.append(v['art'] and not v['corner'] and v['seal'] and not v['qr'])   # 위 · 가운데 칸 = 그림 + 도장
        topk(0); pg.wait_for_timeout(150); v = pg.evaluate(V); pn.append(not v['art'] and not v['corner'] and not v['seal'] and v['qr'] and v['slot'] == 0 and v['name'] == '맨 위 왼쪽 — QR 자리')   # 맨 위 자리 = QR 만
        pg.click('#f-qrkind button[data-k="url"]'); pg.fill('#f-qrurl', 'instagram.com/alps'); pg.fill('#f-qrlabel', '인스타'); pg.wait_for_timeout(200)
        pn.append(pg.evaluate("()=>[JSON.stringify(P(0).qrs), document.querySelectorAll('.sheet[data-pi=\"0\"] .noren .qr.qh').length, document.querySelectorAll('#g-art .pband .qs.has').length]") == ['[{"cell":0,"kind":"url","url":"instagram.com/alps","label":"인스타"}]', 1, 1])   # 종이에 · 격자에 둘 다 보인다
        topk(1); pg.wait_for_timeout(150); v = pg.evaluate(V); pn.append(v['slot'] == 1 and v['qr'])
        pg.click('#f-qrkind button[data-k="wifi"]'); pg.wait_for_timeout(150); pg.fill('#f-qrssid', '알프스'); pg.select_option('#f-qrenc', 'nopass'); pg.wait_for_timeout(200)
        pn.append(pg.evaluate("()=>[JSON.stringify(P(0).qrs), document.querySelectorAll('.sheet[data-pi=\"0\"] .noren .qr.qh').length]") == ['[{"cell":0,"kind":"url","url":"instagram.com/alps","label":"인스타"},{"cell":1,"kind":"wifi","ssid":"알프스","pass":"","enc":"nopass"}]', 2])
        # 아래 칸의 모퉁이 — 하나만
        cell(4); pg.wait_for_timeout(150); v = pg.evaluate(V); pn.append(v['art'] and v['corner'] and v['on'] == 'none' and not v['seal'] and not v['qr'])
        pg.click('#f-corner button[data-k="seal"]'); pg.wait_for_timeout(200); v = pg.evaluate(V)
        pn.append(v['on'] == 'seal' and v['seal'] and not v['qr'] and pg.evaluate("()=>[!!sealAt(P(0),4), !qrAt(P(0),4)]") == [True, True])
        pg.click('#f-corner button[data-k="qr"]'); pg.wait_for_timeout(250); v = pg.evaluate(V)
        pn.append(v['on'] == 'qr' and v['qr'] and not v['seal'] and v['slot'] == 4 and pg.evaluate("()=>[!sealAt(P(0),4), !!qrAt(P(0),4), !!document.querySelector('#g-art .pcells > button:nth-child(5) .pqr')]") == [True, True, True])   # QR 을 고르면 그 모퉁이 도장이 빠지고 격자에 QR 표시
        pg.click('#f-corner button[data-k="seal"]'); pg.wait_for_timeout(250)
        pn.append(pg.evaluate("()=>[!!sealAt(P(0),4), !qrAt(P(0),4)]") == [True, True])   # 도장을 고르면 QR 이 빠진다
        pg.click('#f-corner button[data-k="none"]'); pg.wait_for_timeout(200)
        pn.append(pg.evaluate("()=>[!sealAt(P(0),4), !qrAt(P(0),4)]") == [True, True])
        # 346번 — QR 이 놓일 수 있는 네 곳이 그림에 항상 보인다(맨 위 좌우 끝 · 비어 있는 아래 두 모퉁이) · 누르기 쉬운 크기 · 아래 점선 상자를 누르면 바로 그 모퉁이가 QR · 도장이 있으면 상자 대신 도장
        hint = lambda n: pg.evaluate("(c)=>document.querySelectorAll('#g-art .pcells > button')[c].querySelectorAll('.pqr.hint').length", n)
        pn.append(hint(4) == 1 and hint(5) == 1 and hint(0) == 0 and hint(2) == 0)
        pn.append(pg.evaluate("()=>{const E=[...document.querySelectorAll('#g-art .pband .qs'), ...document.querySelectorAll('#g-art .pqr.hint')]; return E.length===4 && E.every(e=>{const r=e.getBoundingClientRect(); return Math.abs(r.width-r.height)<0.6 && Math.abs(r.width-24)<0.6 && (e.classList.contains('has') || e.classList.contains('hint') || getComputedStyle(e,'::after').content.includes('QR'))})}"))   # 347번 — 맨 위 좌우 끝과 아래 모퉁이의 QR 자리는 모두 크기가 같은 정사각형(24px)
        pg.evaluate("()=>{document.querySelectorAll('#g-art .pcells > button')[4].querySelector('.pqr.hint').click()}"); pg.wait_for_timeout(250); v = pg.evaluate(V)
        pn.append(v['on'] == 'qr' and v['qr'] and v['slot'] == 4 and pg.evaluate("()=>!!qrAt(P(0),4)") and hint(4) == 0)
        pg.click('#f-corner button[data-k="seal"]'); pg.wait_for_timeout(250); pn.append(hint(4) == 0 and pg.evaluate("()=>!!sealAt(P(0),4)"))
        pg.click('#f-corner button[data-k="none"]'); pg.wait_for_timeout(200); pn.append(hint(4) == 1)
        okc = True
        for n in (0, 1, 2, 3): cell(n); pg.wait_for_timeout(80); okc = okc and not pg.evaluate(V)['corner']
        pn.append(okc)   # 위 · 가운데 칸에는 모퉁이 선택이 없다
        pg.evaluate("()=>{P(0).seals=[{cell:0,seal:'word'}]; render(); syncPage();}"); pg.wait_for_timeout(150)
        pn.append(pg.evaluate("()=>[document.querySelectorAll('.sheet[data-pi=\"0\"] .seal:not(.blank)').length, document.querySelectorAll('.sheet[data-pi=\"0\"] .noren .qr.qh').length]") == [1, 2])   # 맨 위 QR 은 같은 번호 도장과 둘 다
        out['panel'] = pn
        # 저장했다 열어도 남는지
        pg.evaluate("()=>{P(0).qrs=[{cell:5,kind:'wifi',ssid:'알프스',pass:'pw;1',enc:'WPA',label:'와이파이'}]; render(); touch();}")
        with pg.expect_download() as d: pg.click('#b-file'); pg.click('#b-save')
        d.value.save_as(D + 'qr_saved.html'); pg.goto(url('qr_saved.html')); pg.wait_for_timeout(300)
        out['saved'] = [pg.evaluate("()=>JSON.stringify(P(0).qrs)"), pg.evaluate("()=>document.querySelectorAll('.sheet[data-pi=\"0\"] .qr').length")]
        # 망가진 값 · 337번 판에서 도장과 QR 을 둘 다 둔 파일
        # **불러오는 순간** — 저장 데이터(파일 안 설정)에 QR 이 들어 있고 같은 아래 구석에 도장도 있는 파일을 연다. 343번에 정리 함수가 const 로 뒤에 정의돼 「초기화 전에 접근」 오류로 종이가 하나도 안 그려졌는데, 불러올 때 도장이 하나도 없는 파일만 열어 보던 검사가 못 잡았다(사용자가 브라우저에 저장해 둔 작업이 이 경우였다)
        src2 = open(D + f, encoding='utf-8').read(); mm = re.search(r'"pages"\s*:\s*\[\s*\{', src2)
        open(D + 'qrload_' + f, 'w', encoding='utf-8').write(src2[:mm.end()] + '"qrs":[{"cell":0,"kind":"url","url":"a.kr"},{"cell":1,"kind":"url","url":"b.kr"},{"cell":5,"kind":"wifi","ssid":"x","pass":"y","enc":"WPA"}],' + src2[mm.end():])
        n_err = len(out['err']); pg.goto(url('qrload_' + f)); pg.wait_for_timeout(600)
        out['loadqr'] = [pg.evaluate("()=>document.querySelectorAll('.sheet').length > 0"), pg.evaluate("()=>document.querySelectorAll('.sheet[data-pi=\"0\"] .qr').length"), pg.evaluate("()=>(P(0).seals||[]).map(x=>x.cell)"), len(out['err']) - n_err]   # 종이가 그려지고 · QR 셋(맨 위 둘 · 바닥 하나) · 겹친 아래 구석 도장은 빠지고 · 오류 0
        out['excl'] = pg.evaluate("()=>{const g={seals:[{cell:0,seal:'word'},{cell:4,seal:'tri'},{cell:5,seal:'word'}],qrs:[{cell:0,kind:'url',url:'a.kr'},{cell:4,kind:'url',url:'a.kr'}]}; normQrs(g); return g.seals.map(x=>x.cell)}")   # 아래 구석은 서로 못 쓴다(QR 을 남긴다) · 위 자리는 도장과 안 겹쳐 그대로
        out['norm'] = pg.evaluate("""()=>{ const g={qrs:[{cell:4,kind:'url',url:'x'.repeat(500),label:'가'.repeat(40)},{cell:4,kind:'wifi'},{cell:9,kind:'url'},{cell:1,kind:'zz'},null,{cell:5,kind:'wifi',ssid:'a',pass:'b',enc:'nopass'}]}; normQrs(g);
          const h={qrs:'망가짐'}; normQrs(h); const k={qrs:[null]}; normQrs(k); return [g.qrs.map(x=>[x.cell,x.kind,(x.url||x.ssid||'').length,(x.label||'').length,x.pass===undefined?'-':x.pass]), 'qrs' in h, 'qrs' in k] }""")
    except Exception as e:
        out['fail'] = str(e).split('\n')[0][:200]
    ctx.close(); return out

# ───────────────────────── 59. 그림 균일(339번)
def t59(b, f):
    """모든 그림을 캔버스로 그려 **아래끝이 같은 선**(488 ~ 500 — 알프스 때 그림은 491 ~ 499)이고 **콘셉트 묶음의 그림은 높이 300 이상**인지.
    329번에 새로 그린 열여섯은 아래끝이 469 ~ 494 로 칸 아래에서 들쭉날쭉했고 꼬치 151 · 김밥 194 · 전 272 로 납작했다(사용자: 균일하게 · 콘셉트에 어울리게 검토)"""
    out = {'err': []}
    c = Ctx(b, f)
    try:
        res = c.js("""async ()=>{ const W=880,H=520, out={}; const keys=Object.keys(ART).filter(k=>k!=='none');
          for(const k of keys){ let svg=ART[k].replace(/var\\(--paper\\)/g,'#ffffff').replace(/currentColor/g,'#000000'); if(!/xmlns=/.test(svg)) svg=svg.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"');
            const img=new Image(); img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(svg); await img.decode().catch(()=>{}); const cv=document.createElement('canvas'); cv.width=W; cv.height=H; const g=cv.getContext('2d'); g.fillStyle='#fff'; g.fillRect(0,0,W,H); g.drawImage(img,0,0,W,H);
            const d=g.getImageData(0,0,W,H).data; let y0=H,y1=-1,x0=W,x1=-1; for(let y=0;y<H;y++)for(let x=0;x<W;x++){ if(d[(y*W+x)*4]<128){ if(y<y0)y0=y; if(y>y1)y1=y; } if(d[(y*W+x)*4]<225){ if(x<x0)x0=x; if(x>x1)x1=x; } }
            out[k]=[y1, y1-y0+1, x1-x0+1, x0, x1]; }   /* 349번. 좌우는 옅은 부분(연한 산 · 흐린 끝)까지 센다(225) — 위아래 규칙은 그대로(128) */
          const groups={}; [...document.querySelectorAll('#f-art optgroup')].forEach(o=>groups[o.label]=[...o.querySelectorAll('option')].map(x=>x.value));
          return {m:out, groups}}""")
        m = res['m']; concept = [k for g, ks in res['groups'].items() if not g.startswith('산 · 동물 · 풍경') for k in ks]
        out['bottom_bad'] = {k: v[0] for k, v in m.items() if k not in ('bridge', 'pasta') and not (488 <= v[0] <= 500)}
        out['flat'] = {k: m[k][1] for k in concept if k in m and m[k][1] < 300}
        out['wide'] = {k: v[2] for k, v in m.items() if v[2] > 880}
        out['side_bad'] = {k: [v[3], 879 - v[4]] for k, v in m.items() if v[3] < 50 or 879 - v[4] < 50 or abs((v[3] + v[4]) / 2 - 440) > 25}   # 349번. 칠해진 부분이 틀 왼쪽 · 오른쪽 끝에서 50 이상 떨어지고 가운데에서 25 넘게 안 벗어난다(산장이 왼쪽으로 쏠려 잘려 보였다)
        out['n'] = [len(m), len(concept)]
    except Exception as e:
        out['fail'] = str(e).split('\n')[0][:200]
    out['err'] += c.errs; c.close(); return out

def t02b(b, f):
    """339번. t02 에서 **그림 · 기타만** — 글꼴 × 도장 121 조합은 그림 · QR 과 상관없어 빼고(세로 8분 · 가로 14분 → 몇 분), 그림을 바꾼 판은 이것만 먼저 돌린다. 제출 직전에는 t02 전체를 한 번"""
    out = {}
    c = Ctx(b, f)
    for o in ('portrait', 'landscape'):
        arts = []
        for a in ['none','horse','zebra','ibex','mountain','fir','cabin','night','bridge','highball','beer','soju','sake','wine','pasta','beerpasta','edelweiss','vine',
                  'ttuk','bapsujeo','bibim','jeon','coffee','croissant','cake','bingsu','teapot','tteok','gimbap','eomuk','ramyeon','chicken','fries','skewer','lantern']:   # 329번. 콘셉트별 그림 16
            c.pg.goto(url(f))
            r = c.js("""([o,a,sel])=>{SETTINGS.orient=o; MENU.sheets.forEach((_,i)=>{ const p=P(i); if (typeof normArts==='function') p.arts = a==='none' ? [] : [0,1,2,3,4,5].map(c=>({cell:c, art:a})); else p.art=a; }); syncControls(); applyLook(); render(); fitNow(); applyScale();
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

# ───────────────────────── 60. AI 초기 세팅 · 와인 읽기 · QR 종이색 · 그림 순서 · 폰 안내 (341번)
READ_WINE = '가게: VINO · 비노\n콘셉트: 와인\n방향: 세로\n단: 1\n글꼴: 명조\n색: 종이 #F5F2EC · 글자 #1A1A1A · 띠 없음 · 포인트 #7a1f2b\n\n[RED 레드] 1 와인\nChâteau Margaux 2015 | 28000 | 168000 | 프랑스 · 보르도 | 까베르네 소비뇽 블렌드 | | 풍부한 검은 과일\nPenfolds Bin 389 2019 | 16000 | 96000 | 호주 · 바로사 밸리 | 쉬라즈 | | 진한 초콜릿 향\nTenuta San Guido Guidalberto | | 88000 | 이탈리아 · 토스카나 | 메를로 | | 부드러운 탄닌\n[WHITE 화이트] 1 와인\nCloudy Bay Sauvignon Blanc 2022 | 14000 | 82000 | 뉴질랜드 · 말보로 | 소비뇽 블랑 | | 상큼한 시트러스\nLouis Latour Chablis 2021 | | 98000 | 프랑스 · 부르고뉴 | 샤르도네 | | 미네랄\n[SPARKLING 스파클링] 1 와인\nMoët & Chandon Impérial | | 160000 | 프랑스 · 샹파뉴 | | | 시트러스와 브리오슈\nMionetto Prosecco | 12000 | 62000 | 이탈리아 · 베네토 | 글레라 | |'
READ_MIX = '가게: 알로라\n콘셉트: 요리주점\n방향: 세로\n단: 2\n글꼴: 고딕\n색: 종이 #FFFFFF · 글자 #1A1A1A · 띠 #1c3145 · 포인트 #a53528\n\n[식사] 1\n크림 파스타 | 14000\n오일 파스타 | 13000 | 추천\n[안주] 2\n생 연어구이 | 10000\n[레드 와인] 2 와인\n하우스 레드 | 9000 | 52000 | 칠레 | 메를로 | | 부드러운 과일\n[화이트 와인] 2 와인\n하우스 화이트 | 9000 | 52000 | 칠레 | 소비뇽 블랑 | | 상큼함'
READ_HANSIK = '가게: 해성 국밥\n콘셉트: 한식\n방향: 세로\n단: 2\n\n[국밥] 1\n돼지국밥 | 9000 | 추천\n순대국밥 | 9500\n[사이드] 2\n수육 | 25000\n공기밥 | 1000'
READ_COLORS_ONLY = "가게: 새 가게\n방향: 세로\n단: 2\n글꼴: 고딕\n색: 종이 #FFFFFF · 글자 #1A1A1A · 띠 없음 · 포인트 #a53528\n\n[식사] 1\n김치찌개 | 9000\n[음료] 2\n콜라 | 2000"
def t60(b, f):
    """사진 읽기 결과(글)를 첫 화면부터 끝까지 따라가 **가게 콘셉트에 맞는 처음 모양**(사진의 글꼴 · 색 + 콘셉트의 모양)과 **와인 장**(원산지 · 품종 · 맛 · 글라스 / 병 가격)이 되는지 · 요청 글에 새 줄이 있는지 ·
    QR 바탕(흰색 · 고른 색 · 바탕 없음 · 대비 안내) · 그림 목록에서 알프스 전용 묶음이 맨 아래인지 · 폰 크기에서 안내가 뜨는지"""
    out = {'err': []}
    src = open(D + f, encoding='utf-8').read(); k = 'const SETTINGS = {\n'
    open(D + 'start_' + f, 'w', encoding='utf-8').write(src.replace(k, k + '  "startScreen": true,\n', 1))   # 341번 — t47 이 만들어 둔 것에 기대지 않는다(안 돌았거나 옛 것이면 옛 코드로 읽는다)
    try: import zxingcpp  # type: ignore
    except Exception: zxingcpp = None
    ctx = b.new_context(viewport={'width': 1400, 'height': 1000}, device_scale_factor=3); pg = ctx.new_page()
    pg.on('pageerror', lambda e: out['err'].append(str(e)))
    def flow(txt):
        pg.goto(url('start_' + f)); pg.wait_for_timeout(500); pg.click('#st-photo'); pg.wait_for_timeout(200)
        pg.evaluate("(t)=>toCheck(t, document.querySelector('#st-appmsg'))", txt); pg.wait_for_timeout(300)
        chk = pg.evaluate("()=>({secs:stParsed.map(s=>[s.name,s.wine||null,s.items.length]), concept:stLook.concept||null, tags:document.querySelectorAll('.st-wtag').length})")
        pg.click('#st-check-go'); pg.wait_for_timeout(300)
        pre = pg.evaluate("()=>({preset:stPreset, name:(PRESETS.photo||{}).name, art:(PRESETS.photo||{}).art, font:(PRESETS.photo||{}).font, theme:(PRESETS.photo||{}).theme, paper:(PRESETS.photo||{}).paper, noren:(PRESETS.photo||{}).noren})")
        pg.click('#st-go'); pg.wait_for_timeout(800)
        res = pg.evaluate("""()=>({kinds:MENU.sheets.map((_,i)=>sheetKind(i)), item:(()=>{const w=[].concat(...[].concat(...MENU.sheets)).find(x=>x.wine); return w?w.items:null})(), feet:MENU.feet.map(f=>f.notes), pages:SETTINGS.pages.slice(0,MENU.sheets.length).map(p=>({art:(p.arts||[]).map(a=>a.art), seal:(p.seals||[]).map(a=>a.seal), autofit:p.autofit===true})), font:SETTINGS.font, theme:SETTINGS.theme, over:MENU.sheets.map((_,i)=>overA4(i))})""")
        return chk, pre, res
    try:
        pg.goto(url(f)); pg.wait_for_timeout(300)
        out['prompt'] = pg.evaluate("()=>[READ_PROMPT.includes('콘셉트: 한식'), READ_PROMPT.includes('와인 목록이면'), READ_PROMPT.includes('와인이 아닌 메뉴의 설명')]")
        out['wine'] = flow(READ_WINE); out['mix'] = flow(READ_MIX); out['hansik'] = flow(READ_HANSIK); out['colors'] = flow(READ_COLORS_ONLY)
        # 그림 목록 순서
        pg.goto(url(f)); pg.wait_for_timeout(300)
        out['groups'] = pg.evaluate("()=>[...document.querySelectorAll('#f-art optgroup')].map(o=>o.label)")
        # QR 바탕(348번) — 흰색(기본) · 고른 색 · 바탕 없음 · 대비가 낮으면 안내만(막지 않는다) · 설정 창의 색 상자 · 바탕 없음 단추
        out['qrbg'] = None
        if zxingcpp:
            def read(sel):
                png = pg.query_selector(sel).screenshot(); return [x.text for x in zxingcpp.read_barcodes(Image.open(io.BytesIO(png)).convert('RGB'))]
            def put(cell, bg):
                return pg.evaluate("([c,b])=>{const q={cell:c,kind:'url',url:'naver.me/abcd'}; if(b) q.bg=b; P(0).qrs=[q]; render(); topBands(); const r=document.querySelector('.sheet[data-pi=\"0\"] .qr svg rect'); return [r?r.getAttribute('fill'):null, qrContrast(q)]}", [cell, bg])
            st = []
            for bgv in (None, '#e8dcc2', 'none'):   # b 는 브라우저라 덮어쓰면 안 된다
                v = put(5, bgv); st.append([v[0], round(v[1], 1), read('.sheet[data-pi="0"] .qr svg')])   # 변수 f 는 파일 이름이라 덮어쓰면 안 된다
            def note(cell, bg):
                put(cell, bg); return pg.evaluate("([c])=>{panelPage=0; qrSlot=c; syncQrNote(); return $('#qr-note').textContent}", [cell])
            n_dark_none_top = note(0, 'none'); n_dark_pick = note(5, '#303030'); n_white = note(5, None); n_none_paper = note(5, 'none')
            ui = pg.evaluate("""()=>{ P(0).qrs=[{cell:5,kind:'url',url:'naver.me/abcd'}]; panelPage=0; qrSlot=5; syncQr(P(0)); const o={};
              o.shown = !$('#qr-bgrow').hidden; o.val = $('#c-qrbg').value;
              const cp=$('#c-qrbg'); cp.value='#112233'; cp.dispatchEvent(new Event('input',{bubbles:true})); o.pick = P(0).qrs[0].bg;
              cp.value='#ffffff'; cp.dispatchEvent(new Event('input',{bubbles:true})); o.white = P(0).qrs[0].bg === undefined;
              const nb=$('#f-qrnone button'); nb.click(); o.none = P(0).qrs[0].bg; o.on = nb.classList.contains('on'); o.dim = $('#c-qrbg').parentNode.classList.contains('off');
              nb.click(); o.back = P(0).qrs[0].bg === undefined; o.off = !$('#f-qrnone button').classList.contains('on'); return o }""")
            out['qrbg'] = [st, n_dark_none_top, n_dark_pick, n_white, n_none_paper, ui]
        out['norm'] = pg.evaluate("()=>{const g={qrs:[{cell:0,kind:'url',url:'a.kr',bg:'paper'},{cell:1,kind:'url',url:'b.kr',bg:'x'},{cell:4,kind:'url',url:'c.kr',bg:'#E8DCC2'},{cell:5,kind:'url',url:'d.kr',bg:'none'}]}; normQrs(g); const h={qrs:[{cell:5,kind:'url',url:'e.kr',bg:'#FFFFFF'}]}; normQrs(h); return g.qrs.map(x=>x.bg||null).concat(h.qrs.map(x=>x.bg||null))}")   # 348번. 옛 paper · 이상한 값은 흰색(없음) · 대문자 색은 소문자로 · #fff 는 기본으로
        # 맨 위 크기 하한 30%(342번) — 막대 범위 · 줄여도 위 여백선 밑으로는 안 내려감 · 45% 밑 안내
        pg.goto(url(f)); pg.wait_for_timeout(300)
        out['nscale'] = pg.evaluate("""()=>{ const hh=ns=>{ P(0).norenScale=ns; render(); return Math.round(document.querySelector('.sheet[data-pi="0"] .noren').getBoundingClientRect().height); };
          const a=hh(.6), b=hh(.3); panelPage=0; setNScale(.1); const clamp=P(0).norenScale; P(0).showTitle=true; nszNote(); const n1=!document.querySelector('#nsz-note').hidden; P(0).showTitle=false; P(0).showSub=false; nszNote(); const n2=document.querySelector('#nsz-note').hidden;
          return [document.querySelector('#nsz-range').min, a, b, clamp, n1, n2] }""")
        # 폰 크기 안내
        m = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True); mp = m.new_page(); mp.goto(url('start_' + f)); mp.wait_for_timeout(600)
        out['narrow'] = mp.evaluate("()=>[narrowView(), !document.querySelector('#st-narrow').hidden]")
        out['narrow_box'] = mp.evaluate("()=>{const h=document.querySelector('#st-choose h3').getBoundingClientRect(), n=document.querySelector('#st-narrow').getBoundingClientRect(); return [h.width > 200, h.height < 100, n.top >= h.bottom - 1]}")   # 342번 — 제목이 한 글자씩 눌리거나 안내가 제목 위에 겹치면 안 된다(341번에 안내를 제목 줄 안에 넣어 눌렸다 — 보이는지만 보던 검사가 못 잡았다)
        m.close()
        pg.goto(url('start_' + f)); pg.wait_for_timeout(300); out['wide'] = pg.evaluate("()=>[narrowView(), !document.querySelector('#st-narrow').hidden]")
    except Exception as e:
        out['fail'] = str(e).split('\n')[0][:200]
    ctx.close(); return out

def judge(t, r):
    """(통과?, 한 줄 요약). None 이면 사람이 볼 것"""
    try:
        if t == 't02b': ok = not any(r[k] for k in r if k.startswith(('art_', 'misc_')) and not k.endswith(('_n_portrait', '_n_landscape', 'checked_portrait', 'checked_landscape'))) and not r['err']; return ok, f"넘침·가림 {'0' if ok else '있음'} (그림 {r['art_checked_portrait']}+{r['art_checked_landscape']}칸 · 기타 {r['misc_n_portrait']}×2)"
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
                    if not (near(pg[0], m[o][0], 0.4) and near(pg[1], m[o][1], 0.4)): bad.append((o, pg))   # 좌우는 글자 상자
                for ib in r[o].get('inkBottom', []):   # 296번. 아래는 잉크 — 여백선(11mm) 밖으로 나가지 않을 것
                    if ib < 10.9: bad.append((o, '아래 잉크', ib))
                if not r[o]['multicol']: bad.append((o, '다단 아님'))
                if max(r[o]['edit_px_diff'] or [0]) > 100: bad.append((o, '편집 중 인쇄 화소', r[o]['edit_px_diff']))
            for L, v in r['long'].items():
                if not (v['priceIn'] and v['prevIn'] and all(x <= v['colRightMm'] + 0.5 for x in v['pdfPriceXmm'])): bad.append(('긴 이름', L))
            return not bad, f"여백 세로 {r['portrait']['margins'][0]} · 가로 {r['landscape']['margins'][0]} · 아래 잉크 {r['portrait'].get('inkBottom')}/{r['landscape'].get('inkBottom')} mm · 편집 중 인쇄 {r['portrait']['edit_px_diff']}/{r['landscape']['edit_px_diff']} {bad or ''}"
        if t == 't08':
            od = r.get('order310') or {}; obad = [k for k, v in od.items() if v is not True]   # 310번
            bad = [(k, n) for k, v in r.items() if k not in ('_sec', 'order310') for n, x in v['r'].items() if x.get('notOpen') or not (x['foot'] and x['hit'] and x['over'] == 0 and x['shadeOk'] and x['detVis'] in (None, True) and (x['h3'] or n.endswith('-open')))] + [(k, 'err') for k, v in r.items() if k not in ('_sec', 'order310') and v['err']]
            return not bad and bool(od) and not obad, f"창 14구성 문제 {len(bad)} {bad[:4]} · 310번 채운 단추가 오른쪽 끝 아님 {obad or '없음'} {od}"
        if t == 't10':
            tl, wd = r['tall'], r['wide']; ok = ('tall' in tl['why'] and '잘립니다' in tl['warn'][2] and 'wide' in wd['why'] and '잘립니다' not in wd['warn'][2] and '[＋ 장 추가]' not in tl['toast'] + tl['warn'][3])
            fake = [x for x in ('[＋ 장 추가]', '[+ 장 추가]') if x in tl.get('tab', '') + wd.get('tab', '')]; ok = ok and not fake   # 297번
            return ok, f"세로: {tl['warn'][1]} / 가로: {wd['warn'][1]} · 탭 줄 없는 단추 이름 {fake or 0}"
        if t == 't11': return all(x[1] for x in r['steps']), str(r['steps'])
        if t == 't14': ok = r['roundtrip_same'] and r['roundtrip_pos'] and not r['legacy_saved_oldkeys'] and not r['legacy_saved_toplevel_pagekeys'] and not (r['rt_err'] or r['legacy_err']) and r['legacy_open']['ns'] == 0.9 and r.get('legacy_art') == '[{"cell":5,"art":"horse"}]' and not r.get('legacy_saved_pagekeys'); return ok, f"왕복 {r['roundtrip_same']} · 옛 저장본 상단 {r['legacy_open']['ns']}(낮게 → 0.9) · 옛 키 {r['legacy_saved_oldkeys']} · 옛 그림 → {r.get('legacy_art')} · 저장본 장별 옛 그림 키 {r.get('legacy_saved_pagekeys')}"
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
        if t == 't39': p = r['pages']; ok = not r['err'] and r['S'] == {'font': 'gungseo', 'theme': 'night', 'mark': '★', 'pageno': 'of', 'sec': 'left', 'wine': 'left'} and all(x[3] == 1 and x[4] == 0.8 for x in p) and r['ui']['font'] == 'gungseo' and all(a is None or a == '[{"cell":2,"art":"horse"}]|[{"cell":2,"seal":"star"}]' for a in r.get('arts', [])) and not any(r.get('align', [True])); return ok, f"복구 {r['S']} · 장 {p} · 그림 칸 · 도장 자리 {r.get('arts')} · 309번 분류 줄 키 남음 {r.get('align')}"
        if t == 't40': return r['allSame'] and r.get('posOk'), f"도장 9가지 동작 고정 {r['allSame']} · 도장(여럿) · 그림이 상단 아래 고른 칸에 섬 {r.get('posOk')} {[x for x in r.get('pos', []) if not x[1] == x[2] == x[3]][:4]} · 302번 sealPos → {r.get('sealPosMove')}"
        if t == 't41':
            al = r.get('align309') or []
            # 309번 — 켬: 줄마다 제목 위끝 차이 0.5px 이하 · 분류 틈 한 값 · 넘침 없음 / 끔: 어긋나 있음(시험이 뜻이 있는지) / 맞춤 켠 구성은 켬이 끔보다 크지 않음
            aok = bool(al) and all(x[2][0] <= 0.5 and x[2][1] <= 1 and x[2][2] is None and x[1][0] > 0.5 for x in al) and all(x[2][3] <= x[1][3] for x in al)
            ok = all(len(x['secGaps']) <= 1 for x in r['sheets']) and aok and not r['err']
            return ok, f"칸 아래 구멍 {[x['holes'] for x in r['sheets']]} · 분류 틈 {[x['secGaps'] for x in r['sheets']]} · 309번 분류 줄 맞추기 [구성, 끔(줄 차 · 틈 수 · 넘침 · 배율), 켬] {al}"
        if t == 't42': ok = all(v['edit'] == 0 and v['prev'] == 0 for k, v in r.items() if k != '_sec') and all(x == 0 for x in r['center']['centerMarginDiff']); return ok, '정렬 셋 · 세 모드 0.0px'
        if t == 't43': ok = all(r[k]['newlines'] == 4 for k in ('sec', 'wine', 'label')) and all(x.count('\n') == 4 for x in r['saved']); return ok, '두 줄 쓰기 · 제한 없음 · 저장 보존'
        if t == 't44':
            dark = lambda h: sum(int(h[i:i+2], 16) for i in (1, 3, 5)) < 60
            sw = r['swatch']; ok = (r['copy'] and r.get('artsame') == '[["#aa0000","strong"],["#aa0000","strong"],["#aa0000","strong"]]' and all(v[0] == v[1] and not dark(v[0]) for v in sw.values()) and r['drag'][0] and r['drag'][1] == 0
                  and r['drag'][2] == '#203079' and r['drag'][3] == 0 and r['live'] == [0, 4, True, False] and r['wineprice'] == '' and r.get('winearts311') == '[{"cell":5,"art":"vine"}]|false' and r['nstep'] == 0.84 and r['saveadd'] == [1, True] and r.get('align309') == [True] * 7 and not r['err'])
            return ok, f"복사 {r['copy']} · 모든 그림에 같게 {r.get('artsame')} · 병 색 상자 {sw} · 끄는 중 {r['drag']} · 끄는 중 다시 그리기 · 레드 병 카드 · 바뀜 · 다른 병도 바뀜 {r['live']} · 빈 와인 카드 가격 '{r['wineprice']}' · 상단 걸음 {r['nstep']} · 저장 뒤 병 추가 {r['saveadd']} · 309번 분류 줄 스위치 [켬 · 다른 장 그대로 · 여백, 끔 · 여백 없음, 한 단 흐림 · 모양] {r.get('align309')}"
        if t == 't45':
            w = r['worst']; bad = {k: v for k, v in w.items() if v[0] < 5.0}
            sh = r['show']; T = 'rgba(0, 0, 0, 0)'   # 401번. 흰색(243번까지)이 아니라 투명 — 테두리 폭만 남는다. 편집 화면에만 빗금 + clip-path
            okv = all(all(x[0] == 'block' and near(x[1], 4.0, 0.3) and x[2] == T for x in m) for o in sh.values() for m in o.values()) \
                and all(all(x[4] and x[5] for x in o['edit']) and all(not x[4] and not x[5] for x in o['idle'] + o['preview'] + o['editPrint']) for o in sh.values())
            mins = {k: v[0] for k, v in w.items()}
            return not bad and okv and not (r['err_portrait'] or r['err_landscape']), f"가장자리 최소 {mins} {bad or ''} · 가장자리 띠 4mm · 투명 · 편집만 빗금 {okv}"
        if t == 't57':
            sv = r.get('server') or {}
            ok = (not r.get('fail') and r['start'] == ['', True] and r['zh'] == ['zh', False, False, True, True] and r['sent'][0] == 1 and r['sent'][2]
                  and r['filled'] == [0, 0, True] and r['en_same'] and r['ask_full'] == [True, True, True] and r['keep'] == [1, ['사람이 고침', True]] and r['undo'] and r['all'] == [True, True, True] and r['all_undo']
                  and r['final_lines'] == [0, True] and r['reopen'] == ['zh', 'zh', True, True] and r['legacy'] == ['en', 'en', True] and not r['err']
                  and r.get('busy310') == [False, '1', True, True] and str(r.get('ja310') or '').lstrip('"\'').startswith('Shippori')
                  and sv == {'ok': 200, 'origin': 403, 'lang': 400, 'many': 400, 'long': 400, 'count': 422, 'clip': 60, 'off': 503})
            return ok, (f"실패: {r['fail']}" if r.get('fail') else f"고르기 {r['zh']} · 보냄 {r['sent']} · 빈 칸 [남음, 와인 카드, 설명] {r['filled']} · 영문 그대로 {r['en_same']} · 다 차면 묻기 [열림, 빈 칸만 흐림, 안 부름] {r['ask_full']} · 빈 칸만 — 고친 칸 그대로 {r['keep']} · 되돌리기 {r['undo']} · 전부 다시 {r['all']} → 되돌리기 {r['all_undo']} · 완성본 빈 줄 없음 {r['final_lines']} · 저장 왕복 {r['reopen']} · 옛 영문 병기 {r['legacy']}") + f" · 서버 {sv}"
        if t == 't56':
            ok = r['top_px_landscape'] == r['top_px_portrait'] and all(r[k] <= 0.5 for k in r if k.startswith('pill_')) and r['tools_out_4col'] == 0 and r['empty_hours_border'] and r['hours_parse'] == [{'label': '점심', 'time': '11:00 - 15:00'}, {'label': '저녁', 'time': '17:00 - 23:00'}] and not r['err']
            return ok, f"맨 위 글자 세로 · 가로 {r['top_px_portrait']} · {r['top_px_landscape']}px · 알약이 여백선 밖 {[r[k] for k in r if k.startswith('pill_')]}px · 가로 4단 분류 도구 칸 밖 {r['tools_out_4col']}px · 빈 영업시간 선 없음 {r['empty_hours_border']} · 영업 줄 읽기 {bool(r['hours_parse'])}"
        if t == 't55':
            ok = all(r['first']) and all(r['saved']) and all(r['reopen']) and all(r['file_clean']) and r['import'][:1] == [2] and all(r['import'][1:]) and all(r['file']) and not r['err']
            return ok, f"웹 처음 [첫 화면, 저장본 없음] {r['first']} · 고친 뒤 [상태, 저장본, 불 꺼짐] {r['saved']} · 다시 열기 [첫 화면 없음, 이어짐, 알림] {r['reopen']} · 받은 파일에 [웹 표시 없음, 상태 글자 없음] {r['file_clean']} · 불러오기 [장, 첫 화면 없음, 알림, 되돌리기] {r['import']} · 컴퓨터 파일 [자동 저장 안 됨, 저장본 안 씀, 불] {r['file']} · 오류 {r['err'][:2]}"
        if t == 't54':
            want = [[['식사', ['단호박 크림 파스타=14000', '고사리 들깨 크림 파스타=14000', '오징어 페코리노 파스타=14000']]], [['안주', ['生 연어구이=10000', '국물바지락=11000', '피망=시가']], ['음료', ['콜라 · 사이다=3000']]]]
            ok = r.get('p352') == [True] * 10 and not r.get('err352') and r.get('p329') == [True] * 3 and r.get('p327') == [True] * 6 and r.get('p326') == [True] * 3 and r.get('p325') == [True] * 4 and r.get('p323') == [True] * 7 and r.get('p322') == [True] * 2 and r.get('p320') == [True] * 3 and r.get('p319') == [True, True] and r.get('seg319') is True and isinstance(r.get('rule318'), dict) and len(r['rule318']) == 6 and not any(r['rule318'].values()) and r.get('p317') == [True] * 4 and r.get('busy316') == [True, True] and r.get('p315') == [True] * 3 and r.get('orient315') == [True] * 5 and r.get('p314') == [True] * 7 and r.get('form314') == [True, True] and r.get('p313') == [True] * 7 and r.get('form313') == [True] * 5 and r.get('p312') == [True] * 15 and isinstance(r.get('fit312'), list) and r['fit312'][0] and r['fit312'][1] >= 0.5 and r['fit312'][2] == 76 and r['check'] == [True, 17, 2] and r['menu'] == want and all(r['gem']) and r['no_key_box'] and r['limit_msg'] and all(r.get('off', [False])) and r.get('prompt_same') is not False and r.get('other') == [True, True] and not r['err']
            return ok, f"352번 [읽은 것 줄 · 종류별 요약(중복 · 가격) · 어디서 보는지 안내 · 시가는 통과 · 4건 · 이름 그대로] {r.get('p352')} · 329번 [그림 묶음 여섯, 목록 = 정의, 새 그림 그려짐] {r.get('p329')} · 327번 [비우면 상호명, 적은 글자, 기호 도장 글자 없음, 정리, 영문 가로, 알프스 박힘 없음] {r.get('p327')} · 326번 [두 묶음 제목, 도장이 밑 · 구분선, 손잡이가 제 묶음 안] {r.get('p326')} · 325번 [← 같은 자리, 제목 같은 자리, 주 단추 같은 자리, 숨긴 파일 칸 안 보임] {r.get('p325')} · 323번 [두 칸 다른 모양, 격자에 보임, 종이에 그 칸만, 색 그 칸만, 없음이면 그 칸만 · 색 흐림, 칸 바꿔도 길이 같음, 칸 이름] {r.get('p323')} · 322번 [그림 칸 바꿔도 길이 같음, 그림 손잡이 흐림] {r.get('p322')} · 320번 [맞춤 스위치, 격자 하나, 다른 장에 격자 밑] {r.get('p320')} · 319번 [격자 빈 칸 ＋, 흐린 까닭] {r.get('p319')} · 고르기 폭 {r.get('seg319')} · 318번 단추 규칙 어긋남(사진 · 확인 · 정하기 · 꾸미기 창) {r.get('rule318')} · 317번 [아이콘 한 쌍, 사진 폭 안, 사진 가운데, 확인 화면 같은 높이] {r.get('p317')} · 316번 진행 막 [방향 → 돌렸습니다 → 읽는 중, 끝나면 사라짐] {r.get('busy316')} · 315번 [돌리기 · 사진 바꾸기 한 열, 직접 돌리면 안 물음, 글자 \\n 나눔] {r.get('p315')} · 방향 묻기 [한 번, 작은 사진, 돌린 사진으로 읽기, 확인 화면 사진, 알림] {r.get('orient315')} · 314번 [돌려도 단추 제자리, 돌리기 사진 옆, 글자 · 그림 기호 없음, 그린 그림, 가운데 ? 뗌, ※ * 뗌 · 노랑, 바닥 ? ] {r.get('p314')} · [사진 폭 같음, 4단 좁은 가격] {r.get('form314')} · 313번 [돌리기 창 안 염, 돌린 크기, 경고 줄, 진한 노랑, 빈 분류 알림 머묾, 알림 글, 정하기 경고] {r.get('p313')} · 방향 · 단 손잡이 [세로, 창 스크롤 없음, 표시, 1단, 칸 그대로] {r.get('form313')} · 312번 [이름 칸 안내, 영업 칸 4, 노란 2, 빈 분류 노랑, ★, 분류 안내, 바닥 글, 사진처럼 표시, 못 찾음 안내, 미리보기 종이색, 영업 고친 값, 추천, 안내, 바닥, 궁서] {r.get('p312')} · 스크롤 없음 [들어감, 배율, 칸] {r.get('fit312')} · 다른 앱 길 [처음엔 숨김, 실패 뒤 보임] {r.get('other')} · 붙여 넣기 → 확인 화면 [보임, 칸, 노란 칸] {r['check']} · 시작 뒤 메뉴 맞음 {r['menu'] == want} · 서버 함수 [주소, 사진, 사진만 보냄, 키 머리글 없음, 확인 화면, 가게 이름] {r['gem']} · 키 칸 없음 {r['no_key_box']} · 한도 안내 {r['limit_msg']} · 두 요청 글 같음 {r.get('prompt_same')} · 꺼 두면 [흐림, 읽기 흐림, 다른 앱으로, 안내] {r.get('off')} · 오류 {r['err'][:2]}"
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
                  and st[1]['tools'] and st[2]['tools'] and r['done'] == [True, 0] and r['again'] and r['esc'] == 0 and r.get('x310') == [True, True, True, [0, True]] and not r['err'])
            return ok, f"그냥 열면 {r['plain_open']} · 단계 {[ (x or {}).get('h','없음')[:6] for x in st]} · 짚은 칸 {[ (x or {}).get('hole') for x in st]} · 말풍선이 가림 {[ (x or {}).get('cover') for x in st]} · 도구 보임 2/3단계 {st[1].get('tools') if len(st)>1 and st[1] else None}/{st[2].get('tools') if len(st)>2 and st[2] else None} · 끝 {r['done']} · 다시 {r['again']} · Esc {r['esc']} · 310번 [✕ · 같은 점 · 건너뛰기 없음, 닫힘] {r.get('x310')} · 오류 {r['err'][:2]}"
        if t == 't48':
            d = {k: v for k, v in r['idle']}; e = {k: v for k, v in r['edit']}; z = {k: v for k, v in r['back']}
            bad = {k: (d[k], e.get(k)) for k in d if k and k in e and d[k] and e[k] and abs(d[k] - e[k]) > 0.5}   # 폭 0 = 그 모드에서 숨은 단추(편집 도구 막대) — 뺀다
            hb, hw = r.get('heights', [[], []]); hok = bool(hb) and min(hb) > 80 and bool(hw) and max(hw) < 0   # 병은 병 모양이 보이는 높이 · ▲▼는 그 줄보다 작게(268번). 335번에 24px 로 박힌 숫자가 새 크기를 막아 30 으로 고쳤다가, 336번에 숫자를 걷고 줄 높이와 견준다(음수 = 줄보다 작다)
            rg = r.get('range308') or [0] * 6; rok = rg[0] == rg[2] and rg[1] == rg[3] and rg[4] == rg[5] == rg[3]   # 308번 — 막대 끝 = 상한 상수 · 140% 에서 막대도 140
            def onoff(L):   # 켜진 단추와 꺼진 단추의 모양이 다른가 — 둘 다 있어야 잴 수 있다
                on = {x[2] for x in L if x[1]}; off = {x[2] for x in L if not x[1]}
                return bool(on) and bool(off) and not (on & off)
            mw, ww = r.get('menu308') or [], r.get('wine308') or []
            one = bool(ww) and all(x[3] == 1 for x in ww)   # 와인 줄 도구 — 단추마다 글자가 한 줄(「추/천」 두 줄이면 2)
            ok308 = rok and onoff(mw) and onoff(ww) and one
            return not bad and d == z and hok and ok308 and not r['err'], f"편집 켜고 끌 때 폭이 바뀐 막대 단추 {bad or '없음'} · 편집 단추 {d.get('b-edit')}/{e.get('b-edit')} · 병 단추 높이 {sorted(set(hb))} · ▲▼ {sorted(set(hw))} · 308번 [막대 끝 = 상한, 켜짐 구별 메뉴 · 와인, 와인 도구 한 줄] [{rok}, {onoff(mw)}, {onoff(ww)}, {one}] 막대 {rg} 와인 단추 글자 줄 수 {sorted({x[3] for x in ww})}"
        if t == 't46':
            g = r['244_foot_fixed']; top = r['256_logo_top_mm']
            ok = (near(g[0], g[1], 1) and g[2] == 'tall' and r['245_invisible'] is None and all(r[f'sec_pad_{n}'] is None for n in (10, 30, 45, 60))
                  and r['254_line_on'][0] is None and r['254_line_off'][0] is None and all(near(v, 11, 0.4) for v in top.values()) and r['246_loadingdone'] >= 1 and not r['err'])
            return ok, f"바닥 고정 {g} · 안 보이는 3px {r['245_invisible']} · 빈 자리 10·30·45·60px {[r[f'sec_pad_{n}'] for n in (10, 30, 45, 60)]} · 밑줄이 도장 +20px 켬/끔(296번 — 도장은 판정에서 빠졌다: 둘 다 None) {r['254_line_on'][0]}/{r['254_line_off'][0]} · 로고 윗변 mm {top} · 글꼴 도착 뒤 다시 재기 {r['246_loadingdone']}회"
        if t == 't47':
            s = r['started']; import re as _re
            ok = (r['open_first'] == [True, 'none', False] and   # 275번 — 사진으로 시작이 준비 중(흐림)에서 눌림으로
                  r['esc_stays'] and r.get('backdrop_stays') and r.get('setup_backdrop_stays') and r['top_follows'] == ['', '가게 이름', True] and all(r['logo_mask_invert'])
                  and not s['open'] and s['editing'] and s['sheets'] == 1 and s['title'] == '시험 가게 — 메뉴' and s['flag'] and s['undo'] == 0 and s['font'] == 'gothic'
                  and s['seal'] == 'none' and s['art'] == 'none' and s['logo'] and s['focus'] == 'sheets.0.0.0.name'
                  and _re.match(r'시험 가게-메뉴-\d{4}-\d\d-\d\d\.html$', r['save_name']) and r['saved_opens_direct'] and r['reopen_close']
                  and r['alps'] == [2, '알프스', True] and r.get('guide_up') and r.get('alps_no_guide') and r['undo_back'] == ['시험 가게', 1] and r['noname'][0] == '메뉴판' and r['noname'][1].startswith('메뉴판-') and not r['err'])
            m330 = r.get('mobile330') or {}   # 330번 — 폰에서 창이 보이는 화면 안에
            ok330 = bool(m330) and all(v['wide'] and v['start'] is True and v['start_wide'] is True and v['print_scrolled'] is True and v['closed_clean'] and not v['err'] for v in m330.values())
            w331 = r.get('wine331') or {}   # 331번 — 와인 분류가 없으면 와인 기능이 안 보인다
            ok331 = bool(w331) and w331['blank'] == [0, True] and w331['wine_added'][0] > 0 and w331['wine_added'][1] is False and w331['saved_no_hidden'] and w331.get('menu_page_hides') is True and w331['undone'] == [0, True, 1, True] and not w331['err']
            t332 = r.get('tabs332') or {}   # 332번 — 하려는 일로 나눈 탭
            T5 = ['look','top','menu','foot','deco']   # 333번 — 한 줄 다섯, 와인 장을 넣어도 탭은 그대로
            G = lambda x, ids: x and x['ids'] == ids and x['oneLine'] and x['rows'] == 1 and x['titles']
            ok332 = bool(t332) and G(t332['blank'], T5) and G(t332['wine'], T5) and t332['home'] == [] \
                    and t332.get('sticky') == [True, True, True] and t332.get('parts335') == [True, True, True, True, True, True] and t332['vis']['look'] == [False, False, 0] and all(v[0] and v[1] and v[2] >= 1 for k, v in t332['vis'].items() if k != 'look') and not t332['err']
            ok = ok and ok330 and ok331 and ok332
            return ok, f"333번 탭 [빈 메뉴판, 와인 장, 제 탭이 아닌 손잡이, 탭마다 고칠 장 · 모든 장에 같게 · 이 장만] {[t332.get('blank'), t332.get('wine'), t332.get('home'), t332.get('vis')]} · 331번 와인 기능 [빈 메뉴판, 와인 장 넣음, 저장본, 되돌림] {[w331.get('blank'), w331.get('wine_added'), w331.get('saved_no_hidden'), w331.get('undone')]} · 330번 폰 창 [첫 화면, 넓은 틀, 밀어 둔 뒤 인쇄 안내, 닫으면 걷힘] {[[v['start'], v['start_wide'], v['print_scrolled'], v['closed_clean']] for v in m330.values()]} · 첫 화면 {r['open_first']} · Esc {r['esc_stays']} · 바깥 누르기 처음/정하기 {r.get('backdrop_stays')}/{r.get('setup_backdrop_stays')} · 맨 위 글자는 상호명을 안 따라감(267번) {r['top_follows']} · 로고 · 뒤집기 {r['logo_mask_invert']} · 시작 {s} · 저장 이름 {r['save_name']} · 저장본 바로 {r['saved_opens_direct']} · 다시 열기 닫기 {r['reopen_close']} · 알프스 {r['alps']} · 되돌리기 {r['undo_back']} · 상호명 없음 {r['noname']} · 오류 {r['err'][:2]}"
        if t == 't59':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            ok = not r['bottom_bad'] and not r['flat'] and not r['wide'] and not r['side_bad'] and r['n'][0] >= 33 and not r['err']
            return ok, f"그림 {r['n'][0]}개(콘셉트 묶음 {r['n'][1]}) · 아래끝이 488 ~ 500 밖 {r['bottom_bad'] or '없음'} · 높이 300 밑 {r['flat'] or '없음'} · 폭 880 넘음 {r['wide'] or '없음'} · 좌우 여백 50 밑 · 가운데서 25 넘게 벗어남 {r['side_bad'] or '없음'}"
        if t == 't70':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            cd = r.get('cards', [[], ''])
            ok = (r.get('parts') == ['「가츠동」 → 「가쓰동」 · 「돈가츠」 → 「돈가스」', '「타코야끼」 → 「타코야키」', '「김치 우동」 → 「김치우동」'] and r['title'] == [None, True, '#8f8a2e']
                  and r.get('ck395') == [False, False, False, 2, False] and r['box'][0] == 'visible' and r['box'][1] <= 1 and r['btbg'] == 'rgb(255, 253, 246)'
                  and r.get('far') == ['케익', '함박스텍', '육계장'] and r.get('fill396') == [True, True, True]
                  and cd[0] == [['가츠동', '가쓰동', '위치', '가츠동|네기가츠동|김치가츠동', '가츠동,가츠동,가츠동'], ['타코야끼', '타코야키', '위치', '타코야끼', '타코야끼']] and cd[1] == '2건'
                  and r.get('frto', [''])[0] == 'line-through' and r['frto'][1] == '700' and r.get('allbtn') == '모두 적용 (3곳)' and r.get('flash') == 3
                  and r['aidone'] == [1, ['가쓰동', '네기가쓰동', '김치가쓰동'], '위치'] and r.get('notag') == ['오코노미야끼', '가츠동 (돈가츠 덮밥)', '김치우동'] and r['aiundo'] == [0, ['가츠동', '네기가츠동', '김치가츠동']] and r.get('aiign') == [3, '1건']
                  and r['toAI'] == {'panel': False, 'ai': True, 'bs': False, 'ba': True, 'ed': False} and r['onbg'] == ['rgb(239, 227, 201)', 'rgba(0, 0, 0, 0)'] and r.get('clean') == [['가츠동', '가쓰동', ''], ['돈가츠', '돈가스', ''], ['두마리', '두 마리', '띄어쓰기'], ['김치찌게', '김치찌개', ''], ['타코야끼', '타코야키', '외래어 표기'], ['여섯개', '여섯 개', '띄어쓰기']] and r.get('aikind') == ['돈까스', '돈가스', '외래어 표기']
                  and [x[0] for x in r.get('aist', [])] == ['ok', 'ok', 'idle'] and len(r['aist']) == 3
                  and r['toStyle'] == {'panel': True, 'ai': False, 'bs': True, 'ba': False, 'ed': True} and r.get('bar392', [None])[:3] == [True, False, 0] and r['bar392'][3] == r.get('pw392') and r['fromView'] == {'panel': True, 'ai': False, 'bs': True, 'ba': False, 'ed': True} and r.get('qrph') == ['예: 네이버 지도', '예: 와이파이'] and not r['err'])
            return ok, f"390번 제목 색 [회색 버림, 까닭, 올리브 받음] {r['title']} · 395번 확인 화면 [맞춤법 줄 · 목록 · 단추 · 줄 수 · 글] {r.get('ck395')} · 박스 스크롤 {r['box']} · 단추 바탕 {r['btbg']} · 다른 말 거름(남은 것) {r.get('far')} · 396번 [넘침 없음, 키움, 띠 안 단추] {r.get('fill396')} · 칠한 칸 {r.get('flash')} · AI 카드 {cd} · 고치기 전/후 {r.get('frto')} · {r.get('allbtn')} · 적용/되돌림/무시 {r['aidone']}/{r['aiundo']}/{r.get('aiign')} · AI 탭 {r['toAI']} · 켜짐 바탕 {r['onbg']} · 꾸미기 탭 {r['toStyle']} · 편집 꺼진 채 {r['fromView']}"
        if t == 't69':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            Z = r['hours_geo']
            ok = (r['bd_first'] == r['bd_again'] and r['bd_first'] != 'rgba(0, 0, 0, 0)' and r['origin_label'] == '원산지'
                  and r['hours_on']['n'] == 1 and r['hours_on']['rows'] == 1 and r['hours_on']['focus'] and r['hours_on']['show'] is not False
                  and abs(Z['zoneTop'] - Z['hoursTop']) <= 1 and abs(Z['zoneH'] - Z['hoursH']) <= 1 and r['hours_keep'] == 1
                  and r['typ0'][1][0] is False and r['typ1'][1][0] is True and '넘침' in r['typ1'][1][1] and r['typ1'][1][2] and r['typ_focus'] and r['typ2'][1][0] is False and not r['err'])
            return ok, f"384번 뒷배경 {r['bd_first']}/{r['bd_again']} · 원산지 이름 {r['origin_label']} · 영업시간 켬 {r['hours_on']} · 틀 {Z} · 켠 채 두 번 눌러도 줄 {r['hours_keep']} · 와인 장 치기 전 {r['typ0'][1]} · 친 뒤 {r['typ1'][1]} · 커서 {r['typ_focus']} · 줄인 뒤 {r['typ2'][1]}"
        if t == 't68':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            w, n = r['with'], r['none']
            ok = (w['notes'] is False and w['show'] is True and w['origin'] is not None and w['last'] is not None and w['last'] <= w['origin'] - 2
                  and n['notes'] is False and n['show'] is not True and n['origin'] is None and n['scale'] >= w['scale'] and not r['err'])
            return ok, f"383번 원산지 있음 {w} · 없음 {n}"
        if t == 't67':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            ok = (r['none_line'][0] == ['맨 위 색 띠 없음 (못 읽음)'] and r['none_line'][1] is False and r['none_line'][2] == 'none'
                  and r['top'][0] == ['맨 위 색 띠 있음'] and r['top'][1] is True and r['top'][2] != 'none'
                  and r['both'][1] is True and r['both'][2] != 'none'
                  and r['sec'][0] == ['맨 위 색 띠 없음'] and r['sec'][1] is False and r['sec'][2] == 'none'
                  and r['no'][1] is False and r['no'][2] == 'none'
                  and r['rows'] == [2, True, '같은 이름: 겹치는 메뉴 없음 / 가격 형식: 문제 없음'] and not r['err'])
            return ok, f"381번 맨 위 띠 [줄 없음 {r['none_line']} · 맨 위 {r['top']} · 둘 다 {r['both']} · 분류 {r['sec']} · 없음 {r['no']}] · 점검 박스 {r['rows']}"
        if t == 't66':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            w, n = r['with'], r['none']
            ok = (w['conf'] == ['TEXTAREA:바닥 글', 'DIV:st-corg', 'TEXTAREA:원산지', 'TEXTAREA:원산지'] and w['feet'][0]['notes'] == ['매주 월요일 휴무'] and w['feet'][0]['origin'] == '돼지고기(국내산) 소고기(미국산) 닭고기(태국산) · 연어(노르웨이산) 쌀(국내산)' and w['show'] is True
                  and n['feet'][0]['origin'] == '' and n['show'] is False and r['qr'][0] and r['qr'][2] >= r['qr'][1] - 1 and not r['err'])
            return ok, f"380번 확인 화면 {w['conf']} · 시작 뒤 {w['feet']} 켜짐 {w['show']} · 원산지 없는 사진 {n['feet']} 켜짐 {n['show']} · QR 있을 때 [QR, 바닥 글 줄 아래, 원산지 위] {r['qr']}"
        if t == 't65':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            R = r['res']; n, a, l, ab = R['none'], R['5'], R['4'], R['45']
            ok = (n['left'][1] == n['row'][1] and a['left'][1] <= a['seals']['5'][0] and l['left'][0] >= l['seals']['4'][1] and ab['left'][0] >= ab['seals']['4'][1] and ab['left'][1] <= ab['seals']['5'][0]
                  and len({tuple(x['footH']) for x in R.values()}) == 1 and n['op'] == [False, False] and a['op'] == [False, True] and l['op'] == [True, False] and ab['op'] == [True, True]
                  and l['origin'][0] + 1 >= 0 and all(c in ('rgba(0, 0, 0, 0)', 'transparent') for c in r['zone']) and r['dash'] and all(c != 'rgba(255, 255, 255, 0.5)' for c in r['dash']) and not r['err'])
            return ok, f"379번 바닥 글 칸 [없음 {n['left']} · 오른쪽 {a['left']} · 왼쪽 {l['left']} · 양쪽 {ab['left']}] 도장 {[x['seals'] for x in R.values()]} · 바닥 높이 같음 {len({tuple(x['footH']) for x in R.values()}) == 1} · 원산지 양옆 여백 {[x['op'] for x in R.values()]} · 구역 틀(마우스 없음) {r['zone']} · 빈 칸 점선(띠 없음) {r['dash']}"
        if t == 't64':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            S = r['setup']
            ok = (r['before']['hd'] == '같은 이름: 겹치는 메뉴 없음 / 가격 형식: 문제 없음' and r['before']['btn'] is False and r['before']['nl'] == []
                  and r['after'] == [['네이가츠동', '네기가츠동', '맞춤법', '네이가츠동']] and r['shadow'] == 'none' and r['scale'] == [0.77, True, 1]
                  and S['chips'][:2] == ['메뉴 2개', '분류 1개'] and '제목 색 못 읽음' in S['chips'] and S['why'] and S['note'] == '' and not r['err'])   # 395번. 남은 점검이 없으면 줄을 안 쓴다
            return ok, f"382번 · 395번 확인 화면(맞춤법 없음) {r['before']} · AI 창 맞춤법 카드 {r['after']} · 다음 화면 {r['setup']} · 없음 미리보기 선 {r['shadow']} · [상단 크기, 맞춤법 봄, 의견 수] {r['scale']}"
        if t == 't63':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            bt = r['btn']
            n4 = r.get('nfill374') or {}
            nf_ok = bool(n4) and n4['flat']['n'] == 'flat' and n4['flat'].get('f') is None and n4['flat']['chk'] and n4['flatOff']['n'] == 'flat' and n4['flatOff'].get('f') is False and 'nr-none' in n4['flatOff']['cls'] and not n4['flatOff']['chk'] and n4['flatOn']['n'] == 'flat' and n4['flatOn'].get('f') is None and n4['waveOff']['n'] == 'wave' and n4['waveOff'].get('f') is False and 'nr-unfill' in n4['waveOff']['cls'] and not n4['waveOff']['chk'] and n4['ridgeKeep']['n'] == 'ridge' and n4['ridgeKeep'].get('f') is False and n4['none']['n'] == 'flat' and 'nr-none' in n4['none']['cls'] and not n4['none']['dis'] and n4['rule']['n'] == 'rule' and 'nr-rule' in n4['rule']['cls'] and n4['rule']['chk'] and n4['ruleOff']['n'] == 'plain' and 'nr-plain' in n4['ruleOff']['cls'] and not n4['ruleOff']['chk'] and n4['stair']['n'] == 'ripple' and n4['stair'].get('f') is None and n4['stair']['chk'] and not n4['stair']['dis'] and n4['frame']['n'] == 'frame' and 'nr-frame' in n4['frame']['cls'] and not n4['frame']['dis'] and n4['frameOn']['n'] == 'frame' and n4['frameOn'].get('f') is True and 'nr-framefill' in n4['frameOn']['cls'] and n4['frameOn']['chk'] and n4['waveOff']['lg'] == n4['none']['lg'] and n4['waveOff']['lg'] != n4['flat']['lg'] and n4['opts'] == 14 and n4['tiles'] == [14, ['flat'], True] and n4['tileClick'] == ['arch', 1]   # 374번 · 375번 · 385번(모든 모양에서 채우기 켜고 끔)
            ok = nf_ok and bt[0] == ['편집', 'AI', '꾸미기', '미리보기'] and bt[1] == [False] * 4 and bt[2] == ['편집', 'AI'] and bt[3] == [False, True] and bt[4] == ['false', 'true'] and bt[6] and r['onbg'].split('|')[1] == 'rgb(239, 227, 201)' and r['onbg'].split('|')[0] != 'rgb(239, 227, 201)' and r['hours'] == [[False, False], [None, True]] and r['txt'] == [True, True, '파일 이름', False, False] and r['pcn'] == ['', '밑줄에는 띠가 없습니다', '', ''] and r['pcn2'] == ['띠가 없는 모양입니다', '밑줄에는 띠가 없습니다', '', ''] and r['newmenu'] == [False, True, True, True, True, True, False] \
                 and r['def'] == ['', '', '', ''] and r['set'] == ['rgb(138, 28, 28)', 'rgb(255, 238, 153)', 'rgb(27, 63, 160)', '#2a6f3a', '#8a1c1c', '#ffee99', '#1b3fa0'] and r['dis'] == [False] * 4 \
                 and r['reset'][:4] == [None] * 4 and r['reset'][4] == r['n0'] and r['preset'] == [None, None, None, None] and r['round'] == ['#2a6f3a', '#8a1c1c', '#1b3fa0', '#1b3fa0'] and r['bad'] == [None, None, '#ABCDEF'] and not r['err']
            return ok, f"366번 단추 [이름, 꺼짐, 편집 · AI 이름, 동시에 켜짐, aria, 켜진 색 같음, 꺼진 색 같음] {bt} · 처음 값 {r['def']} · 칠한 뒤 [분류 띠, 분류 글자, 메뉴 이름, 저장 값 4] {r['set']} · 기본으로 단추 켜짐 {r['dis']} · 되돌림 {r['reset']} · 추천 조합 뒤 {r['preset']} · 저장 왕복 {r['round']} · 나쁜 값 {r.get('bad')} · 오류 {r['err'][:2]}"
        if t == 't62':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            ok = r.get('drag') == [True, True, True, True] and r['look'] == ['band', 'sec', 'ramyeon', True, False] and r.get('sectx') == 'rgb(255, 255, 255)' and r.get('pix') == ['#6c6740', None, '#6c6740', None, '#f4f0e0'] and r.get('band372') == [True, True, False, False, True] and r.get('fn373') == [True] * 4 and r['preset'][0] == 'band' and r['preset'][1] == 'ramyeon' and r['final'][0] == 'band' and 'ramyeon' in r['final'][1] and r['none'] == ['', '', ''] and r.get('wrap') == [True] * 4 and r.get('title') == ['custom', '#8a8a1e', 'rgb(138, 138, 30)'] and r.get('ckt') == 'rgb(138, 138, 30)' and r.get('artin') == [True] * 3 and r.get('start') == [False, False, False] and r.get('prev') == ['rgb(138, 138, 30)', '파일 이름'] and not r['err']
            return ok, f"362번 [끌기 막 · 멈추면 사라짐 · 놓으면 새 탭 막힘 · 사진 올라옴] {r.get('drag')} · 읽은 모양 [분류 제목, 띠 위치, 그림, 미리보기 띠] {r.get('look')} · 정한 값 {r.get('preset')} · 편집 화면 {r.get('final')} · 줄 없으면 {r.get('none')} · 364번 [가게 이름 색 로고 색으로 · 확인 화면 색 · 그림 여백선 안] {r.get('title')} {r.get('ckt')} {r.get('artin')} · 363번 긴 줄 [칸 · 줄바뀜 · 가로 안 밀림 · 엔터 막힘] {r.get('wrap')} · 오류 {r['err'][:2]}"
        if t == 't61':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            ok_ck = r['ck_rows'] == 4 and r['ck_h'] >= 200 and r['ck_go'] == 1 and r['ck_ign'] == 3 and r['sum'][0].startswith('점검할 곳이 3건 남아 있습니다')   # 395번. 확인 화면은 같은 이름 2 · 가격 2 — 맞춤법 줄은 AI 창으로
            ok_pl = r['place'] == [False, True, True, True, True, True, True]
            ok_op = r['open'] == [False, True, True, 0, 0, True] and r['gh'] == ['맞춤법 1건', '가격 1건', '같은 이름 2건'] and len(r['rows']) == 4 and r['note'] == [1, 0] and r['scroll'] == [True, True]
            ok_se = r['sel'] == [1, 1, 1, 2] and r['btn_only'].count(True) == 1 and len(r['btn_only']) == 1
            ok_ai = r['sent']['mode'] == 'typo' and '육계장' in r['sent']['names'] and len(r['rows2']) == 5 and any('비빈밥' in x for x in r['rows2']) and not any('없는이름' in x for x in r['rows2'])
            ok_ap = r['applied'][0] == '육개장' and r['applied'][1] == '육개장' and r['applied'][2] and r['undone'] == '육계장'
            ok_ig = r['ign'] == [5, 4, 1] and r['lang'] == ['en', False]
            ok_st = r['stray'] == [1, '야끼소바dd', '야끼소바', True] and '아직 안 봤습니다' in r['empty'] and r['labels'] == ['틀린 곳', '이렇게', '이유', '위치']
            ok_sh = r['shoplike'] == [True, True, True, False, False, False, False, False, False, False] and r['sealsym'] == [False, True, True]
            ok_lk = r['look'] == [True, False, 'rgb(245, 236, 215)', True]
            ok_sw = r['swap'] == [[True, False, 0], [False, True], [True, 0, False]] and r['print'] == 'none' and r['save'] == [True, '', 0]
            ok_nw = all(isinstance(v, list) and v[0] and v[1] and v[2] >= 4 and v[3] for v in r['narrow'].values()) and len(r['narrow']) == 3
            ok_sv = r['server'] is None or r['server'] == [True, True, True]
            ok = ok_ck and ok_pl and ok_op and ok_se and ok_ai and ok_ap and ok_ig and ok_sw and ok_st and ok_sh and ok_lk and ok_nw and ok_sv and r['mem'] == [2, 2] and not r['err']
            return ok, f"확인 화면 점검 {ok_ck} {[r['ck_rows'], r['ck_go'], r['ck_ign'], r['sum']]} · 자리 {r['place']} · 열기 {ok_op} {r['open']} {r['gh']} {r['note']} {r['scroll']} · 고르면 {ok_se} {r['sel']} · AI {ok_ai} {len(r['rows'])} → {len(r['rows2'])} · 적용 {r['applied']} → 되돌림 {r['undone']} · 무시 {r['ign']} · 꾸미기와 한자리 {r['swap']} 인쇄 {r['print']} 저장 {r['save']} · 번역 {r['lang']} · 기억 {r['mem']} · 폰 폭(막대 단추 · 줄 안 넘침 · 줄 수 · 창이 화면 안) {r['narrow']} · 서버 {r['server']}"
        if t == 't60':
            if r.get('fail'): return False, f"실패: {r['fail']}"
            w, m, h, k = r['wine'], r['mix'], r['hansik'], r['colors']
            ok_w = w[0]['concept'] == 'wine' and w[0]['tags'] == 3 and w[2]['kinds'] == ['wine'] and w[2]['item'][0].get('origin') == '프랑스 · 보르도' and w[2]['item'][0]['price'] == '28,000 / 168,000' and w[2]['item'][2]['price'] == 88000 and w[2]['feet'][0] == ['가격은 글라스 / 병 순서입니다'] and w[2]['pages'][0]['art'] == ['vine'] and w[1]['name'] == '사진처럼' and w[1]['font'] == 'myeongjo' and not any(w[2]['over'])
            ok_m = m[2]['kinds'] == ['menu', 'wine'] and m[2]['feet'][0] == [] and m[2]['feet'][1] == ['가격은 글라스 / 병 순서입니다'] and m[2]['pages'][0]['art'] == ['lantern'] and m[2]['pages'][1]['art'] == ['vine'] and m[2]['font'] == 'gothic' and all(p['autofit'] for p in m[2]['pages']) and not any(m[2]['over'])
            ok_h = h[1]['name'] == '추천 · 한식 식당' and h[1]['art'] == 'ttuk' and h[1]['font'] == 'serif' and h[1]['theme'] == 'pat' and h[2]['kinds'] == ['menu'] and h[2]['pages'][0]['art'] == ['ttuk'] and h[2]['theme'] == 'pat'
            ok_c = k[0]['concept'] is None and k[1]['name'] == '사진처럼' and k[1]['art'] == 'none' and k[2]['kinds'] == ['menu'] and k[2]['pages'][0]['art'] == []   # 콘셉트가 없으면 예전 그대로
            q = r['qrbg']; U = ['https://naver.me/abcd']
            ok_q = q is None or (q[0][0][0] == '#fff' and q[0][0][2] == U and q[0][1][0] == '#e8dcc2' and q[0][1][2] == U and q[0][2][0] is None and q[0][2][2] == U
                and '못 읽을 수' in q[1] and '못 읽을 수' in q[2] and '못 읽을 수' not in q[3] and '못 읽을 수' not in q[4]
                and q[5]['shown'] is True and q[5]['val'] == '#ffffff' and q[5]['pick'] == '#112233' and q[5]['white'] is True and q[5]['none'] == 'none' and q[5]['on'] is True and q[5]['dim'] is True and q[5]['back'] is True and q[5]['off'] is True)   # 348번
            ok = all(r['prompt']) and ok_w and ok_m and ok_h and ok_c and ok_q and r['groups'][-1].startswith('산 · 동물 · 풍경') and r['groups'][0] != r['groups'][-1] and r['norm'] == [None, None, '#e8dcc2', 'none', None] and r['nscale'][0] == '30' and r['nscale'][2] <= r['nscale'][1] - 20 and r['nscale'][3] == 0.3 and r['nscale'][4] is True and r['nscale'][5] is True and r['narrow'] == [True, True] and r['narrow_box'] == [True, True, True] and r['wide'] == [False, False] and not r['err']
            return ok, f"요청 글 {r['prompt']} · 와인만 {ok_w} · 섞임 {ok_m} · 한식 콘셉트만 {ok_h} · 콘셉트 없음 {ok_c} · QR 바탕 {'읽는 도구 없음' if q is None else ok_q} · 그림 목록 맨 아래 {r['groups'][-1]} · 폰 {r['narrow']} · 컴퓨터 {r['wide']} · 정리 {r['norm']} · 맨 위 크기 [막대 최소, 60% 높이, 30% 높이, 눌러 본 하한, 작을 때 안내, 끄면 안내 없음] {r['nscale']}"
        if t == 't58':
            if r.get('no_reader'): return False, '만든 QR 을 읽는 도구가 없습니다 — pip install zxing-cpp'
            if r.get('fail'): return False, f"실패: {r['fail']}"
            ok = (r['read'] == [True] * 5 and r['none_drawn'] == [0, 1] and not r['layout_bad'] and not r['fit_bad'] and r['mid'] == [1] and all(r['panel']) and len(r['panel']) == 18 and r['excl'] == [0, 5] and r['loadqr'] == [True, 3, [], 0]
                  and r['saved'] == ['[{"cell":5,"kind":"wifi","ssid":"알프스","pass":"pw;1","enc":"WPA","label":"와이파이"}]', 1]
                  and r['norm'] == [[[4, 'url', 300, 20, '-'], [5, 'wifi', 1, 0, '']], False, False] and not r['err'])
            return ok, f"읽은 값 {r['read']} · 못 읽는 주소 · 빈 칸 · 300자 그려짐 {r['none_drawn']} · 자리(위 = 단 맨 위 · 아래 = 바닥 글 옆 · 글자 · 도장과 안 겹침 · 20 ~ 30mm) 문제 {r['layout_bad'] or '없음'} · 한 장에 맞춤 + QR 겹침 {r['fit_bad'] or '없음'} · 가운데 칸 QR 은 버림 {r['mid']} · 꾸미기 창(격자 한 그림 — 탭 한 줄 · 구분선 · 맨 위 좌우 끝 = QR · 아래 두 칸은 모퉁이 하나만) {r['panel']} · 열 때 겹친 파일 {r['excl']} · 저장 데이터를 불러오는 순간 [종이 그려짐, QR 수, 남은 도장, 오류] {r['loadqr']} · 저장했다 연 뒤 {r['saved']} · 망가진 값 {r['norm']}"
        if t == 't71':
            o = r['origin']
            ok = (r['handles'] == ['art', 'qr', 'seal'] and r['hidden_other_tab'] and r['pos'][:3] == [True, True, True] and r['pos'][3] == {'x': 0, 'y': 1}
                  and all(x[1] for x in r['inbox']) and len(r['inbox']) == 3 and r['sel'][:2] == [4, None] and r['sel'][2] == ['free'] and r['print'] == [True, True]
                  and r['labtop'] == ['top', 'qrl top'] and r['back_cell'] is False and r['free_here'] == [True, True] and all(x[1] for x in r['land_inbox']) and len(r['land_inbox']) == 3
                  and r['norm'] == '[[{"cell":0,"art":"beer"},{"cell":1,"art":"beer","pos":{"x":1,"y":0}}],[{"cell":2,"seal":"word"}],[{"cell":4,"kind":"url","url":"a.b"},{"cell":5,"kind":"url","url":"a.b","lab":"top","pos":{"x":0.25,"y":0.5}}]]'
                  and o[0][0] == o[1][0] and o[1][1] == o[2][1] and all(x[2] == '1' and x[3] == '1' for x in o) and not r['err'])
            return ok, f"402번 손잡이 {r['handles']} · 끈 뒤 pos {r['pos']} · 점선 안 {r['inbox']} · 인쇄 같음 · 손잡이 안 찍힘 {r['print']} · 이름 위 {r['labtop']} · 칸으로 {not r['back_cell']} · 제자리 자유 {r['free_here']} · 가로 점선 안 {[x[1] for x in r['land_inbox']]} · 원산지 [바닥 높이 · 윗선 폭 · 투명도] 편집 빈 칸 {o[0]} · 편집 {o[1]} · 미리보기 {o[2]}"
        if t == 't72':
            tb, rc = r['table'], r['rect']; pn = r['panel']
            ok_t = tb[0] == [] and tb[1] == [] and tb[2] == tb[3]
            ok_r = len(rc) == 8 * 4 + 3 * 4 and all(x[4] and x[5] and x[6] for x in rc)
            ok_b = len(r['box']) == 2 and all(abs(x[0] - 91) < .3 for x in r['box']) and abs(r['box'][0][1] - 14) < .3 and abs(r['box'][1][1] - 105) < .3
            ok_d = r['drag'][0] == {'x': 0, 'y': 0} and r['drag'][1] and r['drag'][2]
            ok_p = pn[0] == 3 and pn[1] and pn[2] and pn[6] and pn[7]
            ok = ok_t and ok_r and ok_b and r['handle'] == [True, True] and ok_d and ok_p and not r['err']
            return ok, f"403번 표가 그림마다 다시 잰 값과 같음 {ok_t} {tb[0][:3]} · 구석에서 점선 안 + 변에 닿음 {ok_r} {[x[:4] for x in rc if not (x[4] and x[5] and x[6])][:6]} · 칸 배치 상자 폭 · 왼쪽 {ok_b} {r['box']} · 손잡이 가운데 {r['handle']} · 끌어서 모서리까지 {r['drag']} · 꾸미기 창 [상자 수, 모두 상자, 칸 고르기, 이름 셋, 이어 붙음, 이름표 색, 이름표, 이 장만 숨김, QR 제목] {pn}"
        if t == 'tstatic': ok = r.get('css_braces', [0, []]) == [0, []] and r['css_comments'][0] == r['css_comments'][1] and r['html_comments'][0] == r['html_comments'][1] and r['node'] in (True, 'node 없음') and r['dialog_tags_ok']; return ok, f"CSS 괄호 {r.get('css_braces')} · 주석 짝 CSS {r['css_comments']} · HTML {r['html_comments']} · JS {r['node']} · 안내창 태그 짝 {r['dialog_tags_ok']}"
    except Exception as e:
        return False, f'판정 실패: {e}'
    return None, ''

ALL = ['tstatic', 't02', 't03', 't04', 't04p', 't05', 't06', 't07', 't08', 't10', 't11', 't14', 't15', 't16', 't17', 't21', 't23', 't24',
       't25', 't27', 't28', 't30', 't31v', 't32', 't35', 't36', 't37', 't38', 't39', 't40', 't41', 't42', 't43', 't44', 't45', 't46', 't47', 't48', 't49', 't50', 't51', 't52', 't53', 't54', 't55', 't56', 't57', 't58', 't59', 't60', 't61', 't62', 't63', 't64', 't65', 't66', 't67', 't68', 't69', 't70', 't71', 't72', 't02b']
# 305번. 빠른 묶음 — 304번에 잰 시간(한 파일 기준)이 45초 이하인 것. 빠진 무거운 것: t02 · t04p · t05 · t07 · t08 · t15 · t23 · t25 · t31v · t32 · t37 · t45
QUICK = ['tstatic', 't06', 't10', 't11', 't14', 't16', 't17', 't21', 't24', 't28', 't30', 't35', 't36', 't38', 't39', 't40', 't41', 't42',
         't43', 't44', 't46', 't47', 't48', 't49', 't50', 't51', 't52', 't53', 't54', 't55', 't56', 't57', 't58', 't59', 't60', 't61', 't62', 't63', 't64', 't65', 't66', 't67', 't68', 't69', 't70', 't71', 't72', 't02b']
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
    if tests == ['quick']: tests = QUICK   # 305번
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
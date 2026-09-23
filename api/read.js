// 메뉴판 사진 읽기 — 버셀 서버 함수(276번). 메뉴판(index.html)이 사진을 보내면 제미나이로 읽어 글로 돌려준다.
//
// 왜 서버를 거치나
//   키를 브라우저에 두면 페이지를 연 누구나 꺼내 쓸 수 있다. 키는 여기(버셀 환경 변수)에만 둔다.
//   가게 사장님은 키 없이 사진만 올린다.
//
// 이 함수가 하는 일은 "메뉴판 사진 읽기" 하나뿐이다
//   요청 글(PROMPT)은 여기 고정이다 — 받는 것은 사진뿐. 주소가 알려져도 공짜 제미나이 창구로 못 쓴다.
//   PROMPT 는 index.html 의 READ_PROMPT 와 같아야 한다(다른 AI 앱 길이 같은 글을 쓴다). 고치면 둘 다
//
// 비용
//   GEMINI_API_KEY 는 결제 등록 없는 무료 키로 둔다 — 한도를 넘으면 멈출 뿐 청구되지 않는다.
//   한도는 모델마다 따로다(실습 0827 의 기록) — 분당 한도에 걸리면 다음 모델로 한 번 더
//
// 버셀 설정  Settings → Environment Variables
//   GEMINI_API_KEY   필수
//   GEMINI_MODEL     선택. 비우면 gemini-3.5-flash-lite
//   ALLOWED_ORIGINS  선택. 쉼표로. 비우면 https://menupan-jin.vercel.app 와 컴퓨터 파일(null)
//   READ_ENABLED     선택. off 면 사진 읽기를 끈다(278번 — 제미나이를 아예 부르지 않는다). 비우거나 on 이면 켜짐
//   바꾼 뒤에는 Deployments 에서 Redeploy 해야 적용된다

const PROMPT = [
  "이 사진은 가게 메뉴판입니다. 적힌 메뉴를 아래 모양으로만 적어 주세요. 다른 말은 쓰지 마세요.",
  "[분류 이름]",
  "메뉴 이름 | 가격",
  "",
  "- 가격은 숫자만 적습니다(쉼표 · 원 없이). 가격이 없거나 '시가' 같은 글자면 그 글자를 그대로 적습니다.",
  "- 분류가 안 보이면 [메뉴] 하나로 적습니다.",
  "- 잘 안 보이거나 확실하지 않은 이름 · 가격은 그 값 바로 뒤에 ? 를 붙입니다.",
  "- 메뉴 설명 · 원산지 · 영업시간 · 전화번호는 적지 않습니다.",
  "- 가게 이름이 보이면 맨 첫 줄에 '가게: 가게 이름' 으로 적습니다. 안 보이면 이 줄은 쓰지 않습니다."
].join("\n");   // 290번. index.html 의 READ_PROMPT 와 같게
const DEFAULT_MODEL = "gemini-3.5-flash-lite";
const MAX_B64 = 4000000;   // 사진(base64) 약 3MB. 메뉴판은 긴 쪽 1600px JPEG 로 줄여 보낸다(보통 0.5MB 안)

function allowed(origin){
  const list = (process.env.ALLOWED_ORIGINS || "https://menupan-jin.vercel.app,null").split(",").map(s => s.trim()).filter(Boolean);
  return !!origin && list.includes(origin);
}

module.exports = async function handler(req, res){
  const origin = req.headers.origin || "";
  if (allowed(origin)){
    res.setHeader("Access-Control-Allow-Origin", origin);   // 컴퓨터 파일에서 연 메뉴판은 Origin 이 "null"
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  }
  if (req.method === "OPTIONS"){ res.status(allowed(origin) ? 204 : 403).end(); return; }
  const on = String(process.env.READ_ENABLED || "on").trim().toLowerCase() !== "off";   // 278번. 켜고 끄는 스위치
  if (req.method === "GET"){ res.status(200).json({ enabled:on && !!process.env.GEMINI_API_KEY }); return; }   // 메뉴판이 사진 창을 열 때 묻는다
  if (req.method !== "POST"){ res.status(405).json({ error:"POST 만 받습니다", code:"method" }); return; }
  if (!on){ res.status(503).json({ error:"사진 읽기를 꺼 두었습니다", code:"off" }); return; }
  if (!allowed(origin)){ res.status(403).json({ error:"이 주소에서 온 요청은 받지 않습니다", code:"origin" }); return; }

  const key = process.env.GEMINI_API_KEY;
  if (!key){ res.status(500).json({ error:"GEMINI_API_KEY 가 설정되지 않았습니다", code:"nokey" }); return; }

  let body = req.body;
  if (typeof body === "string"){ try { body = JSON.parse(body); } catch(e){ body = {}; } }
  const img = body && typeof body.image === "string" ? body.image : "";
  const m = img.match(/^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/);
  if (!m){ res.status(400).json({ error:"사진(data:image/…;base64)이 필요합니다", code:"image" }); return; }
  if (m[2].length > MAX_B64){ res.status(413).json({ error:"사진이 너무 큽니다", code:"size" }); return; }

  const first = process.env.GEMINI_MODEL || DEFAULT_MODEL;
  const models = [...new Set([first, DEFAULT_MODEL, "gemini-2.5-flash-lite", "gemini-2.5-flash"])];
  let lastStatus = 0, lastDetail = "";
  const t0 = Date.now(), tries = [];   // 292번. 모델마다 걸린 시간 — 버셀 Logs 에 남긴다(느려진 까닭을 가리려고)
  const log = extra => console.log(JSON.stringify({ route:"read", ms:Date.now() - t0, tries, ...extra }));
  for (const model of models){
    let r; const t1 = Date.now();
    try {
      r = await fetch("https://generativelanguage.googleapis.com/v1beta/models/" + encodeURIComponent(model) + ":generateContent", {
        method:"POST", headers:{ "Content-Type":"application/json", "x-goog-api-key":key },
        body:JSON.stringify({ contents:[{ parts:[{ text:PROMPT }, { inline_data:{ mime_type:m[1], data:m[2] } }] }],
                              generationConfig:{ temperature:0, maxOutputTokens:2048 } })
      });
    } catch(e){ lastStatus = 502; lastDetail = String(e && e.message || e).slice(0, 200); tries.push({ model, status:"fetch", ms:Date.now() - t1 }); continue; }
    tries.push({ model, status:r.status, ms:Date.now() - t1 });
    if (r.status >= 500 && !r.retried){   // 295번. 구글 쪽 일시 오류(500 · 503 등)는 같은 모델로 1초 뒤 한 번 더 — 사장님이 [읽기]를 다시 눌러야 했다(2.7초 만의 502)
      await new Promise(ok => setTimeout(ok, 1000)); const t2 = Date.now();
      try { const r2 = await fetch("https://generativelanguage.googleapis.com/v1beta/models/" + encodeURIComponent(model) + ":generateContent", {
          method:"POST", headers:{ "Content-Type":"application/json", "x-goog-api-key":key },
          body:JSON.stringify({ contents:[{ parts:[{ text:PROMPT }, { inline_data:{ mime_type:m[1], data:m[2] } }] }], generationConfig:{ temperature:0, maxOutputTokens:2048 } }) });
        r2.retried = true; tries.push({ model, status:r2.status, ms:Date.now() - t2, retry:true }); r = r2; } catch(e){ tries.push({ model, status:"fetch", ms:Date.now() - t2, retry:true }); }
    }
    if (r.status === 404 || r.status === 429){ lastStatus = r.status; lastDetail = (await r.text()).slice(0, 300); continue; }   // 모델이 없거나 그 모델 한도 — 다음 모델
    if (!r.ok){ log({ result:"error" }); res.status(502).json({ error:"제미나이 응답 오류 " + r.status, code:"gemini", detail:(await r.text()).slice(0, 300), model }); return; }
    const data = await r.json();
    const text = ((((data.candidates || [])[0] || {}).content || {}).parts || []).map(p => p.text || "").join("");
    if (!text.trim()){ log({ result:"empty" }); res.status(422).json({ error:"빈 답", code:"empty", model }); return; }
    log({ result:"ok", model }); res.status(200).json({ text:text.slice(0, 20000), model, ms:Date.now() - t0, tries:tries.length });
    return;
  }
  log({ result:"fail" });
  res.status(lastStatus === 429 ? 429 : 502).json({ error: lastStatus === 429 ? "무료 사용 한도" : "쓸 수 있는 모델이 없습니다", code: lastStatus === 429 ? "limit" : "model", detail:lastDetail });
};
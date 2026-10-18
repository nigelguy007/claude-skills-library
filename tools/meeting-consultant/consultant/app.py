"""HTTP server: join form, live meeting pages, Recall webhooks, and the standalone assistant."""
import asyncio
import contextlib
import html
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from .agents import Researcher
from .assistant import Assistant
from .brain import Consultant
from .config import Settings
from .llm import LLM
from .providers import Providers
from .recall import RecallClient
from .skills import SkillLibrary
from .tts import TTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
esc = html.escape

CSS = """<style>
:root{--bg:#f5f6f8;--panel:#fff;--fg:#1a1d24;--muted:#5f6878;--line:#dde1e8;--accent:#2a56c6}
@media(prefers-color-scheme:dark){:root{--bg:#111419;--panel:#1a1e26;--fg:#e6e9ef;--muted:#99a2b1;--line:#2c323d;--accent:#7d9dff;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin-bottom:12px}
input,textarea,select,button{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px 10px;width:100%}
button{background:var(--accent);color:#fff;border-color:var(--accent);cursor:pointer;width:auto}label{display:block;margin:8px 0 4px;color:var(--muted);font-size:13px}
a{color:var(--accent)}.muted{color:var(--muted);font-size:13px}pre{white-space:pre-wrap;font:13px/1.45 ui-monospace,Menlo,monospace;margin:0}
ul{margin:4px 0;padding-left:20px}.pill{display:inline-block;padding:1px 8px;border-radius:10px;border:1px solid var(--line);font-size:12px}
</style>"""


def page(title: str, body: str, refresh: Optional[int] = None) -> HTMLResponse:
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return HTMLResponse(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                        f'content="width=device-width,initial-scale=1">{meta}<title>{esc(title)}</title>{CSS}</head>'
                        f"<body><main>{body}</main></body></html>")


def config_problems(settings: Settings):
    problems = []
    if not settings.anthropic_api_key:
        problems.append("ANTHROPIC_API_KEY is not set: the bot can't think.")
    if not settings.recall_api_key:
        problems.append("RECALL_API_KEY is not set: the bot can't join meetings.")
    if settings.webhook_token == "change-me":
        problems.append("WEBHOOK_TOKEN is still the default. Set a long random value.")
    if not settings.admin_token:
        problems.append("ADMIN_TOKEN is not set: anyone with the URL can use the bot and read meeting notes.")
    if settings.public_base_url.startswith("http://localhost"):
        problems.append("PUBLIC_BASE_URL is localhost: Recall can't reach it. Use your deployed URL or a tunnel.")
    return problems


def build(settings: Settings):
    llm = LLM(settings)
    skills = SkillLibrary(settings.skills_dirs, settings.learned_skills_dir)
    providers = Providers(settings, llm)
    researcher = Researcher(settings, llm, providers)
    recall = RecallClient(settings.recall_api_key or "", settings.recall_region)
    consultant = Consultant(settings, recall, llm, skills, TTS(settings), researcher)
    assistant = Assistant(settings, llm, skills, researcher, providers, consultant)
    return consultant, assistant


def create_app(settings: Optional[Settings] = None, consultant: Optional[Consultant] = None,
               assistant: Optional[Assistant] = None) -> FastAPI:
    settings = settings or Settings()
    if consultant is None:
        consultant, assistant = build(settings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        for problem in config_problems(settings):
            logging.warning("CONFIG: %s", problem)
        await asyncio.to_thread(consultant.skills.index)

        async def loop():
            while True:
                await asyncio.sleep(10)
                try:
                    await consultant.tick()
                except Exception:  # noqa: BLE001
                    logging.exception("tick failed")

        task = asyncio.create_task(loop())
        yield
        task.cancel()

    app = FastAPI(title="Meeting consultant", lifespan=lifespan)

    def authed(request: Request) -> bool:
        if not settings.admin_token:
            return True
        supplied = (request.headers.get("x-admin-token") or request.cookies.get("mc_key")
                    or request.query_params.get("key"))
        return supplied == settings.admin_token

    def guard(request: Request) -> None:
        if not authed(request):
            raise HTTPException(401, "Add ?key=<ADMIN_TOKEN> to the URL once to sign in.")

    def check_token(token: str) -> None:
        if token != settings.webhook_token:
            raise HTTPException(403, "bad token")

    def with_cookie(resp, request: Request):
        key = request.query_params.get("key")
        if key and key == settings.admin_token:
            resp.set_cookie("mc_key", key, httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 24 * 90)
        return resp

    # ---------------------------------------------------------------- webhooks (Recall -> us)
    @app.post("/webhook/recall/realtime")
    async def realtime(request: Request, background: BackgroundTasks, token: str = ""):
        check_token(token)
        background.add_task(consultant.on_realtime, await request.json())
        return {"ok": True}

    @app.post("/webhook/recall/status")
    async def status(request: Request, background: BackgroundTasks, token: str = ""):
        check_token(token)
        background.add_task(consultant.on_status, await request.json())
        return {"ok": True}

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "skills_indexed": len(consultant.skills.skills), "meetings": len(consultant.meetings),
                "ai_services": assistant.providers.available() if assistant else [],
                "config_problems": config_problems(settings)}

    # ---------------------------------------------------------------- meetings
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        guard(request)
        rows = "".join(
            f'<li><a href="/meetings/{m.id}">{esc(m.topic or m.meeting_url)}</a> <span class="pill">{m.status}</span></li>'
            for m in sorted(consultant.meetings.values(), key=lambda m: -m.created_at)[:20]) or "<li>None yet</li>"
        body = f"""<h1>{esc(settings.short_name)}: meeting consultant</h1>
<p class="muted">Paste a Zoom, Google Meet or Teams link. The bot joins, listens, answers when someone says
"{esc(settings.short_name)}", and writes a memo and research notes afterwards. <a href="/assistant">Open the voice assistant</a>.</p>
<form class="card" method="post" action="/join">
<label for="u">Meeting link</label><input id="u" name="meeting_url" required placeholder="https://meet.google.com/abc-defg-hij">
<label for="t">Topic</label><input id="t" name="topic" placeholder="Scoping the MVP for our invoice-chasing tool">
<label for="c">Context for the consultant (optional)</label><textarea id="c" name="context" rows="3" placeholder="Who's attending, what you want to decide, background it should know"></textarea>
<label for="mo">How it participates</label><select id="mo" name="mode"><option value="chat">Chat messages</option><option value="voice">Chat + short spoken questions</option></select>
<p><button type="submit">Send the consultant in</button></p></form>
<h2>Meetings</h2><div class="card"><ul>{rows}</ul></div>
<p class="muted">{len(consultant.skills.skills)} skills indexed.</p>"""
        return with_cookie(page("Meeting consultant", body), request)

    @app.post("/join")
    async def join(request: Request, meeting_url: str = Form(...), topic: str = Form(""), context: str = Form(""),
                   mode: str = Form("chat")):
        guard(request)
        try:
            m = await consultant.join(meeting_url.strip(), topic.strip(), context.strip(), mode)
        except Exception as e:  # noqa: BLE001
            return page("Couldn't join", f"<h1>Couldn't send the bot</h1><p>{esc(str(e))}</p><p><a href='/'>Back</a></p>")
        return RedirectResponse(f"/meetings/{m.id}", status_code=303)

    @app.post("/api/join")
    async def api_join(request: Request):
        guard(request)
        body = await request.json()
        m = await consultant.join(body["meeting_url"], body.get("topic", ""), body.get("context", ""), body.get("mode"))
        return {"id": m.id, "status": m.status, "mode": m.mode, "note": m.error}

    def get_meeting(meeting_id: str):
        m = consultant.meetings.get(meeting_id)
        if not m:
            raise HTTPException(404, "No such meeting")
        return m

    @app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
    async def meeting_page(request: Request, meeting_id: str):
        guard(request)
        m = get_meeting(meeting_id)
        b = m.brief or {}

        def lst(items):
            items = [i if isinstance(i, str) else " — ".join(str(v) for v in i.values() if v) for i in (items or [])]
            return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else '<p class="muted">Nothing yet.</p>'

        brief = (f"<p>{esc(b.get('summary', ''))}</p><h3>Decisions</h3>{lst(b.get('decisions'))}"
                 f"<h3>Open questions</h3>{lst(b.get('open_questions'))}<h3>Untested assumptions</h3>{lst(b.get('risks_assumptions'))}"
                 f"<h3>Actions</h3>{lst(b.get('action_items'))}") if b else '<p class="muted">The brief appears after a couple of minutes of discussion.</p>'
        said = "".join(f"<li><b>{esc(i['kind'])}</b>: {esc(i['text'][:400])}</li>" for i in reversed(m.interventions[-15:]))
        skills = ", ".join(f"{esc(s['name'])} <span class='muted'>({esc(s.get('why', ''))})</span>" for s in m.skills) or "None yet"
        links = " · ".join(x for x in [
            f'<a href="/meetings/{m.id}/report">Memo</a>' if m.report_path else "",
            f'<a href="/meetings/{m.id}/notes">Research and follow-up notes</a>' if m.notes_path else "",
            f'<a href="/meetings/{m.id}/transcript">Transcript</a>' if m.utterances else ""] if x)
        finish = (f'<form method="post" action="/meetings/{m.id}/finish"><button>Leave and write up now</button></form>'
                  if m.status in ("joining", "live") else "")
        body = f"""<p><a href="/">← All meetings</a></p><h1>{esc(m.topic or 'Meeting')}</h1>
<p><span class="pill">{m.status}</span> <span class="muted">{esc(m.meeting_url)} · mode: {m.mode}{' · quiet' if m.quiet else ''}</span></p>
{f'<p class="muted">{esc(m.error)}</p>' if m.error else ''}<p>{links}</p>{finish}
<h2>Running brief</h2><div class="card">{brief}</div>
<h2>Expert profile and playbooks</h2><div class="card"><p>{esc((m.profile or {}).get('expert_persona', 'Not decided yet'))}</p><p class="muted">{skills}</p></div>
<h2>What the bot has done</h2><div class="card"><ul>{said or '<li>Nothing yet</li>'}</ul></div>
<h2>Latest transcript</h2><div class="card"><pre>{esc(m.recent(20)) or 'Waiting for speech…'}</pre></div>"""
        return page(m.topic or "Meeting", body, refresh=15 if m.status in ("joining", "live", "finishing") else None)

    def read_file(path: Optional[str], what: str) -> PlainTextResponse:
        if not path or not Path(path).exists():
            raise HTTPException(404, f"No {what} yet")
        return PlainTextResponse(Path(path).read_text(), media_type="text/markdown; charset=utf-8")

    @app.get("/meetings/{meeting_id}/report")
    async def report(request: Request, meeting_id: str):
        guard(request)
        return read_file(get_meeting(meeting_id).report_path, "memo")

    @app.get("/meetings/{meeting_id}/notes")
    async def notes(request: Request, meeting_id: str):
        guard(request)
        return read_file(get_meeting(meeting_id).notes_path, "notes")

    @app.get("/meetings/{meeting_id}/transcript")
    async def transcript(request: Request, meeting_id: str):
        guard(request)
        return PlainTextResponse(get_meeting(meeting_id).transcript_text(10_000_000))

    @app.post("/meetings/{meeting_id}/finish")
    async def finish(request: Request, meeting_id: str, background: BackgroundTasks):
        guard(request)
        background.add_task(consultant.finish, get_meeting(meeting_id), True)
        return RedirectResponse(f"/meetings/{meeting_id}", status_code=303)

    # ---------------------------------------------------------------- standalone assistant
    @app.get("/assistant", response_class=HTMLResponse)
    async def assistant_page(request: Request):
        guard(request)
        return with_cookie(HTMLResponse(ASSISTANT_HTML.replace("__NAME__", esc(settings.short_name))
                                        .replace("__WAKE__", esc((settings.wake_words or [settings.short_name])[0].lower()))),
                           request)

    @app.post("/api/assistant")
    async def assistant_ask(request: Request):
        guard(request)
        text = (await request.json()).get("text", "")
        return {"reply": await assistant.ask(text)}

    @app.get("/api/assistant/events")
    async def assistant_events(request: Request, after: int = 0):
        guard(request)
        return {"events": assistant.events_after(after)}

    @app.post("/api/research")
    async def research(request: Request):
        guard(request)
        body = await request.json()
        job = assistant.researcher.start(body["question"], body.get("context", ""), on_done=assistant._research_done)
        return {"job_id": job.id}

    @app.get("/api/research/{job_id}")
    async def research_job(request: Request, job_id: str):
        guard(request)
        job = assistant.researcher.to_dict(job_id)
        if not job:
            raise HTTPException(404, "No such job")
        return JSONResponse(json.loads(json.dumps(job, default=str)))

    return app


ASSISTANT_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<title>__NAME__</title>""" + CSS + """<style>
main{display:flex;flex-direction:column;min-height:100vh;gap:12px;padding-bottom:calc(20px + env(safe-area-inset-bottom))}
#log{flex:1;display:flex;flex-direction:column;gap:8px}
.msg{padding:10px 12px;border-radius:10px;max-width:88%;white-space:pre-wrap;border:1px solid var(--line)}
.me{align-self:flex-end;background:var(--accent);color:#fff;border-color:var(--accent)}.bot{align-self:flex-start;background:var(--panel)}
.note{align-self:center;color:var(--muted);font-size:13px;text-align:center}
#talk{width:96px;height:96px;border-radius:50%;font-size:15px;align-self:center}
#talk.on{background:#d13a3a;border-color:#d13a3a}.row{display:flex;gap:8px;align-items:center}.row input[type=text]{flex:1}
</style></head><body><main>
<h1>__NAME__</h1><p class="muted" id="hint">Tap the button and speak, or type below. Turn on hands-free and say "__WAKE__" before a request.</p>
<div id="log"></div>
<button id="talk" aria-label="Tap to talk">Tap to talk</button>
<div class="row"><label class="muted" style="margin:0;display:flex;gap:6px;align-items:center;white-space:nowrap"><input type="checkbox" id="hands" style="width:auto"> Hands-free</label>
<label class="muted" style="margin:0;display:flex;gap:6px;align-items:center;white-space:nowrap"><input type="checkbox" id="speak" style="width:auto" checked> Read replies aloud</label></div>
<form class="row" id="f"><input type="text" id="q" placeholder="Ask anything, or: join my meeting at https://…" autocomplete="off"><button>Send</button></form>
</main><script>
const WAKE="__WAKE__", log=document.getElementById('log'), talk=document.getElementById('talk');
let lastEvent=0, busy=false, rec=null, listening=false;
function add(cls,t){const d=document.createElement('div');d.className='msg '+cls;d.textContent=t;log.appendChild(d);d.scrollIntoView({behavior:'smooth'});}
function say(t){if(!document.getElementById('speak').checked||!window.speechSynthesis)return;speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(t.replace(/[#*_`]/g,''));speechSynthesis.speak(u);}
async function ask(text){text=text.trim();if(!text||busy)return;busy=true;add('me',text);const w=document.createElement('div');w.className='note';w.textContent='Thinking…';log.appendChild(w);
 try{const r=await fetch('/api/assistant',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text})});
  const j=await r.json();w.remove();if(!r.ok)throw new Error(j.detail||r.status);add('bot',j.reply);say(j.reply);await poll(true);}
 catch(e){w.textContent='Error: '+e.message;}finally{busy=false;}}
async function poll(skipReplies){try{const r=await fetch('/api/assistant/events?after='+lastEvent);const j=await r.json();
 for(const e of j.events){lastEvent=Math.max(lastEvent,e.id);if(e.kind==='research'){add('bot',e.text);say(e.text);}}}catch(e){}}
(async()=>{try{const r=await fetch('/api/assistant/events?after=0');const j=await r.json();for(const e of j.events.slice(-12)){lastEvent=Math.max(lastEvent,e.id);if(e.kind==='reply'){add('me',e.question);add('bot',e.text);}else add('bot',e.text);}}catch(e){}})();
setInterval(()=>poll(false),5000);
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
function startRec(continuous){if(!SR){add('note','Voice input needs Chrome, Edge or Safari. You can still type.');return;}
 rec=new SR();rec.lang=navigator.language||'en-GB';rec.continuous=continuous;rec.interimResults=false;listening=true;talk.classList.add('on');talk.textContent=continuous?'Listening…':'Speak now';
 rec.onresult=e=>{const t=e.results[e.results.length-1][0].transcript.trim();if(!continuous){ask(t);return;}
  const i=t.toLowerCase().indexOf(WAKE);if(i>=0){const cmd=t.slice(i+WAKE.length).replace(/^[\\s,.!?]+/,'');if(cmd)ask(cmd);else say('Yes?');}};
 rec.onerror=e=>{if(e.error==='not-allowed'){add('note','Microphone blocked. Allow it in your browser settings.');stopRec();}};
 rec.onend=()=>{if(listening&&document.getElementById('hands').checked){try{rec.start();}catch(e){}}else stopRec();};
 try{rec.start();}catch(e){}}
function stopRec(){listening=false;talk.classList.remove('on');talk.textContent='Tap to talk';try{rec&&rec.stop();}catch(e){}}
talk.onclick=()=>{if(listening)stopRec();else startRec(document.getElementById('hands').checked);};
document.getElementById('hands').onchange=e=>{stopRec();if(e.target.checked)startRec(true);};
document.getElementById('f').onsubmit=e=>{e.preventDefault();const q=document.getElementById('q');ask(q.value);q.value='';};
</script></body></html>"""

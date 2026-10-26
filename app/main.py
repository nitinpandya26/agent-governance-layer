import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.graph import build_graph
from agent.tools import CUSTOMERS
from app.api import router as api_router
from audit.logger import get_trace, list_escalations, list_runs, resolve_escalation, verify_chain

APP_DIR = Path(__file__).resolve().parent
DASHBOARD_DIST = APP_DIR / "static" / "dashboard"

app = FastAPI(title="Agent Governance Layer")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.include_router(api_router)

graph = build_graph()


@app.get("/dashboard")
@app.get("/dashboard/{_path:path}")
def dashboard_spa(_path: str = ""):
    """Serve the built React dashboard (dashboard/, built into
    app/static/dashboard/) for every /dashboard route - it's a
    client-side-routed single-page app (BrowserRouter, basename=/dashboard),
    so every path under here needs to resolve to the same index.html and
    let React Router take over from there."""
    index = DASHBOARD_DIST / "index.html"
    if not index.exists():
        raise RuntimeError(
            f"{index} not found - run `npm install && npm run build` in dashboard/ first."
        )
    return FileResponse(index)


@app.get("/")
def home(request: Request):
    runs = list_runs()
    return templates.TemplateResponse(
        request, "runs_list.html", {"runs": runs}
    )


@app.get("/requests/new")
def new_request_form(request: Request):
    return templates.TemplateResponse(
        request, "new_request.html", {"customers": CUSTOMERS}
    )


@app.post("/requests")
def submit_request(
    requester: str = Form(...),
    amount: float = Form(...),
    currency: str = Form("USD"),
    destination_country: str = Form(...),
    category: str = Form(...),
    memo: str = Form(""),
):
    customer = CUSTOMERS.get(requester, {})
    payload = {
        "requester": requester,
        "requester_name": customer.get("name", "unknown"),
        "amount": amount,
        "currency": currency,
        "destination_country": destination_country,
        "category": category,
        "memo": memo,
    }
    result = graph.invoke(
        {"request": payload, "run_id": "", "tool_results": {}, "decision": {}}
    )
    return RedirectResponse(url=f"/runs/{result['run_id']}", status_code=303)


@app.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    trace = get_trace(run_id)
    return templates.TemplateResponse(
        request, "run_detail.html", {"run_id": run_id, "trace": trace}
    )


@app.get("/escalations")
def escalations_list(request: Request):
    escalations = list_escalations()
    return templates.TemplateResponse(
        request, "escalations.html", {"escalations": escalations}
    )


@app.post("/escalations/{run_id}/resolve")
def escalations_resolve(run_id: str):
    resolve_escalation(run_id)
    return RedirectResponse(url="/escalations", status_code=303)


@app.get("/runs/{run_id}/verify")
def run_verify(request: Request, run_id: str):
    trace = get_trace(run_id)
    valid = verify_chain(run_id)
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {"run_id": run_id, "trace": trace, "verify_result": valid},
    )

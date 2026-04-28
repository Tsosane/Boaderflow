from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


def _humanize(value: object) -> str:
    if value is None:
        return "N/A"
    text = str(value).replace("_", " ").replace("-", " ")
    return " ".join(word.capitalize() for word in text.split())


def _format_dt(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["humanize"] = _humanize
templates.env.filters["dt"] = _format_dt


def render_template(request, template_name: str, context: dict | None = None):
    merged = {
        "request": request,
        "settings": request.app.state.settings,
        "site_code": request.app.state.settings.site_code,
        "site_name": request.app.state.settings.site_name,
        "current_user": getattr(request.state, "user", None),
        "message": request.query_params.get("message"),
        "error": request.query_params.get("error"),
    }
    if context:
        merged.update(context)
    return templates.TemplateResponse(request=request, name=template_name, context=merged)


def redirect_to(path: str, *, message: str | None = None, error: str | None = None, status_code: int = 303):
    params = {}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    destination = f"{path}?{urlencode(params)}" if params else path
    return RedirectResponse(destination, status_code=status_code)

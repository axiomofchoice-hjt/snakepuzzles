#!/usr/bin/env python3
"""Deterministically inject the optional AI Works event-tracking bridge."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend_html_pages import project_file, validate_html_pages


BRIDGE_PROTOCOL_VERSION = 1
BRIDGE_ENDPOINT_PATH = "/api/v1/event_tracking"
EVENT_TRACKING_ENDPOINT = "https://tracking.aiworks.site/api/v1/event_tracking"
TICKET_ENVIRONMENT_VARIABLE = "AIWORKS_EVENT_TRACKING_TICKET"
TICKET_PLACEHOLDER = "__AIWORKS_EVENT_TRACKING_TICKET__"
TICKET_ATTRIBUTE = "data-aiworks-event-tracking-ticket"
PARENT_ORIGIN_POLICY = "https-zhihu-domain"
BRIDGE_MAX_JSON_BYTES = 1024 * 1024
BRIDGE_MARKER = "data-aiworks-event-tracking-bridge"
BRIDGE_HASH_MARKER = "data-aiworks-event-tracking-sha256"
TICKET_MATERIALIZER_PATH = "_tmp/materialize-event-tracking-ticket.cjs"
TICKET_MATERIALIZATION_COMMAND = f"node {TICKET_MATERIALIZER_PATH}"
TRACKING_BUILD_SCRIPT = "build:track"
TRACKING_PACKAGE_MARKER = "aiworksEventTrackingBuild"
TRACKING_PACKAGE_MARKER_VERSION = 1

SKIP_DIRECTORIES = {
    ".git", ".hg", ".svn", "_tmp", "node_modules", "dist", "build", "out",
    ".next", ".nuxt", ".output", ".svelte-kit", "coverage", "docs", "test", "tests",
}
CSP_PATTERN = re.compile(
    r"content-security-policy|contentSecurityPolicy|content_security_policy|helmet\s*\.\s*contentSecurityPolicy",
    re.I,
)
MARKER_PATTERN = re.compile(
    rf"<script\b[^>]*\b{re.escape(BRIDGE_MARKER)}\s*=\s*([\"'])([^\"']+)\1",
    re.I,
)


def validate_endpoint(value: str | None) -> tuple[str | None, str]:
    if not value:
        return None, "event tracking endpoint is not configured"
    if any(character in value for character in "\r\n\x00"):
        return None, "event tracking endpoint contains control characters"
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None, "event tracking endpoint is not a valid absolute URL"
    if parsed.scheme != "https" or not parsed.hostname:
        return None, "event tracking endpoint must be an absolute HTTPS URL"
    if parsed.username is not None or parsed.password is not None:
        return None, "event tracking endpoint must not contain credentials"
    if parsed.query or parsed.fragment:
        return None, "event tracking endpoint must not contain query or fragment"
    if parsed.path != BRIDGE_ENDPOINT_PATH:
        return None, f"event tracking endpoint path must be {BRIDGE_ENDPOINT_PATH}"
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit(("https", netloc, BRIDGE_ENDPOINT_PATH, "", "")), "configured"


BRIDGE_SCRIPT = (
    "(()=>{try{const current=document.currentScript,ticket=current&&current.dataset.aiworksEventTrackingTicket,"
    "placeholder='__'+'AIWORKS_EVENT_TRACKING_TICKET'+'__';"
    "if(!ticket||ticket===placeholder)return;let sent=false;"
    "const send=data=>{if(sent)return false;let body;try{body=JSON.stringify({...data,deploy_uuid:ticket})}catch{return false}"
    f"if(new TextEncoder().encode(body).byteLength>{BRIDGE_MAX_JSON_BYTES})return false;sent=true;"
    f"fetch({json.dumps(EVENT_TRACKING_ENDPOINT, ensure_ascii=True, separators=(',', ':'))},"
    "{method:'POST',headers:{'content-type':'application/json'},body,credentials:'omit',"
    "referrerPolicy:'no-referrer',keepalive:true}).catch(()=>{});return true};"
    "if(self===top){const pageShow=()=>send({member_id:null,member_hash_id:null,client_id:null,"
    "element_type:'Page',log_type:'Show',view_url:location.href,is_iframe_show:0,"
    "client_timestamp:Date.now(),p_platform:'desktopweb'});"
    "if(document.readyState==='complete')queueMicrotask(pageShow);else addEventListener('load',pageShow,{once:true});return}"
    "const allowed=origin=>{try{const url=new URL(origin),host=url.hostname.toLowerCase();"
    "return url.protocol==='https:'&&(host==='zhihu.com'||host.endsWith('.zhihu.com'))}catch{return false}};"
    "const receive=event=>{if(sent||event.source!==parent||!allowed(event.origin))return;"
    "const data=event.data;if(!data||Array.isArray(data)||Object.prototype.toString.call(data)!=='[object Object]')return;"
    "if(send(data))removeEventListener('message',receive)};addEventListener('message',receive)}catch{}})();"
)


def bridge_script() -> str:
    return BRIDGE_SCRIPT


def script_sha256(script: str) -> str:
    digest = hashlib.sha256(script.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


BRIDGE_SCRIPT_SHA256 = "sha256-EoPGuFoq/s3r6h+3VAlMJ15toAPmybAFkhWE58QcZqI="
if script_sha256(BRIDGE_SCRIPT) != BRIDGE_SCRIPT_SHA256:
    raise RuntimeError("fixed event tracking bridge script does not match its golden SHA-256")


def html_snippet() -> str:
    script = bridge_script()
    return (
        f'<script {BRIDGE_MARKER}="{BRIDGE_PROTOCOL_VERSION}" '
        f'{BRIDGE_HASH_MARKER}="{BRIDGE_SCRIPT_SHA256}" {TICKET_ATTRIBUTE}="{TICKET_PLACEHOLDER}">{script}</script>'
    )


def jsx_snippet() -> str:
    script = bridge_script()
    literal = json.dumps(script, ensure_ascii=True)
    return (
        f'<script {BRIDGE_MARKER}="{BRIDGE_PROTOCOL_VERSION}" '
        f'{BRIDGE_HASH_MARKER}="{BRIDGE_SCRIPT_SHA256}" '
        f'{TICKET_ATTRIBUTE}="{TICKET_PLACEHOLDER}" '
        f'dangerouslySetInnerHTML={{{{__html:{literal}}}}} />'
    )


def ticket_materialization_source(contract: Any, build_command: str | None = None) -> str | None:
    if not isinstance(contract, dict) or contract.get("Status") != "injected":
        return None
    if (
        contract.get("TicketEnvironmentVariable") != TICKET_ENVIRONMENT_VARIABLE
        or contract.get("TicketPlaceholder") != TICKET_PLACEHOLDER
    ):
        raise ValueError("event tracking ticket materialization contract mismatch")
    targets = contract.get("TargetFiles", [contract.get("TargetFile")])
    if (not isinstance(targets, list) or not targets
            or any(not isinstance(target, str) or not target or Path(target).is_absolute()
                   or ".." in Path(target).parts or "\\" in target for target in targets)
            or len(set(targets)) != len(targets)
            or targets[0] != contract.get("TargetFile")):
        raise ValueError("event tracking ticket target is invalid")
    if build_command is not None and (
        not isinstance(build_command, str)
        or not build_command.strip()
        or any(character in build_command for character in "\r\n\x00")
    ):
        raise ValueError("frontend build command is invalid")
    source = (
        "'use strict';\n"
        "const fs = require('node:fs');\n"
        "const path = require('node:path');\n"
        "const childProcess = require('node:child_process');\n"
        "process.chdir(path.resolve(__dirname, '..'));\n"
        "const files = " + json.dumps(targets, ensure_ascii=True) + ";\n"
        "const token = " + json.dumps(TICKET_PLACEHOLDER, ensure_ascii=True) + ";\n"
        "const ticket = process.env." + TICKET_ENVIRONMENT_VARIABLE + ";\n"
        "console.log('[aiworks:event-tracking] AIWORKS_EVENT_TRACKING_TICKET=' + "
        "(ticket ? 'present' : 'missing'));\n"
        "if (ticket) {\n"
        "  if (!/^[A-Za-z0-9_-]{1,256}$/.test(ticket)) throw new Error('invalid event tracking ticket');\n"
        "  const updates = files.map(file => {\n"
        "  const stat = fs.lstatSync(file);\n"
        "  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('invalid event tracking target');\n"
        "  const text = fs.readFileSync(file, 'utf8');\n"
        "  const parts = text.split(token);\n"
        "  if (parts.length !== 2) throw new Error('event tracking ticket placeholder mismatch');\n"
        "  return { file, stat, parts };\n"
        "  });\n"
        "  for (const { file, stat, parts } of updates) {\n"
        "  const temporary = file + '.aiworks-ticket.' + process.pid + '.tmp';\n"
        "  try {\n"
        "    fs.writeFileSync(temporary, parts[0] + ticket + parts[1], "
        "{ encoding: 'utf8', mode: stat.mode, flag: 'wx' });\n"
        "    fs.renameSync(temporary, file);\n"
        "  } finally {\n"
        "    try { fs.unlinkSync(temporary); } catch (error) { if (error.code !== 'ENOENT') throw error; }\n"
        "  }\n"
        "  }\n"
        "}\n"
    )
    if build_command is not None:
        encoded_build = base64.b64encode(build_command.encode("utf-8")).decode("ascii")
        source += (
            "const build = Buffer.from(" + json.dumps(encoded_build) + ", 'base64').toString('utf8');\n"
            "const result = childProcess.spawnSync(build, { shell: true, stdio: 'inherit' });\n"
            "if (result.error) throw result.error;\n"
            "if (result.status !== 0) process.exit(result.status === null ? 1 : result.status);\n"
        )
    return source


def ticket_materialization_command(contract: Any, build_command: str | None = None) -> str | None:
    if ticket_materialization_source(contract, build_command) is None:
        return None
    return TICKET_MATERIALIZATION_COMMAND


def tracking_package_path(root: Path, frontend_component: dict[str, Any]) -> Path:
    directory = frontend_component.get("Directory")
    if (
        not isinstance(directory, str)
        or not directory
        or "\\" in directory
        or any(character in directory for character in "\r\n\x00")
        or Path(directory).is_absolute()
        or ".." in Path(directory).parts
    ):
        raise ValueError("frontend component directory is invalid for event tracking npm script")
    component_dir = root if directory == "." else root / directory
    component_package = component_dir / "package.json"
    if component_package.exists() or component_package.is_symlink():
        return component_package
    return root / "package.json"


def tracking_package_script(root: Path, package_path: Path) -> str:
    try:
        relative = os.path.relpath(root / TICKET_MATERIALIZER_PATH, package_path.parent)
    except ValueError as error:
        raise ValueError("cannot locate event tracking helper from frontend package") from error
    relative = Path(relative).as_posix()
    if any(character in relative for character in "\r\n\x00"):
        raise ValueError("event tracking helper path is invalid")
    return f"node {relative}"


def tracking_frontend_build_command(root: Path, frontend_component: dict[str, Any]) -> str:
    package_path = tracking_package_path(root, frontend_component)
    if package_path.parent == root:
        return f"npm run {TRACKING_BUILD_SCRIPT}"
    original = frontend_component.get("BuildCommand")
    if isinstance(original, str):
        workspace = re.search(r"(?:^|\s)--workspace(?:=|\s+)([A-Za-z0-9@._/-]+)(?:\s|$)", original)
        if workspace:
            return f"npm run {TRACKING_BUILD_SCRIPT} --workspace {workspace.group(1)}"
    directory = frontend_component.get("Directory")
    if (
        not isinstance(directory, str)
        or not directory
        or directory == "."
        or re.fullmatch(r"[A-Za-z0-9_./-]+", directory) is None
    ):
        raise ValueError("frontend package directory is invalid")
    return f"npm run {TRACKING_BUILD_SCRIPT} --prefix {directory}"


def tracking_package_conflict(root: Path, frontend_component: dict[str, Any]) -> tuple[str | None, list[str]]:
    try:
        package_path = tracking_package_path(root, frontend_component)
        expected_script = tracking_package_script(root, package_path)
        tracking_frontend_build_command(root, frontend_component)
        relative = _relative(package_path, root)
    except (OSError, ValueError):
        return "could not safely locate package.json for build:track", []
    if not package_path.exists():
        return None, []
    if package_path.is_symlink() or not package_path.is_file():
        return "package.json for build:track is not a regular file", [relative]
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "package.json for build:track is unreadable or invalid", [relative]
    if not isinstance(package, dict):
        return "package.json for build:track must contain an object", [relative]
    scripts = package.get("scripts")
    if scripts is not None and not isinstance(scripts, dict):
        return "package.json scripts prevents deterministic build:track injection", [relative]
    existing = scripts.get(TRACKING_BUILD_SCRIPT) if isinstance(scripts, dict) else None
    if existing is not None and existing != expected_script:
        return "package.json contains a conflicting build:track script", [relative]
    marker = package.get(TRACKING_PACKAGE_MARKER)
    if marker is not None and marker != TRACKING_PACKAGE_MARKER_VERSION:
        return "package.json contains a conflicting event tracking build marker", [relative]
    return None, []


def _read_text(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _csp_evidence(root: Path, component_dir: Path) -> list[str]:
    evidence: list[str] = []
    scopes = [root]
    if component_dir != root:
        scopes.append(component_dir)
    seen: set[Path] = set()
    for scope in scopes:
        for current, directories, files in os.walk(scope):
            directories[:] = [name for name in directories if name not in SKIP_DIRECTORIES]
            current_path = Path(current)
            for name in files:
                path = current_path / name
                if path in seen or path.is_symlink() or path.stat().st_size > 512 * 1024:
                    continue
                seen.add(path)
                if path.suffix.lower() not in {"", ".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml"}:
                    continue
                text = _read_text(path)
                if text is not None and CSP_PATTERN.search(text):
                    evidence.append(_relative(path, root))
    return sorted(set(evidence))


def _target(component_dir: Path, framework: str | None) -> tuple[Path | None, str | None, str]:
    framework = framework or ""
    if framework in {"next", "vinext"}:
        app_layouts = [
            component_dir / prefix / f"layout.{suffix}"
            for prefix in ("app", "src/app")
            for suffix in ("tsx", "jsx", "ts", "js")
        ]
        page_documents = [
            component_dir / prefix / f"_document.{suffix}"
            for prefix in ("pages", "src/pages")
            for suffix in ("tsx", "jsx", "ts", "js")
        ]
        existing_layouts = [path for path in app_layouts if path.is_file() and not path.is_symlink()]
        existing_documents = [path for path in page_documents if path.is_file() and not path.is_symlink()]
        if len(existing_layouts) == 1:
            return existing_layouts[0], "next-app-layout", "located Next App Router root layout"
        if not existing_layouts and len(existing_documents) == 1:
            return existing_documents[0], "next-pages-document", "located Next Pages Router document"
        return None, None, "could not uniquely locate a Next/vinext root layout or custom document"
    if framework == "sveltekit":
        path = component_dir / "src" / "app.html"
        return (path, "sveltekit-app-html", "located SvelteKit app template") if path.is_file() and not path.is_symlink() else (None, None, "could not locate src/app.html")
    if framework == "nuxt":
        candidates = [component_dir / "app.html", component_dir / "src" / "app.html"]
        existing = [path for path in candidates if path.is_file() and not path.is_symlink()]
        return (existing[0], "nuxt-app-html", "located Nuxt app template") if len(existing) == 1 else (None, None, "could not uniquely locate a Nuxt app.html template")
    path = component_dir / "index.html"
    if path.is_file() and not path.is_symlink():
        return path, "html-head", "located frontend index.html"
    return None, None, "could not locate a supported frontend source template"


def _inject_html(text: str, snippet: str) -> str | None:
    head = re.search(r"<head\b[^>]*>", text, re.I)
    if head:
        insertion = head.end()
        if (first_script := re.search(r"<script\b", text, re.I)) and first_script.start() < insertion:
            return None
        return text[:insertion] + "\n" + snippet + text[insertion:]
    html = re.search(r"<html\b[^>]*>", text, re.I)
    if html:
        insertion = html.end()
        return text[:insertion] + "\n<head>" + snippet + "</head>" + text[insertion:]
    doctype = re.match(r"\s*<!doctype\s+html\s*>", text, re.I)
    if doctype:
        insertion = doctype.end()
        return text[:insertion] + "\n" + snippet + text[insertion:]
    return snippet + "\n" + text


def _inject_next(text: str, snippet: str, adapter: str) -> str | None:
    if adapter == "next-pages-document":
        self_closing = re.search(r"<Head\s*/>", text)
        if self_closing:
            return text[:self_closing.start()] + "<Head>" + snippet + "</Head>" + text[self_closing.end():]
        head = re.search(r"<Head\b[^>]*>", text)
        if head:
            return text[:head.end()] + "\n" + snippet + text[head.end():]
        return None
    head = re.search(r"<head\b[^>]*>", text, re.I)
    if head:
        return text[:head.end()] + "\n" + snippet + text[head.end():]
    html = re.search(r"<html\b[^>]*>", text, re.I)
    if html:
        return text[:html.end()] + "\n<head>" + snippet + "</head>" + text[html.end():]
    return None


def _atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def event_tracking_bridge_contract(
    root: Path,
    frontend_component: dict[str, Any] | None,
    allow_injection: bool,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    base = {
        "Status": "not-applicable" if frontend_component is None else "skipped",
        "ProtocolVersion": BRIDGE_PROTOCOL_VERSION,
        "Endpoint": None,
        "TicketEnvironmentVariable": TICKET_ENVIRONMENT_VARIABLE,
        "TicketPlaceholder": TICKET_PLACEHOLDER,
        "ParentOriginPolicy": PARENT_ORIGIN_POLICY,
        "ScriptSha256": None,
        "Adapter": None,
        "TargetFile": None,
        "Reason": "project has no page-rendering component" if frontend_component is None else "event tracking bridge was not injected",
        "Evidence": [],
    }
    if frontend_component is None:
        return base
    endpoint, endpoint_reason = validate_endpoint(EVENT_TRACKING_ENDPOINT)
    if endpoint is None:
        raise ValueError(f"invalid built-in event tracking endpoint: {endpoint_reason}")
    base["Endpoint"] = endpoint
    base["ScriptSha256"] = BRIDGE_SCRIPT_SHA256
    if not allow_injection:
        base["Reason"] = "deploy plan is blocked before event tracking bridge injection"
        base["Evidence"] = ["deploy-plan findings"]
        return base
    directory_value = frontend_component.get("Directory")
    if not isinstance(directory_value, str):
        base["Reason"] = "frontend component directory is unresolved"
        return base
    component_dir = root if directory_value == "." else root / directory_value
    if frontend_component.get("HtmlPages"):
        try:
            pages = validate_html_pages(root, frontend_component["HtmlPages"])
        except (OSError, UnicodeError, ValueError) as error:
            base["Reason"] = str(error)
            return base
        # Preflight every page before editing any of them.
        children = []
        for page in pages:
            child = dict(frontend_component)
            child.pop("HtmlPages")
            child["ReviewedHtmlTarget"] = page["Path"]
            result = event_tracking_bridge_contract(root, child, allow_injection, dry_run=True)
            if result["Status"] != "injected":
                result["Evidence"] = sorted({page["Path"], *result["Evidence"]})
                return result
            children.append(child)
        if not dry_run:
            for child in children:
                event_tracking_bridge_contract(root, child, allow_injection)
        base.update({
            "Status": "injected", "Adapter": "backend-html",
            "TargetFile": pages[0]["Path"], "TargetFiles": [page["Path"] for page in pages],
            "Reason": "injected HTML pages linked by reviewed backend route evidence",
            "Evidence": sorted({f"{item['File']}:{item['Line']}" for page in pages for item in page["Evidence"]}),
        })
        return base
    if "ReviewedHtmlTarget" in frontend_component:
        target = project_file(root, frontend_component["ReviewedHtmlTarget"])
        adapter, target_reason = "backend-html", "located reviewed backend HTML source"
    else:
        target, adapter, target_reason = _target(component_dir, frontend_component.get("Framework"))
    if target is None or adapter is None:
        base["Reason"] = target_reason
        base["Evidence"] = [directory_value]
        return base
    relative_target = _relative(target, root)
    base["Adapter"] = adapter
    base["TargetFile"] = relative_target
    base["Evidence"] = [relative_target]
    if frontend_component.get("Unit") == "frontend":
        package_conflict, package_evidence = tracking_package_conflict(root, frontend_component)
        if package_conflict:
            base["Reason"] = package_conflict
            base["Evidence"] = package_evidence or [directory_value]
            return base
    csp = _csp_evidence(root, component_dir)
    if csp:
        base["Reason"] = "project CSP requires a framework-specific policy update, so best-effort injection was skipped"
        base["Evidence"] = csp
        return base
    text = _read_text(target)
    if text is None:
        base["Reason"] = "frontend source template is unreadable or too large"
        return base
    markers = MARKER_PATTERN.findall(text)
    expected_snippet = jsx_snippet() if adapter.startswith("next-") else html_snippet()
    if markers:
        if len(markers) == 1 and markers[0][1] == str(BRIDGE_PROTOCOL_VERSION) and expected_snippet in text:
            base["Status"] = "injected"
            base["Reason"] = "matching event tracking bridge is already present"
            return base
        base["Reason"] = "an unknown or conflicting event tracking bridge marker already exists"
        return base
    updated = _inject_next(text, expected_snippet, adapter) if adapter.startswith("next-") else _inject_html(text, expected_snippet)
    if updated is None:
        base["Reason"] = "could not place the event tracking bridge before application scripts"
        return base
    if not dry_run:
        _atomic_write(target, updated)
    base["Status"] = "injected"
    base["Reason"] = target_reason
    return base


def validate_event_tracking_bridge(root: Path | None, contract: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["deploy-plan.json: EventTrackingBridge must be an object"]
    status = contract.get("Status")
    if contract.get("ProtocolVersion") != BRIDGE_PROTOCOL_VERSION:
        errors.append("deploy-plan.json: EventTrackingBridge ProtocolVersion mismatch")
    if contract.get("TicketEnvironmentVariable") != TICKET_ENVIRONMENT_VARIABLE:
        errors.append("deploy-plan.json: EventTrackingBridge TicketEnvironmentVariable mismatch")
    if contract.get("TicketPlaceholder") != TICKET_PLACEHOLDER:
        errors.append("deploy-plan.json: EventTrackingBridge TicketPlaceholder mismatch")
    if contract.get("ParentOriginPolicy") != PARENT_ORIGIN_POLICY:
        errors.append("deploy-plan.json: EventTrackingBridge ParentOriginPolicy mismatch")
    if status != "injected":
        return errors
    endpoint, _ = validate_endpoint(contract.get("Endpoint"))
    if endpoint != EVENT_TRACKING_ENDPOINT or endpoint != contract.get("Endpoint"):
        errors.append("deploy-plan.json: injected EventTrackingBridge endpoint does not match the built-in endpoint")
        return errors
    if contract.get("ScriptSha256") != BRIDGE_SCRIPT_SHA256:
        errors.append("deploy-plan.json: EventTrackingBridge ScriptSha256 mismatch")
    if "TargetFiles" in contract:
        targets = contract["TargetFiles"]
        if (not isinstance(targets, list) or not targets
                or any(not isinstance(value, str) for value in targets)
                or len(set(targets)) != len(targets) or targets[0] != contract.get("TargetFile")):
            return errors + ["deploy-plan.json: EventTrackingBridge TargetFiles is invalid"]
        for target_value in targets:
            child = {key: value for key, value in contract.items() if key != "TargetFiles"}
            child["TargetFile"] = target_value
            errors.extend(validate_event_tracking_bridge(root, child))
        return errors
    if root is None:
        return errors
    target_value = contract.get("TargetFile")
    adapter = contract.get("Adapter")
    if not isinstance(target_value, str) or not target_value or Path(target_value).is_absolute() or ".." in Path(target_value).parts:
        errors.append("deploy-plan.json: injected EventTrackingBridge TargetFile is invalid")
        return errors
    try:
        target = project_file(root, target_value)
    except ValueError as error:
        return errors + [str(error)]
    text = _read_text(target)
    if text is None:
        errors.append("deploy-plan.json: injected EventTrackingBridge target is missing or unreadable")
        return errors
    expected = jsx_snippet() if isinstance(adapter, str) and adapter.startswith("next-") else html_snippet()
    materialized_pattern = re.escape(expected).replace(
        re.escape(TICKET_PLACEHOLDER), r"[A-Za-z0-9_-]{1,256}",
    )
    if text.count(expected) != 1 and len(re.findall(materialized_pattern, text)) != 1:
        errors.append("deploy-plan.json: injected EventTrackingBridge source does not match its deterministic contract")
    return errors

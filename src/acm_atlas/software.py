"""Validate and render supplemental upstream-code provenance, without running code."""

from datetime import date, datetime
import html
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


LICENSE_LABELS = {
    "license_text_verified": "已核对独立许可文本",
    "MIT_declared_in_setup_classifier_no_standalone_license_file_observed": "包元数据声明 MIT；未见独立许可文件",
    "GPL-2_declared_in_DESCRIPTION_no_standalone_license_file_observed": "DESCRIPTION 声明 GPL-2；未见独立许可文件",
    "no_standalone_license_file_or_metadata_license_identified_in_checked_root": "已查根目录未确认许可声明",
    "no_public_original_code_license_verified": "未核实公开原始代码许可",
}


def _public_url(value):
    """Require a credential-free public HTTPS URL; never turn local paths into links."""
    if not isinstance(value, str) or re.search(r"[\s<>\\\x00-\x1f]", value):
        raise ValueError("Software source needs a public HTTPS URL")
    u = urlsplit(value)
    host = (u.hostname or "").lower()
    if u.scheme != "https" or not host or u.username or u.password:
        raise ValueError("Software source needs a public HTTPS URL")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Software source URL must not reference a private host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z][a-z0-9-]*", host):
            raise ValueError("Software source URL must use a public host") from None
    else:
        if not address.is_global:
            raise ValueError("Software source URL must not reference a private address")
    return value


def _check_public_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"repo_url", "paper_url", "license_file_url", "license_metadata_url", "commit_url", "metadata_api", "repo_redirect_from"} and item is not None:
                _public_url(item)
            if key == "evidence_urls":
                for url in item:
                    _public_url(url)
            _check_public_values(item)
    elif isinstance(value, list):
        for item in value:
            _check_public_values(item)
    elif isinstance(value, str):
        if re.search(r"(?:^|[\s\"'=])/(?:Users|home|tmp|private|var)/|[A-Za-z]:\\", value):
            raise ValueError("Software catalogue must not contain private local paths")
        if re.search(r"(?:file|javascript|data|http)://", value, re.I):
            raise ValueError("Software catalogue contains an unsafe URL scheme")


def validate_software(data):
    """Reject unpinned public code, inflated run claims, unsafe links and licence conflation."""
    if data.get("scope") != "supplemental_software_provenance_not_method_statistics":
        raise ValueError("Software sources must remain supplemental to method statistics")
    date.fromisoformat(data["verified_on"])
    _check_public_values(data)
    entries = data["entries"]
    if not entries:
        raise ValueError("Software catalogue is empty")
    seen = set()
    for row in entries:
        key = row["code_id"]
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or key in seen:
            raise ValueError("Software code IDs must be unique and safe")
        seen.add(key)
        if row.get("run_status") != "not_run" or row.get("reproduction_claim") != "source_verified_only_not_reproduced":
            raise ValueError("Source audit cannot claim a reproduced upstream run")
        if not re.fullmatch(r"10\.\d{4,9}/\S+", row["source_doi"]):
            raise ValueError("Software source requires a DOI")
        if row["paper_url"] != "https://doi.org/" + row["source_doi"]:
            raise ValueError("Software paper URL must match its DOI")
        for field in ("name", "task", "inputs", "outputs", "platform_and_donor_limits", "evidence_urls"):
            if not row.get(field):
                raise ValueError("Software source needs task, data requirements and evidence")
        repo = row.get("repo_url")
        if repo:
            parsed = urlsplit(repo)
            if parsed.hostname != "github.com" or not re.fullmatch(r"/[^/]+/[^/]+", parsed.path):
                raise ValueError("Pinned source repository must be a GitHub owner/repository URL")
            if not re.fullmatch(r"[0-9a-f]{40}", row.get("observed_commit", "")):
                raise ValueError("Public software source requires a full pinned commit")
            if not row.get("default_branch"):
                raise ValueError("Public software source requires its observed branch")
            datetime.fromisoformat(row["commit_date"].replace("Z", "+00:00"))
        elif row.get("observed_commit") is not None or row.get("code_availability") != "available_on_request_as_stated_in_formal_article":
            raise ValueError("On-request source cannot claim a pinned public repository")
        status = row.get("license_status")
        if status not in LICENSE_LABELS:
            raise ValueError("Unknown software license verification level")
        if status == "license_text_verified" and not (row.get("license_file_url") and row.get("license_github_spdx")):
            raise ValueError("Verified license text requires a source file and identified license")
        if status in {
            "MIT_declared_in_setup_classifier_no_standalone_license_file_observed",
            "GPL-2_declared_in_DESCRIPTION_no_standalone_license_file_observed",
        } and not row.get("license_metadata_url"):
            raise ValueError("Metadata-only license declaration requires its package source")
    return True


def build_software(root: Path, out_dir: Path):
    """Write a static escaped page and its validated public JSON export."""
    data = json.loads((root / "data/software_sources.json").read_text(encoding="utf-8"))
    validate_software(data)
    out_dir.mkdir(parents=True, exist_ok=True)
    exports = out_dir / "exports"
    exports.mkdir(exist_ok=True)
    (exports / "software_sources.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    esc = lambda value: html.escape(str(value), quote=True)

    def link(url, label):
        return f'<a href="{esc(_public_url(url))}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'

    def items(values):
        return "<ul>" + "".join("<li>" + esc(value) + "</li>" for value in values) + "</ul>"

    cards = []
    for row in data["entries"]:
        links = [link(row["paper_url"], "原始论文")]
        if row.get("repo_url"):
            links += [link(row["repo_url"], "作者仓库"), link(row["commit_url"], "固定源码快照")]
            source = f'<p class="source">分支 {esc(row["default_branch"])} · 提交日期 {esc(row["commit_date"])}<br><code>{esc(row["observed_commit"])}</code></p>'
        else:
            source = '<p class="source">原文说明：代码需向作者索取；未核实公开原始分析仓库。</p>'
        if row.get("license_file_url"):
            links.append(link(row["license_file_url"], "许可文件"))
        if row.get("license_metadata_url"):
            links.append(link(row["license_metadata_url"], "包内许可声明"))
        references = " · ".join(link(url, "依据 " + str(index + 1)) for index, url in enumerate(row["evidence_urls"]))
        cards.append(
            f'<article id="{esc(row["code_id"])}"><h2>{esc(row["name"])} <span class="badge">NOT_RUN · 尚未运行</span></h2>'
            f'<p>{esc(row["task"])}</p><p>{" · ".join(links)}</p>{source}'
            f'<p class="license"><b>许可核对层级：</b>{esc(LICENSE_LABELS[row["license_status"]])}；声明：{esc(row.get("license_declared") or "未确认")}</p>'
            f'<div class="grid"><section><h3>所需输入</h3>{items(row["inputs"])}</section><section><h3>方法输出</h3>{items(row["outputs"])}</section></div>'
            f'<h3>环境与复现条件</h3>{items(row.get("environment_notes", []))}'
            f'<h3>数据与推断边界</h3>{items(row["platform_and_donor_limits"])}'
            f'<p class="source">来源核验日期 {esc(row["verification_date"])} · {references}</p></article>'
        )
    page = TEMPLATE.replace("__DATE__", esc(data["verified_on"])).replace("__COUNT__", str(len(data["entries"]))).replace("__CARDS__", "\n".join(cards))
    (out_dir / "software.html").write_text(page, encoding="utf-8")
    return data


TEMPLATE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACM Methods Atlas · 代码来源与复现条件</title><style>
:root{--ink:#243b4a;--blue:#154f68;--muted:#657c89;--line:#d8e4ea;--bg:#f3f7f9}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}header{background:#133f55;color:#fff;padding:35px max(24px,calc((100vw - 1120px)/2))}header a{color:#f4d79b}h1{font-size:32px;margin:8px 0}main{max-width:1160px;padding:24px 22px 60px;margin:auto}a{color:#086b91}h2{font-size:21px;color:var(--blue);margin:0 0 12px}h3{font-size:16px;margin:14px 0 5px}article{padding:24px;background:#fff;border:1px solid var(--line);border-radius:9px;margin:20px 0}.note{padding:16px 18px;background:#e9f2f6;border-left:4px solid #4c8ca2;margin:16px 0}.badge{display:inline-block;border:1px solid #d7c595;background:#fff8e6;color:#69511e;border-radius:12px;padding:2px 9px;font-size:12px;vertical-align:middle}.source{font-size:12px;color:var(--muted);overflow-wrap:anywhere}.license{background:#f4f7f9;padding:10px 14px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}ul{padding-left:22px;margin:6px 0}code{overflow-wrap:anywhere}footer{border-top:1px solid var(--line);padding-top:18px;font-size:13px;color:var(--muted)}@media(max-width:760px){.grid{grid-template-columns:1fr}h1{font-size:26px}article{padding:18px}header{padding:25px 22px}}
</style></head><body><header><small>ACM Methods Atlas · 来源核验 __DATE__</small><h1>代码来源与复现条件</h1><p>__COUNT__ 项来源条目：追溯官方源码、固定版本、许可依据与数据要求。</p><a href="index.html">方法目录</a> · <a href="research_paths.html">研究路径</a> · <a href="connection_audit.html">临床桥接审计</a></header><main>
<div class="note"><b>当前状态：来源已核验，__COUNT__ 项均未运行原方法。</b>源码固定提交不等于锁定环境或完成复现；包元数据许可声明与独立许可文本分别标注。目录内无第三方源码副本，来源数据和先验网络仍适用其各自使用条件。</div>
<div class="note"><b>补充资源口径：</b>本页不并入现有122项方法概念或25篇原始研究目录的统计分母。VIMA空间病例对照检验、通讯网络推断和原研究分析回答的问题不同，不据此进行统一优劣排名。</div>
<p><a href="./workflows/gse29819/index.html">另见：GSE29819原创供者层重分析与出图工作流</a>。该工作流为本项目独立重分析，不表示已复现本页的第三方方法。</p>
<p><a href="exports/software_sources.json" download>下载完整来源及运行状态 JSON</a></p>
__CARDS__
<footer>引用具体方法时请引用原论文和所用软件版本。本目录整理受本项目原创标注许可约束，第三方源码的许可保持独立。所有上游条目的运行状态为 NOT_RUN。</footer></main></body></html>'''

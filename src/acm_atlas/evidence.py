"""Descriptive audit of selected claims and their clinical bridge conditions."""

from collections import Counter
import csv
import html
import json
from pathlib import Path

AXES = {"temporal_basis": "时间依据", "spatial_basis": "空间依据", "perturbation_basis": "扰动/对照依据", "clinical_outcome_basis": "临床结局依据"}


def validate_evidence(data, catalog):
    study_ids = {s["study_id"] for s in catalog["studies"]}
    path_ids = {p["path_id"] for p in catalog["research_paths"]["paths"]}
    seen = set()
    for r in data["relations"]:
        if r["relation_id"] in seen:
            raise ValueError("Duplicate relationship ID")
        seen.add(r["relation_id"])
        if r["study_id"] not in study_ids or r["path_id"] not in path_ids:
            raise ValueError("Relationship references unknown study/path")
        if r["design_domain"] not in data["domain_labels_zh"]:
            raise ValueError("Unknown relationship design domain")
        if not r["source_url"].startswith("https://") or not r["source_locator"].strip() or not r["limits_zh"].strip():
            raise ValueError("Relationship needs a source, locator and inference boundary")
        for axis in AXES:
            if not r[axis].get("code") or not r[axis].get("description_zh"):
                raise ValueError("Relationship needs all four evidence axes")
        if r["human_review_status"] not in {"pending", "verified_with_public_review_record"}:
            raise ValueError("Unrecognized human verification status")
        if r["human_review_status"] == "verified_with_public_review_record" and not r.get("human_review_record"):
            raise ValueError("Human verification requires a review record")
    bridge_ids = [b["bridge_id"] for b in data["clinical_bridges"]]
    if len(bridge_ids) != len(set(bridge_ids)):
        raise ValueError("Duplicate clinical bridge ID")
    for b in data["clinical_bridges"]:
        if not set(b["source_study_ids"]) <= study_ids or b["path_id"] not in path_ids:
            raise ValueError("Clinical bridge references unknown evidence")
        if not b["required_conditions_zh"] or not b["scope_note_zh"] or not b["not_required_for_this_question_zh"]:
            raise ValueError("Clinical bridge needs applicable conditions and scope")
    return True


def summarize_evidence(data):
    relations = data["relations"]
    counts = Counter(r["design_domain"] for r in relations)
    return {"audit_date": data["audit_date"], "unit": "selected relationship assertions, not independent studies", "n_relations": len(relations), "n_studies": len({r["study_id"] for r in relations}), "n_predefined_bridges": len(data["clinical_bridges"]), "by_domain": [{"domain": d, "label_zh": label, "n_relations": counts[d], "n_distinct_studies": len({r["study_id"] for r in relations if r["design_domain"] == d})} for d, label in data["domain_labels_zh"].items()], "human_dual_review_status": data["human_dual_review_status"], "scope_zh": data["scope_zh"]}


def build_evidence(catalog, root, out_dir):
    data = catalog["connection_evidence"]
    stats = summarize_evidence(data)
    e = lambda x: html.escape(str(x), quote=True)
    studies = {s["study_id"]: s for s in catalog["studies"]}
    exports = out_dir / "exports"
    for name, value in (("connection_evidence.json", data), ("connection_summary.json", stats)):
        (exports / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    rows = []
    for r in data["relations"]:
        rows.append({k:r[k] for k in ("relation_id", "study_id", "path_id", "statement_zh", "design_domain", "source_locator", "source_url", "limits_zh", "human_review_status")})
        for axis in AXES:
            rows[-1][axis] = r[axis]["code"]+": "+r[axis]["description_zh"]
    with (exports / "connection_evidence.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k:"'"+v if str(v).startswith(("=", "+", "-", "@")) else v for k,v in row.items()})
    (exports / "human_connection_review_template.csv").write_bytes((root / "data/human_connection_review_template.csv").read_bytes())
    counts = "".join(f'<tr><td>{e(r["label_zh"])}</td><td>{r["n_relations"]}</td><td>{r["n_distinct_studies"]}</td></tr>' for r in stats["by_domain"])
    markdown = ["# ACM证据条件审计：先导结果", "", data["scope_zh"], "", f'选定断言{stats["n_relations"]}条，涉及{stats["n_studies"]}篇文章；预先定义临床桥接问题{stats["n_predefined_bridges"]}个。两位人类独立复核：待完成。', "", "| 断言主设计域 | 断言数 | 不同文章数 |", "|---|---:|---:|"]
    markdown += [f'| {r["label_zh"]} | {r["n_relations"]} | {r["n_distinct_studies"]} |' for r in stats["by_domain"]]
    markdown += ["", "同一篇论文可贡献多个断言或系统，文章数不跨域相加；人体真实时间观察包含回顾登记和病例，不等于前瞻对照试验。", "", "## 临床桥接的条件", ""]
    bridges = []
    for b in data["clinical_bridges"]:
        relation_links = " · ".join(f'<a href="#{e(r["relation_id"])}">{e(r["relation_id"])}</a>' for r in data["relations"] if r["study_id"] in b["source_study_ids"])
        bridges.append(f'<article class="bridge"><h3>{e(b["bridge_id"])} · {e(b["question_zh"])}</h3><p><b>要回答它需要：</b>'+"；".join(e(x) for x in b["required_conditions_zh"])+f'</p><p><b>已有片段：</b>{e(b["current_fragments_zh"])}</p><p><b>尚缺对齐：</b>{e(b["missing_alignment_zh"])}</p><p class="note">该问题的适用条件：{e(b["not_required_for_this_question_zh"])}</p><p class="note">范围：{e(b["scope_note_zh"])}</p><p class="refs">追溯研究内断言：{relation_links}</p></article>')
        markdown += [f'### {b["bridge_id"]} {b["question_zh"]}', "", '- 需要：'+"；".join(b["required_conditions_zh"]), '- 已有片段：'+b["current_fragments_zh"], '- 尚缺对齐：'+b["missing_alignment_zh"], '- 适用条件：'+b["not_required_for_this_question_zh"], '- 范围：'+b["scope_note_zh"], ""]
    cards = []
    markdown += ["## 研究内部的具体断言", ""]
    for r in data["relations"]:
        axes = "".join(f'<dt>{label}</dt><dd>{e(r[key]["description_zh"])}</dd>' for key,label in AXES.items())
        cards.append(f'<details class="relation" id="{e(r["relation_id"])}" data-domain="{e(r["design_domain"])}"><summary><span class="badge">{e(r["relation_id"])}</span> {e(r["statement_zh"])}</summary><p class="note">{e(data["domain_labels_zh"][r["design_domain"]])} · {e(studies[r["study_id"]]["title"])}</p><dl>{axes}</dl><p><b>推断边界：</b>{e(r["limits_zh"])}</p><p class="note">原文定位：{e(r["source_locator"])} · 人工复核待完成</p><p><a href="{e(r["source_url"])}" target="_blank" rel="noopener">原始来源</a> · <a href="research_paths.html#{e(r["path_id"])}-evidence-{e(r["study_id"])}">回到研究路径</a></p></details>')
        markdown += [f'### {r["relation_id"]} · {r["study_id"]}', "", r["statement_zh"], "", f'主设计域：{data["domain_labels_zh"][r["design_domain"]]}', ""]
        markdown += [f'- {label}：{r[key]["description_zh"]}' for key,label in AXES.items()]
        markdown += ['- 边界：'+r["limits_zh"], f'- 来源：[{r["source_locator"]}]({r["source_url"]})', ""]
    opts = "".join(f'<option value="{e(key)}">{e(label)}</option>' for key,label in data["domain_labels_zh"].items())
    search_md = build_search_summary(root, out_dir)
    page = TEMPLATE.replace("__SCOPE__", e(data["scope_zh"])).replace("__COUNTS__", counts).replace("__BRIDGES__", "".join(bridges)).replace("__CARDS__", "".join(cards)).replace("__OPTIONS__", opts).replace("__N_REL__", str(stats["n_relations"])).replace("__N_STUDY__", str(stats["n_studies"])).replace("__N_BRIDGE__", str(stats["n_predefined_bridges"]))
    (out_dir / "connection_audit.html").write_text(page, encoding="utf-8")
    (out_dir / "connection_audit.md").write_text("\n".join(markdown), encoding="utf-8")
    (out_dir / "search_update.md").write_text(search_md, encoding="utf-8")


def build_search_summary(root, out_dir):
    pointer = json.loads((root / "searches/current_run.json").read_text())
    folder = pointer["directory"]
    if Path(folder).name != folder:
        raise ValueError("Search snapshot must be a direct child directory")
    run_dir = root / "searches" / folder
    run = json.loads((run_dir / "search_run.json").read_text())
    (out_dir / "exports/search_run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (out_dir / "exports/search_candidates.csv").write_bytes((run_dir / "candidates.csv").read_bytes())
    lines = ["# 检索可行性更新：候选尚未筛选", "", "这是现有定向文献库的方法升级与召回校准，不是完成的范围综述。PubMed与Europe PMC有大量重叠，不当作独立数据库或独立研究。", "", f'当前目录：`{folder}`；检索开始UTC：{run["search_started_utc"]}。', "", "| 平台 | 状态 | 命中数 | 取回元数据 | 截断 |", "|---|---|---:|---:|---|"]
    for name, item in run["platforms"].items():
        lines.append(f'| {name} | {item["status"]} | {item.get("count", "未知")} | {item.get("retrieved_metadata", 0)} | {item.get("truncated", "未知")} |')
    lines += ["", f'取回来源记录{run["retrieved_source_records"]}条，以DOI/PMID标识去重后候选{run["deduplicated_candidate_records"]}条。所有记录均为待筛选；这不是纳入数，不改变23篇先导分母。', "", '已知条目校准：'+pointer["main_pilot_known_item_retrieval"]+'（默认先导研究）；'+pointer["catalogue_known_item_retrieval"]+'（全部目录）。已知条目召回不能估计未知遗漏。', "", "初版遗漏了7个已知条目，DOI核查后扩展同义词和相关概念；原始运行完整保留。尚需补充机构数据库、引文追踪和人类独立筛选/复核。", "", "[候选CSV](exports/search_candidates.csv) · [完整检索日志JSON](exports/search_run.json) · [方案草案](https://github.com/Zero-soda/acm-methods-atlas/blob/main/protocol/scoping_protocol.md) · [两版原始快照](https://github.com/Zero-soda/acm-methods-atlas/tree/main/searches)", ""]
    return "\n".join(lines)


TEMPLATE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACM证据条件审计 · 先导结果</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f6f8;color:#243d4a;font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}header{padding:30px max(24px,calc((100vw - 1160px)/2));background:#173f54;color:white}header a{color:#f5d69a}h1{font-size:30px}main{max-width:1200px;margin:auto;padding:25px 22px 60px}a{color:#086988}.scope{padding:15px 20px;background:#e6eff3;border-left:4px solid #4b8ba2}.note{font-size:13px;color:#5a7482}.metrics{display:flex;gap:15px;flex-wrap:wrap;margin:20px 0}.metric{background:white;border:1px solid #d6e1e6;padding:14px 22px;flex:1;min-width:180px}.metric b{display:block;font-size:27px;color:#17526c}table{width:100%;border-collapse:collapse;background:white}th,td{padding:10px 15px;border:1px solid #d6e1e6;text-align:left}th{background:#e6eff3}.bridge{background:#fffaf0;border:1px solid #e5d3ab;border-left:4px solid #b58c35;padding:15px 21px;margin:15px 0}.bridge h3{margin:0 0 10px;font-size:17px}.refs{font-size:12px}.relation{background:white;border:1px solid #d6e1e6;border-radius:6px;padding:14px 19px;margin:12px 0;scroll-margin-top:20px}.relation[hidden]{display:none}summary{font-weight:600;cursor:pointer}.badge{font-size:12px;background:#e5eff3;padding:3px 7px;white-space:nowrap}dt{font-weight:600;margin-top:10px}dd{margin:2px 0 8px}select{font:inherit;padding:10px;margin:10px 0;border:1px solid #9eb9c6;background:#fff}h2{margin-top:30px}footer{border-top:1px solid #d6e1e6;margin-top:25px;padding-top:18px;font-size:12px;color:#5a7482}a:focus-visible,summary:focus-visible,select:focus-visible{outline:3px solid #b58c35;outline-offset:4px}
</style></head><body><header><small>ACM Methods Atlas · 方法升级</small><h1>每条研究连接，究竟由什么证据支持？</h1><p>把研究内部可观察的关系与临床桥接所需条件分开，逐条记录时间、空间、扰动和临床结局。</p><a href="research_paths.html">研究路径</a> · <a href="index.html">方法目录</a> · <a href="search_update.md">检索更新与方案</a></header><main><div class="scope">__SCOPE__<br><b>人工双人复核待完成；当前为先导审计，未完成范围综述。</b></div><div class="metrics"><div class="metric"><b>__N_REL__</b>选定研究内断言</div><div class="metric"><b>__N_STUDY__</b>不同文章</div><div class="metric"><b>__N_BRIDGE__</b>预先定义的临床桥接问题</div></div><h2>按断言的主设计域描述</h2><table><thead><tr><th>设计域</th><th>断言数</th><th>不同文章数</th></tr></thead><tbody>__COUNTS__</tbody></table><p class="note">这是29条选定断言的构成；每篇可有多个系统或断言，文章数不跨域相加。人体真实时间观察含回顾登记、影像重复及病例，不等于前瞻随机试验。标签不是质量总分。</p><h2>临床桥接：缺的是哪一种对齐？</h2><p>不同问题需要不同条件：预后问题不以随机治疗为必要条件，跨模态对应问题也不必强求未来事件。当前库未检出直接验证，只描述本次审读范围。</p>__BRIDGES__<h2>逐条查看研究内部关系</h2><label for="domain">断言主设计域：</label><select id="domain"><option value="">全部设计域</option>__OPTIONS__</select><p id="shown" class="note"></p>__CARDS__<h2>下载与接续人工复核</h2><p><a href="exports/connection_evidence.csv">断言审计CSV</a> · <a href="exports/connection_evidence.json">结构化JSON</a> · <a href="exports/human_connection_review_template.csv">人工复核空表</a> · <a href="connection_audit.md">完整文字版</a></p><p><a href="exports/search_candidates.csv">待筛选检索候选CSV</a> · <a href="search_update.md">检索日志说明</a> · <a href="https://github.com/Zero-soda/acm-methods-atlas/blob/main/protocol/scoping_protocol.md">范围综述方案草案</a></p><footer>源文件、候选和正式纳入是不同层次。当前标签由AI辅助整理并经定向来源检查，人工复核未完成；不宣称临床有效性、穷尽检索、正式偏倚评价或领域缺失率。原创归纳CC BY 4.0，代码MIT；原论文仍按自身许可。</footer></main><script>
const filter=document.getElementById('domain'),cards=[...document.querySelectorAll('.relation')];function render(){let n=0;for(const c of cards){c.hidden=!!filter.value&&c.dataset.domain!==filter.value;if(!c.hidden)n++;}document.getElementById('shown').textContent='显示 '+n+' 条选定断言；上方统计固定为完整先导审计。';}filter.addEventListener('change',render);function anchor(){const id=decodeURIComponent(location.hash.slice(1)),el=document.getElementById(id);if(el&&el.classList.contains('relation')){filter.value='';render();el.open=true;el.scrollIntoView({block:'start'});}}addEventListener('hashchange',anchor);render();anchor();
</script></body></html>'''

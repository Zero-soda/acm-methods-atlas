"""Evidence-linked research paths, distinct from disease or citation chronology."""

import html
import json


RELATION_TYPES = {"research_synthesis", "parallel_evidence", "proposed_bridge"}


def validate_paths(data, studies):
    study_ids = {s["study_id"] for s in studies}
    nodes = data["study_summaries"]
    node_ids = [n["study_id"] for n in nodes]
    if len(node_ids) != len(set(node_ids)) or not set(node_ids) <= study_ids:
        raise ValueError("Duplicate or unknown pathway study")
    for node in nodes:
        for field in ("short_label_zh", "question_zh", "approach_zh", "finding_zh", "unresolved_zh", "source_locator"):
            if not node.get(field, "").strip():
                raise ValueError("Pathway study needs a finding, boundary and source locator")
        if not node["source_url"].startswith("https://"):
            raise ValueError("Pathway source must have an HTTPS URL")
    path_ids = [p["path_id"] for p in data["paths"]]
    if len(path_ids) != len(set(path_ids)):
        raise ValueError("Duplicate pathway ID")
    for path in data["paths"]:
        stages = path["stages"]
        stage_ids = [s["stage_id"] for s in stages]
        if len(stage_ids) != len(set(stage_ids)) or len(stages) < 2:
            raise ValueError("Pathway requires unique stages")
        for stage in stages:
            if not stage["study_ids"] or not set(stage["study_ids"]) <= set(node_ids):
                raise ValueError("Pathway stage references unknown evidence")
        for edge in path["connections"]:
            if edge["from_stage"] not in stage_ids or edge["to_stage"] not in stage_ids:
                raise ValueError("Pathway connection references unknown stage")
            if edge["relation_type"] not in RELATION_TYPES:
                raise ValueError("Unsupported pathway relation; causal/citation links are not inferred")
            if not edge.get("boundary_zh", "").strip():
                raise ValueError("Cross-study connections require an interpretation boundary")
        for field in ("question_zh", "design_zh", "measurements_zh", "outcomes_zh", "falsification_zh"):
            if not path["next_study"].get(field, "").strip():
                raise ValueError("Proposed bridge needs a testable design and falsification condition")
    for pair in data.get("cross_paper_tensions", []):
        if pair["paper_a"] not in node_ids or pair["paper_b"] not in node_ids:
            raise ValueError("Cross-paper comparison references unknown study")
    return True


def build_pathways(catalog, out_dir):
    data = catalog["research_paths"]
    studies = {s["study_id"]: s for s in catalog["studies"]}
    nodes = {n["study_id"]: n for n in data["study_summaries"]}
    e = lambda value: html.escape(str(value), quote=True)
    labels = {"research_synthesis": "跨研究整合", "parallel_evidence": "并行证据互补", "proposed_bridge": "待验证桥接"}

    def study_link(sid):
        return f'<a href="#evidence-{e(sid)}">{e(nodes[sid]["short_label_zh"])} · {studies[sid]["year"]}</a>'

    panels = []
    markdown = ["# ACM 研究路径：从问题到下一步证据", "", data["scope_note_zh"], "", data["central_question_zh"], ""]
    next_labels = {"question_zh": "要检验的问题", "design_zh": "研究设计", "measurements_zh": "关键测量", "outcomes_zh": "分别评价的结局", "falsification_zh": "什么结果会削弱这条解释", "public_data_now_zh": "公开数据现在能做到哪一步"}
    for i, path in enumerate(data["paths"]):
        stages = {s["stage_id"]: s for s in path["stages"]}
        cards = []
        markdown += [f'## {i + 1}. {path["title_zh"]}', "", f'临床问题：{path["clinical_question_zh"]}', "", path["synthesis_zh"], ""]
        for j, stage in enumerate(path["stages"]):
            cards.append(f'<article class="stage"><span class="step">{j+1:02}</span><h3>{e(stage["title_zh"])}</h3><p>{e(stage["contribution_zh"])}</p><p class="links">'+"<br>".join(study_link(sid) for sid in stage["study_ids"])+f'</p><p class="gap"><b>留下的问题</b><br>{e(stage["open_question_zh"])}</p></article>')
            refs = "；".join(f'[{nodes[sid]["short_label_zh"]}]({nodes[sid]["source_url"]})' for sid in stage["study_ids"])
            markdown += [f'### {j+1}. {stage["title_zh"]}', "", stage["contribution_zh"], "", f'证据：{refs}', "", f'留下的问题：{stage["open_question_zh"]}', ""]
        edges = []
        markdown += ["### 步骤之间如何连接", ""]
        for edge in path["connections"]:
            label = labels[edge["relation_type"]]
            start, end = stages[edge["from_stage"]]["title_zh"], stages[edge["to_stage"]]["title_zh"]
            edges.append(f'<li class="edge {e(edge["relation_type"])}"><span class="tag">{label}</span><b>{e(start)} → {e(end)}</b><p>{e(edge["rationale_zh"])}</p><p class="boundary">连接边界：{e(edge["boundary_zh"])}</p></li>')
            markdown += [f'- **{label}：{start} → {end}**。{edge["rationale_zh"]} 边界：{edge["boundary_zh"]}', ""]
        proposal = "".join(f'<dt>{label}</dt><dd>{e(path["next_study"][key])}</dd>' for key, label in next_labels.items())
        markdown += ["### 下一项值得做的研究（提议，尚未执行）", ""]
        markdown += [f'- **{label}**：{path["next_study"][key]}' for key, label in next_labels.items()]
        markdown += ["", "### 逐篇研究卡片", ""]
        evidence = []
        for sid in dict.fromkeys(sid for s in path["stages"] for sid in s["study_ids"]):
            n, s = nodes[sid], studies[sid]
            fields = [("原始问题", "question_zh"), ("采用的路径", "approach_zh"), ("研究内发现", "finding_zh"), ("仍未回答", "unresolved_zh")]
            # IDs include the path because one study can contribute to multiple paths.
            details = "".join(f'<dt>{label}</dt><dd>{e(n[key])}</dd>' for label, key in fields)
            evidence.append(f'<details id="{e(path["path_id"])}-evidence-{e(sid)}"><summary>{e(n["short_label_zh"])} · {s["year"]}<small>{e(s["title"])}</small></summary><p class="source">研究系统：{e(" / ".join(s["systems"]))}<br>审读范围：{e(s["reading_depth"])}</p><dl>{details}</dl><p class="source">定位：{e(n["source_locator"])}</p><p><a href="{e(n["source_url"])}" target="_blank" rel="noopener">核对原始来源</a> · <a href="index.html?study={e(sid)}#catalogue">查看方法标注</a></p></details>')
            markdown += [f'#### [{n["short_label_zh"]}]({n["source_url"]}) · {s["year"]}', ""]
            markdown += [f'- **{label}**：{n[key]}' for label, key in fields]
            markdown += [f'- **原文定位**：{n["source_locator"]}', ""]
        # Stage links open the relevant evidence card in their own panel.
        flow = "".join(cards).replace('href="#evidence-', f'href="#{e(path["path_id"])}-evidence-')
        panels.append(f'<section class="path-panel" id="path-{e(path["path_id"])}" aria-labelledby="tab-{e(path["path_id"])}"'+(' hidden' if i else '')+f'><h2>{e(path["title_zh"])}</h2><p class="clinical"><b>临床问题：</b>{e(path["clinical_question_zh"])}</p><p>{e(path["synthesis_zh"])}</p><h3>研究如何推进问题</h3><div class="flow">{flow}</div><h3>连接的依据与边界</h3><ul class="edges">'+"".join(edges)+f'</ul><aside class="proposal"><h3>下一项值得做的研究 <small>提议，尚未执行</small></h3><dl>{proposal}</dl></aside><h3>逐篇追溯：问题 → 方法 → 发现 → 未解问题</h3>'+"".join(evidence)+'</section>')
    buttons = "".join(f'<button id="tab-{e(p["path_id"])}" aria-controls="path-{e(p["path_id"])}" aria-pressed="'+('true' if i == 0 else 'false')+f'" data-path="{e(p["path_id"])}">{e(p["short_title_zh"])}</button>' for i, p in enumerate(data["paths"]))
    tensions = []
    markdown += ["## 跨研究差异：需要解释，不能硬拼", "", "以下是定向比较的两组候选关系，不是全库两两矛盾检测；解释尚待研究者确认。", ""]
    for pair in data.get("cross_paper_tensions", []):
        refs = " · ".join(f'<a href="{e(nodes[sid]["source_url"])}">{e(nodes[sid]["short_label_zh"])}</a>' for sid in (pair["paper_a"], pair["paper_b"]))
        tensions.append(f'<article class="clinical"><h3>{e(pair["overlap_topic"])}</h3><p>{e(pair["a_finding"])} {e(pair["b_finding"])}</p><p>{e(pair["interpretation_zh"])}</p><p class="source">{refs} · 研究者确认待完成</p></article>')
        markdown += [f'### {pair["overlap_topic"]}', "", f'{pair["paper_a"]}：{pair["a_finding"]}', "", f'{pair["paper_b"]}：{pair["b_finding"]}', "", pair["interpretation_zh"], "", '研究者确认：待完成。', ""]
    comparisons = '<h2>跨研究差异：需要解释，不能硬拼</h2><p class="scope">这里只定向比较两组候选关系，不是全库两两矛盾检测；解释尚待研究者确认。</p>'+"".join(tensions)
    page = TEMPLATE.replace("__BUTTONS__", buttons).replace("__PANELS__", "".join(panels)+comparisons).replace("__SCOPE__", e(data["scope_note_zh"])).replace("__CENTRAL__", e(data["central_question_zh"]))
    (out_dir / "research_paths.html").write_text(page, encoding="utf-8")
    (out_dir / "research_paths.md").write_text("\n".join(markdown), encoding="utf-8")
    (out_dir / "exports" / "research_paths.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


TEMPLATE = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ACM 研究路径 · 问题如何推进</title><style>
:root{--ink:#223c4a;--muted:#56707d;--line:#d6e1e6;--blue:#124b64;--bg:#f4f7f8;--gold:#a96f13}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}header{background:#143f54;color:white;padding:32px max(24px,calc((100vw - 1240px)/2))}h1{font-size:32px;margin:8px 0}header p{max-width:1000px;color:#dce9ee}a{color:#096b8b}header a{color:#f2d28f}main{max-width:1290px;margin:auto;padding:25px}h2{font-size:25px}h3{font-size:18px}p{margin:10px 0}.intro,.clinical{border-left:4px solid #5791a5;background:#e8f1f5;padding:14px 18px}.scope{font-size:13px;color:var(--muted)}nav{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}button{font:inherit;border:1px solid #a8bec9;background:#fff;padding:11px 18px;border-radius:7px;color:var(--blue);cursor:pointer}button[aria-pressed="true"]{background:var(--blue);color:white}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #bb7d16;outline-offset:4px}.flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.stage{border:1px solid var(--line);border-top:4px solid #48869d;background:#fff;border-radius:6px;padding:16px}.stage h3{margin:5px 0 10px}.step{font:600 25px/1.2 monospace;color:#81a6b6}.links{font-size:13px}.gap{border-top:1px solid var(--line);padding-top:12px;font-size:13px;color:var(--muted)}.edges{list-style:none;padding:0}.edge{padding:14px 18px;background:white;margin:12px 0;border-left:4px solid #7f9ca9}.edge.proposed_bridge{border:1px dashed #ba871f;border-left:4px solid #ba871f}.tag{display:inline-block;font-size:12px;background:#e7eff3;color:#245268;border-radius:4px;padding:2px 8px;margin-right:10px}.proposed_bridge .tag{background:#fcf0d8;color:#8c5d10}.boundary,.source{font-size:13px;color:var(--muted)}.proposal{background:#fff8e9;border:1px solid #e3cc9f;border-radius:7px;padding:8px 22px 18px;margin:24px 0}dt{font-weight:600;margin-top:12px}dd{margin:2px 0 10px}small{font-weight:400;font-size:12px;color:var(--muted)}details{background:white;border:1px solid var(--line);border-radius:6px;margin:12px 0;padding:14px 18px;scroll-margin-top:20px}summary{cursor:pointer;font-weight:600}summary small{display:block;margin-top:3px}.path-panel[hidden]{display:none}.downloads{margin-top:35px;border-top:1px solid var(--line);padding-top:20px}.downloads a{display:inline-block;margin-right:20px}footer{font-size:12px;color:var(--muted);margin-top:20px}@media(max-width:1000px){.flow{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.flow{grid-template-columns:1fr}main{padding:18px}h1{font-size:25px}nav button{width:100%;text-align:left}}
</style></head><body><header><small style="color:#d6e6ed">ACM Methods Atlas · 研究路径</small><h1>把论文串成问题推进的路径</h1><p>每一步连接已有发现、能回答问题的方法、尚缺的证据与下一项临床研究。</p><a href="connection_audit.html">证据条件审计</a> · <a href="index.html">方法目录与统计</a> · <a href="https://github.com/Zero-soda/acm-methods-atlas">GitHub 开源项目</a></header><main><div class="intro"><b>共同问题：</b>__CENTRAL__</div><p class="scope">__SCOPE__</p><nav aria-label="选择研究路径">__BUTTONS__</nav>__PANELS__<div class="downloads"><a href="exports/research_paths.json">下载结构化路径 JSON</a><a href="research_paths.md">阅读完整文字版</a><a href="index.html">查询方法标注</a></div><footer>研究内发现来自所列原始文献；跨研究联系与下一步设计是本项目的整合和提议。未声称已核实作者引用承接关系。阶段编号表示问题组织顺序，不代表所有ACM患者的病程，也不代表证据质量评分。AI辅助整理，欢迎附原始出处纠错。</footer></main><script>
const buttons=[...document.querySelectorAll('[data-path]')];function showPath(id){for(const b of buttons){const selected=b.dataset.path===id;b.setAttribute('aria-pressed',String(selected));document.getElementById('path-'+b.dataset.path).hidden=!selected;}}for(const b of buttons)b.addEventListener('click',()=>showPath(b.dataset.path));function openEvidence(){const id=decodeURIComponent(location.hash.slice(1));const el=document.getElementById(id);if(el&&el.tagName==='DETAILS'){const panel=el.closest('.path-panel');if(panel)showPath(panel.id.slice(5));el.open=true;el.scrollIntoView({block:'start'});}}addEventListener('hashchange',openEvidence);openEvidence();
</script></body></html>'''

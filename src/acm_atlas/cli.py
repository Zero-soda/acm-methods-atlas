"""Generate a static, searchable catalogue and machine-readable exports."""

import argparse
import csv
import html
import json
from pathlib import Path

from .catalog import COHORTS, load_catalog, summarize
from .pathways import build_pathways
from .evidence import build_evidence
from .software import build_software, validate_software

FAMILY_LABELS = {"design": "研究设计", "measurement": "测量技术", "computational": "计算与统计", "intervention": "受控扰动"}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path, rows, fields):
    def cell(value):
        if isinstance(value, list):
            value = " | ".join(map(str, value))
        value = str(value)
        return "'" + value if value.startswith(("=", "+", "-", "@")) else value
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: cell(row.get(key, "")) for key in fields})


def build(root, out_dir, cohort):
    catalog = load_catalog(root / "data")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    exports = out_dir / "exports"
    exports.mkdir(exist_ok=True)
    summaries = {name: summarize(catalog, name) for name in COHORTS}
    stats = summaries[cohort]
    write_json(out_dir / "summary.json", stats)
    write_json(exports / "all_cohort_summaries.json", summaries)
    for name in ("studies", "methods", "method_annotations", "context_sources"):
        write_json(exports / f"{name}.json", catalog[name])
    write_csv(out_dir / "method_summary.csv", stats["by_method"],
              ["id", "label", "family", "group_id", "n_studies", "denominator", "percent", "study_ids"])
    write_csv(out_dir / "computational_methods.csv", [r for r in stats["by_method"] if r["family"] == "computational"],
              ["id", "label", "n_studies", "denominator", "percent", "study_ids"])
    write_csv(out_dir / "method_groups.csv", stats["by_group"], ["id", "n_studies", "denominator", "percent", "study_ids"])
    write_csv(out_dir / "method_cooccurrence.csv", stats["cooccurrence"], ["method_a", "method_b", "n_studies"])
    write_csv(exports / "studies.csv", catalog["studies"],
              ["study_id", "title", "doi", "url", "year", "publication_status", "in_manuscript", "systems", "reading_depth", "clinical_question_ids", "independence_note"])
    write_csv(exports / "method_annotations.csv", catalog["method_annotations"],
              ["study_id", "method_id", "annotation_status", "data_origin", "evidence_basis", "source_locator", "source_url"])
    top = [r for r in stats["by_method"] if r["family"] == "computational"][:12]
    md = ["# 方法标注统计快照", "", f"默认队列：`{cohort}`；分母 **{stats['denominator']} 篇**。",
          "", "这是当前定向文献库中已确认的方法标注频次；未记录代表未确认。百分比是多标签，不应相加。",
          "", "| 计算/统计方法 | 篇数 | 比例 |", "|---|---:|---:|"]
    md += [f"| {r['label']} | {r['n_studies']}/{r['denominator']} | {r['percent']:.2f}% |" for r in top]
    md += ["", "[全部方法CSV](method_summary.csv) · [计算方法CSV](computational_methods.csv) · [完整JSON](summary.json)",
           "", "统计单位为文章，不是患者、细胞或独立队列；同队列复用的论文不能视作独立重复验证。", ""]
    (out_dir / "README.md").write_text("\n".join(md), encoding="utf-8")
    payload = {"studies": catalog["studies"], "methods": catalog["methods"], "annotations": catalog["method_annotations"],
               "questions": catalog["clinical_questions"], "context": catalog["context_sources"],
               "summaries": summaries, "defaultCohort": cohort, "manifest": catalog["manifest"], "families": FAMILY_LABELS}
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    page = TEMPLATE.replace("__ATLAS_DATA__", data).replace("__ATLAS_VERSION__", html.escape(catalog["manifest"]["version"])).replace("__ANNOTATION_DATE__", html.escape(catalog["manifest"]["annotation_date"]))
    (out_dir / "index.html").write_text(page, encoding="utf-8")
    build_pathways(catalog, out_dir)
    build_evidence(catalog, root, out_dir)
    build_software(root, out_dir)
    return stats


def main(root=None):
    root = Path(root or Path(__file__).resolve().parents[2])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=COHORTS, default="manuscript")
    parser.add_argument("--out", type=Path, default=root / "docs")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        cat = load_catalog(root / "data")
        validate_software(json.loads((root / "data/software_sources.json").read_text(encoding="utf-8")))
        print(json.dumps({"valid": True, "studies": len(cat["studies"]), "annotations": len(cat["method_annotations"])}, ensure_ascii=False))
        return
    stats = build(root, args.out, args.cohort)
    print(json.dumps({"cohort": args.cohort, "denominator": stats["denominator"],
                      "confirmed_annotations": stats["annotation_count"], "methods": stats["annotated_method_count"]}, ensure_ascii=False))


TEMPLATE = r'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACM Methods Atlas · 方法与临床问题证据图谱</title>
<style>
:root{--ink:#243b4a;--blue:#154f68;--muted:#657c89;--line:#d8e4ea;--bg:#f3f7f9}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif}header{background:#133f55;color:#fff;padding:38px max(24px,calc((100vw - 1160px)/2))}h1{font-size:34px;margin:8px 0}header p{color:#d9e9ef;max-width:940px}header a{color:#f4d79b}main{max-width:1200px;padding:25px 22px 60px;margin:auto}h2{font-size:22px;color:var(--blue);margin:30px 0 14px}a{color:#086b91}.note{background:#e9f2f6;border-left:4px solid #4c8ca2;padding:15px 18px;margin:15px 0}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.metric{padding:18px;border:1px solid var(--line);border-radius:9px;background:white}.metric b{display:block;font-size:28px;color:var(--blue)}.metric span{color:var(--muted);font-size:13px}.controls{display:flex;flex-wrap:wrap;gap:10px;margin:15px 0}input,select{padding:11px 13px;background:#fff;border:1px solid #b6cbd6;border-radius:6px;font:inherit;color:var(--ink)}input{flex:1;min-width:230px}table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{border:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}th{background:#e9f1f5}.table-wrap{overflow:auto;max-height:520px}.bar{display:inline-block;height:9px;background:#4b91a9;border-radius:4px;margin-left:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}details.study,details.context{background:#fff;border:1px solid var(--line);border-radius:8px;margin:13px 0;padding:16px 19px}summary{cursor:pointer;font-weight:600;line-height:1.7}summary small{font-weight:400;color:var(--muted)}.pill{display:inline-block;border:1px solid #c8dce6;background:#f3f8fa;border-radius:12px;padding:1px 8px;margin:2px;font-size:12px}.methods{padding-left:21px}.methods li{margin:12px 0}.methods p{margin:3px 0;font-size:13px}.source-note{color:var(--muted);font-size:12px;overflow-wrap:anywhere}.question{padding:14px 17px;background:#fff;border:1px solid var(--line);border-radius:7px;margin:10px 0}.question h3{margin:2px 0;font-size:16px}.downloads a{display:inline-block;margin-right:16px;margin-bottom:7px}footer{padding-top:20px;margin-top:30px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}@media(max-width:800px){h1{font-size:27px}.cards{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}header{padding:28px 23px}}button{cursor:pointer}
</style></head><body><header><small>研究路径与方法目录 · v__ATLAS_VERSION__ · __ANNOTATION_DATE__</small><h1>ACM Methods Atlas</h1><p>把致心律失常性心肌病研究中的方法、证据类型与临床问题放在一起。逐篇可追溯，统计可复现，支持持续补充和纠错。</p><a href="https://github.com/Zero-soda/acm-methods-atlas">GitHub 开源项目</a></header><main>
<div class="note"><b>先看研究如何串联：</b><a href="research_paths.html">打开研究路径图：从问题、方法与发现走向下一步临床研究 →</a></div>
<div class="note"><b>研究连接的支持条件：</b><a href="connection_audit.html">查看时间、空间、扰动与临床结局审计 →</a></div>
<div class="note"><b>代码与实际复现：</b><a href="software.html">代码来源、版本与运行状态</a> · <a href="workflows/gse29819/index.html">公开 ACM 配对双室案例与可重生成图表 →</a></div>
<div class="note"><b>统计口径：</b>当前定向文献库中已确认的方法标注频次。分母为研究文章，同一文章可包含多种方法；未标注表示未确认。此库不估计整个ACM领域的方法使用率，也不以方法数量评价研究质量。</div>
<label for="cohort">统计队列：</label><select id="cohort"><option value="manuscript">综述引用的正式原始研究</option><option value="peer_reviewed">目录内全部正式原始研究</option><option value="all">全部研究记录（含预印本）</option></select>
<div class="cards" id="metrics"></div>
<div class="grid"><section><h2>计算与统计方法</h2><div class="table-wrap"><table><thead><tr><th>已确认的方法</th><th>研究篇数</th><th>比例</th></tr></thead><tbody id="computational"></tbody></table></div></section><section><h2>方法上位分类</h2><div class="table-wrap"><table><thead><tr><th>方法类别</th><th>研究篇数</th><th>比例</th></tr></thead><tbody id="groups"></tbody></table></div><p class="source-note">上位分类按研究去重，同组多个方法只算一篇。真实随访、分批时间序列与计算拟时序分别编码。</p></section></div>
<h2>方法连接哪些临床问题</h2><div id="questions"></div>
<h2 id="catalogue">研究与方法目录</h2><div class="controls"><input id="search" type="search" placeholder="检索题名、DOI、方法或证据说明" aria-label="检索目录"><select id="family" aria-label="方法类别"><option value="">全部方法类别</option></select><select id="question" aria-label="临床问题"><option value="">全部临床问题</option></select></div><p class="source-note" id="shown"></p><div id="studies"></div>
<h2>临床背景来源</h2><p>指南、综述、注册和会议资料单列；不进入原始研究的方法统计分母。试验注册与会议信号不等同于已完成疗效验证。</p><div id="context"></div>
<h2>下载与复现</h2><div class="downloads"><a href="method_summary.csv">方法统计CSV</a><a href="computational_methods.csv">计算方法CSV</a><a href="method_cooccurrence.csv">方法共现CSV</a><a href="exports/studies.csv">研究目录CSV</a><a href="exports/method_annotations.csv">逐条标注CSV</a><a href="exports/all_cohort_summaries.json">三种口径JSON</a></div><p><code>python3 scripts/build_atlas.py</code> 可从项目中的数据重建本页与统计。运行环境为 Python 3.10+，没有第三方依赖。</p>
<footer>代码：MIT；项目原创归纳与标注：CC BY 4.0。论文原文、第三方图表及患者级数据不打包，权利归原权利人。AI辅助整理与核对，尚非双人独立人工全文编码；欢迎附原始来源提交纠错。证据检索范围与标注深度见项目说明。</footer>
</main><script id="atlas-data" type="application/json">__ATLAS_DATA__</script><script>
'use strict';const D=JSON.parse(document.getElementById('atlas-data').textContent),E=id=>document.getElementById(id),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),M=Object.fromEntries(D.methods.map(m=>[m.method_id,m])),A={};for(const a of D.annotations)(A[a.study_id]??=[]).push(a);let cohort=D.defaultCohort;
for(const [id,label] of Object.entries(D.families))E('family').insertAdjacentHTML('beforeend','<option value="'+id+'">'+label+'</option>');for(const q of D.questions)E('question').insertAdjacentHTML('beforeend','<option value="'+q.question_id+'">'+esc(q.label_zh)+'</option>');
const groupNames=D.manifest.group_labels_zh,statusNames={verified_local_text:'核对原文相关段落',verified_existing_audit:'依据既有审读记录',abstract_only:'摘要级'};
function summary(){const s=D.summaries[cohort];E('metrics').innerHTML=[[s.denominator,'当前队列研究篇数'],[s.annotated_method_count,'已确认方法概念'],[s.annotation_count,'研究—方法标注'],[D.context.length,'单列临床背景来源']].map(([n,t])=>'<div class="metric"><b>'+n+'</b><span>'+t+'</span></div>').join('');E('computational').innerHTML=s.by_method.filter(r=>r.family==='computational').map(r=>'<tr><td>'+esc(r.label)+'</td><td>'+r.n_studies+'/'+r.denominator+'</td><td>'+r.percent.toFixed(2)+'%</td></tr>').join('');E('groups').innerHTML=[...s.by_group].sort((a,b)=>b.n_studies-a.n_studies||a.id.localeCompare(b.id)).map(r=>'<tr><td>'+esc(groupNames[r.id]||r.id)+'</td><td>'+r.n_studies+'/'+r.denominator+'</td><td>'+r.percent.toFixed(2)+'%<span class="bar" style="width:'+r.percent*.65+'px"></span></td></tr>').join('');E('questions').innerHTML=s.clinical_questions.map(q=>'<div class="question"><h3>'+esc(q.label_zh)+' <small>('+q.n_studies+'篇)</small></h3><p>'+esc(q.scope_note)+'</p><span class="source-note">此处为综述问题映射，尚非验证过的决策规则。</span></div>').join('');render();}
function render(){const ids=new Set(D.summaries[cohort].selected_study_ids),query=E('search').value.trim().toLowerCase(),fam=E('family').value,qid=E('question').value;const rows=D.studies.filter(s=>ids.has(s.study_id)&&(!qid||s.clinical_question_ids.includes(qid))&&(!fam||(A[s.study_id]||[]).some(a=>M[a.method_id].family===fam))&&(!query||[s.study_id,s.title,s.doi,...(A[s.study_id]||[]).map(a=>M[a.method_id].label_zh+' '+a.evidence_basis)].join(' ').toLowerCase().includes(query))).sort((a,b)=>b.year-a.year||a.study_id.localeCompare(b.study_id));E('shown').textContent='目录筛选显示 '+rows.length+' 篇；上方汇总按所选统计队列计算。';E('studies').innerHTML=rows.map(s=>'<details class="study"><summary>'+esc(s.title)+'<br><small>'+esc(s.study_id)+' · '+s.year+' · '+esc(s.publication_status)+'</small></summary><p><a target="_blank" rel="noopener" href="'+esc(s.url)+'">原始来源</a> · DOI '+esc(s.doi)+'</p><p>'+s.systems.map(x=>'<span class="pill">'+esc(x)+'</span>').join('')+'</p><p class="source-note">阅读层级：'+esc(s.reading_depth)+'<br>独立性说明：'+esc(s.independence_note)+'</p><ul class="methods">'+(A[s.study_id]||[]).filter(a=>!fam||M[a.method_id].family===fam).map(a=>'<li><b>'+esc(M[a.method_id].label_zh)+'</b> <span class="pill">'+esc(D.families[M[a.method_id].family])+'</span><span class="pill">'+esc(statusNames[a.annotation_status])+'</span><p>'+esc(a.evidence_basis)+'</p><p class="source-note">定位：'+esc(a.source_locator)+(a.data_origin!=='not_classified'?' · 数据来源：'+esc(a.data_origin):'')+'</p></li>').join('')+'</ul></details>').join('');}
E('context').innerHTML=D.context.map(s=>'<details class="context"><summary>'+esc(s.title)+'<br><small>'+esc(s.source_kind)+'</small></summary><p><a target="_blank" rel="noopener" href="'+esc(s.url)+'">查看来源</a></p><p>'+esc(s.evidence_note)+'</p></details>').join('');E('cohort').value=cohort;E('cohort').addEventListener('change',()=>{cohort=E('cohort').value;summary()});['search','family','question'].forEach(id=>E(id).addEventListener(id==='search'?'input':'change',render));E('search').value=new URLSearchParams(location.search).get('study')||'';summary();
</script></body></html>'''

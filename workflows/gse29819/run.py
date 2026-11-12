#!/usr/bin/env python3
"""Fetch pinned public inputs, run a donor-aware R analysis, and build its report.

No third-party Python dependencies. Raw and prepared data stay in ignored cache.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def acquire(spec, cache, source_dir=None):
    """Use only the expected checksum; never silently accept an updated input."""
    target = cache / spec.get("filename", f"{spec['name']}-{spec['version']}.tar.gz" if "name" in spec else "input")
    if target.exists():
        if sha256(target) != spec["sha256"]:
            raise ValueError(f"Checksum mismatch in cached {target.name}; inspect it before removing/replacing it")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    try:
        source = source_dir / target.name if source_dir else None
        if source and source.is_file():
            shutil.copyfile(source, part)
        else:
            print(f"Downloading {target.name}", flush=True)
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "ACM-Methods-Atlas/0.4-public-workflow"})
            with urllib.request.urlopen(request, timeout=90) as response, part.open("wb") as output:
                shutil.copyfileobj(response, output)
        if sha256(part) != spec["sha256"]:
            raise ValueError(f"Source checksum changed for {target.name}; no analysis performed. Review source_manifest before updating the pin")
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return target


def parse_sample_metadata(headers):
    accessions = headers["!Sample_geo_accession"][0]
    titles = headers["!Sample_title"][0]
    if len(accessions) != len(titles) or len(set(accessions)) != len(accessions):
        raise ValueError("Duplicate or inconsistent GEO samples")
    rows = []
    characteristics = headers.get("!Sample_characteristics_ch1", [])
    for index, (sample, title) in enumerate(zip(accessions, titles)):
        match = re.fullmatch(r"(LV|RV)_(ARVC|DCM|NF)_(\d+)", title)
        if not match:
            raise ValueError(f"Unsupported sample title: {title}")
        chamber, diagnosis, number = match.groups()
        info = {}
        for entry in characteristics:
            if len(entry) != len(accessions):
                raise ValueError("Inconsistent characteristic length")
            key, separator, value = entry[index].partition(":")
            if separator:
                info[key.strip().lower()] = value.strip()
        age = info.get("age", "")
        age = str(float(age)) if re.fullmatch(r"\d+(?:\.\d+)?", age) else "NA"
        sex = {"w": "F", "f": "F", "m": "M"}.get(info.get("gender", "").lower(), "NA")
        expected_ventricle = {"LV": "left", "RV": "right"}[chamber]
        if info.get("ventricle") != expected_ventricle:
            raise ValueError(f"Title/ventricle disagreement in {sample}")
        rows.append(dict(sample=sample, title=title, donor=f"{diagnosis}_{number}", chamber=chamber, diagnosis=diagnosis, age=age, sex=sex))
    validate_pairs(rows)
    return rows


def validate_pairs(rows):
    donors = {}
    for row in rows:
        donors.setdefault(row["donor"], []).append(row)
    for donor, pair in donors.items():
        if len(pair) != 2 or {r["chamber"] for r in pair} != {"LV", "RV"}:
            raise ValueError(f"Incomplete/duplicate chamber pair: {donor}")
        if any(len({r[field] for r in pair}) != 1 for field in ("diagnosis", "age", "sex")):
            raise ValueError(f"Inconsistent donor covariates: {donor}")
    return donors


def prepare_inputs(series, annotation, prepared, spec):
    prepared.mkdir(parents=True, exist_ok=True)
    headers, samples, probe_count = {}, None, 0
    expression = prepared / "expression.tsv.gz"
    with gzip.open(series, "rt", encoding="utf-8") as source, expression.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as output:
                writer = csv.writer(output, delimiter="\t", lineterminator="\n")
                in_table = False
                for line in source:
                    if line.startswith("!series_matrix_table_begin"):
                        samples = parse_sample_metadata(headers)
                        in_table = True
                        continue
                    if line.startswith("!series_matrix_table_end"):
                        in_table = False
                        break
                    if not in_table:
                        if line.startswith("!") and "\t" in line:
                            row = next(csv.reader([line], delimiter="\t"))
                            headers.setdefault(row[0], []).append(row[1:])
                        continue
                    row = next(csv.reader([line], delimiter="\t"))
                    if row[0] == "ID_REF":
                        if row[1:] != [r["sample"] for r in samples]:
                            raise ValueError("Matrix columns and GEO metadata do not match")
                        writer.writerow(["probe_id", *row[1:]])
                    else:
                        if len(row) != len(samples) + 1:
                            raise ValueError("Expression column count changed")
                        if any(not math.isfinite(float(x)) or float(x) <= 0 for x in row[1:]):
                            raise ValueError("log2(x) requires positive finite MAS5 values; no automatic pseudocount")
                        writer.writerow(row)
                        probe_count += 1
    if samples is None or not probe_count:
        raise ValueError("Missing series matrix")
    donors = validate_pairs(samples)
    groups = {name: sum(pair[0]["diagnosis"] == name for pair in donors.values()) for name in spec["expected_donors"]}
    if len(samples) != spec["expected_samples"] or groups != spec["expected_donors"]:
        raise ValueError(f"Unexpected sample/donor counts: {len(samples)}, {groups}")
    with (prepared / "samples.tsv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, list(samples[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(samples)
    mapped, excluded, header = [], 0, None
    with gzip.open(annotation, "rt", encoding="utf-8") as source:
        for line in source:
            if line.startswith("ID\t"):
                header = next(csv.reader([line], delimiter="\t"))
                continue
            if header is None or line.startswith(("!", "#", "^")) or not line.strip():
                continue
            cells = next(csv.reader([line], delimiter="\t"))
            if len(cells) != len(header):
                raise ValueError("Malformed GPL annotation row")
            row = dict(zip(header, cells))
            symbols = {s.strip() for s in row["Gene symbol"].split("///") if s.strip() and s.strip() != "---"}
            if len(symbols) == 1:
                mapped.append((row["ID"], next(iter(symbols))))
            else:
                excluded += 1
    if not mapped or len({x[0] for x in mapped}) != len(mapped):
        raise ValueError("Missing or duplicate unambiguous annotation")
    with (prepared / "annotation.tsv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target, delimiter="\t", lineterminator="\n")
        writer.writerow(["probe_id", "gene_symbol"])
        writer.writerows(mapped)
    return {"expression_probes": probe_count, "samples": len(samples), "independent_donors": len(donors), "donor_groups": groups, "unambiguous_annotation_rows": len(mapped), "ambiguous_or_unmapped_annotation_rows": excluded}


def run_checked(command, *, env=None, timeout=1200):
    # subprocess supervises process completion and enforces a hard timeout.
    subprocess.run(command, check=True, env=env, timeout=timeout)


def r_environment(cache, lock, install):
    library = cache / "r-library"
    library.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, R_LIBS_USER=str(library))
    for package in lock["r_packages_install_order"]:
        expression = f'quit(status=if(requireNamespace("{package["name"]}",quietly=TRUE) && as.character(packageVersion("{package["name"]}"))=="{package["version"]}") 0 else 1)'
        check = subprocess.run(["Rscript", "--vanilla", "-e", expression], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check.returncode:
            if not install:
                raise RuntimeError(f"Requires {package['name']} {package['version']}; rerun with --install to build pinned packages in the local cache")
            archive = acquire(package, cache / "package-sources")
            print(f"Installing {package['name']} {package['version']} into local workflow cache", flush=True)
            run_checked(["R", "CMD", "INSTALL", "--no-multiarch", "--library=" + str(library), str(archive)], env=env)
    return library, env


def read_tsv(path):
    with Path(path).open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def canonical_compress(path):
    target = path.with_suffix(path.suffix + ".gz")
    with path.open("rb") as source, target.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as output:
            shutil.copyfileobj(source, output)
    path.unlink()
    return target


def render_figures(out):
    """Convert the same R vector PDF to SVG and PNG without an X11 display."""
    if not shutil.which("pdftocairo"):
        raise RuntimeError("Figure export requires Poppler pdftocairo (macOS: brew install poppler; Debian/Ubuntu: apt install poppler-utils)")
    figures = sorted((out / "figures").glob("*.pdf"))
    if len(figures) != 4:
        raise ValueError(f"Expected 4 PDF figures, found {len(figures)}")
    for path in figures:
        run_checked(["pdftocairo", "-svg", str(path), str(path.with_suffix(".svg"))], timeout=120)
        run_checked(["pdftocairo", "-png", "-singlefile", "-r", "180", str(path), str(path.with_suffix(""))], timeout=120)
        for extension in (".pdf", ".svg", ".png"):
            if path.with_suffix(extension).stat().st_size < 100:
                raise ValueError(f"Missing or empty scientific figure: {path.stem}{extension}")
    version = subprocess.run(["pdftocairo", "-v"], capture_output=True, text=True, check=True)
    return (version.stdout + version.stderr).strip().splitlines()[0]


def render_report(out, spec, qc, lock):
    contrasts = read_tsv(out / "contrast_summary.tsv")
    sensitivity = read_tsv(out / "primary_sensitivity_summary.tsv")
    leave_one_out = read_tsv(out / "primary_leave_one_out_summary.tsv")
    primary = next(row for row in contrasts if row["model_role"] == "primary")
    sensitivity_counts = [int(row["FDR05"]) for row in sensitivity]
    conclusion = f"主交互作用对比在 {primary['n_genes']} 个基因中有 {primary['FDR05']} 个达到 BH FDR < 0.05；固定的敏感性模型中为 {min(sensitivity_counts)}–{max(sensitivity_counts)} 个。阈值计数受探针处理、方差趋势及供者集合影响，需同时查看效应量与稳定性。"
    summary = {"accession": spec["accession"], "workflow_version": "0.4.0", "implementation": spec["implementation"], "input_qc": qc, "contrasts": contrasts, "primary_sensitivity": sensitivity, "leave_one_donor_out": leave_one_out, "interpretation_limits": spec["limitations"], "validation": "One dataset reanalysis; no independent replication or clinical endpoint validation"}
    write_json(out / "results_summary.json", summary)
    def table(rows):
        if not rows:
            return "<p>No rows.</p>"
        fields = list(rows[0])
        return '<div class="scroll"><table><thead><tr>' + "".join("<th>" + html.escape(f) + "</th>" for f in fields) + "</tr></thead><tbody>" + "".join("<tr>" + "".join("<td>" + html.escape(str(row.get(f, ""))) + "</td>" for f in fields) + "</tr>" for row in rows) + "</tbody></table></div>"
    figures = sorted((out / "figures").glob("*.svg"))
    gallery = "".join(f'<figure><a href="figures/{p.name}"><img src="figures/{p.name}" alt="{html.escape(p.stem)}"></a><figcaption>{html.escape(p.stem)} · <a href="figures/{p.with_suffix(".pdf").name}">PDF</a> · <a href="figures/{p.with_suffix(".png").name}">PNG</a></figcaption></figure>' for p in figures)
    files = [p for p in sorted(out.iterdir()) if p.is_file() and p.name not in {"index.html", "README.md"}]
    downloads = " · ".join(f'<a href="{html.escape(p.name)}">{html.escape(p.name)}</a>' for p in files)
    limits = "".join("<li>" + html.escape(x) + "</li>" for x in spec["limitations"])
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ACM · 配对双室复现案例</title><style>
body{{font:15px/1.8 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;color:#243b4a;background:#f3f7f9;margin:0}}header{{background:#133f55;color:white;padding:28px max(22px,calc((100vw - 1140px)/2))}}main{{max-width:1140px;margin:auto;padding:22px}}h1{{font-size:29px}}h2{{font-size:22px}}a{{color:#08759b}}header a{{color:#f5d994}}.note{{background:#e9f2f6;padding:16px 20px;border-left:4px solid #4c8ca2}}.scroll{{overflow:auto}}table{{border-collapse:collapse;font-size:12px;background:white}}th,td{{border:1px solid #d8e4ea;padding:8px;text-align:left}}img{{width:100%;height:auto;background:white}}figure{{margin:20px 0}}code{{overflow-wrap:anywhere}}.downloads{{overflow-wrap:anywhere}}figcaption{{font-size:13px;color:#657c89}}</style></head><body><header><a href="../../index.html">ACM Methods Atlas</a> · <a href="../../software.html">代码来源目录</a><h1>公开数据复现：ACM 的配对双室表达</h1><p>GSE29819 · 19 位供者，38 份组织 · donor-aware reanalysis</p></header><main>
<div class="note"><b>本例检验什么：</b>比较 ARVC 与非衰竭对照的供者内 RV−LV 表达差异，并检查分析选择和个别供者的影响。这是对公开终末期组织数据的重新分析；原研究已讨论双室表达，不宣称新发现或临床分期。</div>
<p>原始研究：<a href="{spec['article']['url']}">{html.escape(spec['article']['title'])}</a> · <a href="https://doi.org/{spec['article']['doi']}">DOI</a>。实现代码、处理与源文件校验值：<a href="https://github.com/Zero-soda/acm-methods-atlas/tree/main/workflows/gse29819">GitHub 工作流</a>。</p>
<h2>运行与统计单位</h2><p>19 位供者：ARVC 6、DCM 7、NF 6；每位供者配对 LV/RV。主分析使用每人的 log2(RV)−log2(LV)，在 ARVC 与 NF 之间比较。MAS5 线性信号显式 log2 转换，不加伪计数；仅使用无歧义基因注释，多个探针取平均 log2 表达。</p><p>limma 3.62.2，trend=TRUE、robust=FALSE。BH 校正在每项对比的全基因范围内分别计算，未对全部探索性对比联合校正；主交互作用检验单列，次要对比不升级为验证。阈值仅用于描述，不显著不能证明心室等价。</p>
<h2>这次运行说明什么</h2><p>{conclusion}</p><p>组内左右室差异、疾病相关表达变化与疾病×心室交互作用是不同问题；不能用其中一个检验替代另一个。</p>
<h2>全部固定对比</h2>{table(contrasts)}
<h2>方法选择敏感性</h2>{table(sensitivity)}<p>方法一致性与留一供者分析反映本数据内的敏感性，不是独立人群验证。</p>
<h2>结果图：可下载并由代码重新生成</h2>{gallery}
<h2>临床研究下一步</h2><p>本例能复核 B-S1 的心室组织表达一侧。下一项研究需要同患者、同区域、接近时间的组织分子测量与 CMR／电标测对应，再通过前瞻性随访检验其是否关联持续性室性心律失常等明确结局。不同供者的横断面组织不能排列成真实病程。</p><ul>{limits}</ul>
<h2>复用与下载</h2><p><code>python3 workflows/gse29819/run.py --install</code> 下载校验输入、在本地缓存安装锁定版本、运行分析并生成本页。要求 Python 3.10+、R 4.4.3（参考环境）、Poppler 的 pdftocairo，以及安装缺失 R 包时所需的构建工具。默认输出到 <code>docs/workflows/gse29819</code>，原始数据留在忽略的缓存目录。</p><div class="downloads">{downloads}</div><p>图和统计表由本项目代码生成；使用时同时引用<a href="{spec['article']['url']}">原始研究</a>、<a href="https://doi.org/10.1093/nar/gkv007">limma</a>和本项目版本。第三方软件保留原许可；原始表达与完整临床协变量表未打包；派生 QC 和敏感性表保留公开的样本／供者及诊断、心室标签。</p></main></body></html>'''
    (out / "index.html").write_text(page, encoding="utf-8")
    md = ["# GSE29819 donor-aware reanalysis", "", spec["implementation"], "", f"Input: {qc['independent_donors']} independent donors, {qc['samples']} tissues; groups {qc['donor_groups']}.", "", "Primary estimand: " + spec["primary_estimand"], "", conclusion, "", "[Analysis/download report](index.html) · [Machine-readable results](results_summary.json)", "", "## Clinical evidence boundary", "", *["- " + x for x in spec["limitations"]], "", "The original study already examined biventricular expression. This example demonstrates reproducibility and sensitivity; no new biological discovery is claimed.", ""]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def verify_outputs(current, reference):
    # Compare decompressed numerical tables, not platform-specific font/PDF metadata.
    names = {p.name for p in current.iterdir() if p.name.endswith((".tsv", ".tsv.gz"))}
    reference_names = {p.name for p in reference.iterdir() if p.name.endswith((".tsv", ".tsv.gz"))}
    if not names or names != reference_names:
        raise ValueError(f"Re-run table inventory mismatch: missing={sorted(reference_names - names)}, extra={sorted(names - reference_names)}")
    differences = []
    for name in sorted(names):
        a, b = current / name, reference / name
        if not b.exists():
            differences.append(name + ": absent from reference")
            continue
        opener = gzip.open if name.endswith(".gz") else open
        with opener(a, "rb") as x, opener(b, "rb") as y:
            if x.read() != y.read():
                differences.append(name + ": numerical table differs")
    if differences:
        raise ValueError("Re-run comparison failed: " + "; ".join(differences))
    return {"status": "exact_table_match", "compared_tables": len(names), "comparison": "decompressed numerical TSV contents, same environment; graphics and timestamps excluded"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "gse29819")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "workflows" / "gse29819")
    parser.add_argument("--source-dir", type=Path, help="Use previously downloaded source files only when their pinned checksums match")
    parser.add_argument("--install", action="store_true", help="Build missing pinned R packages inside cache; requires compilers")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--verify-against", type=Path, help="Compare all numerical tables with a previous result directory")
    args = parser.parse_args()
    spec = json.loads((HERE / "source_manifest.json").read_text())
    lock = json.loads((HERE / "environment.lock.json").read_text())
    cache, out = args.cache.resolve(), args.out.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    inputs = [acquire(x, cache / "sources", args.source_dir) for x in spec["inputs"]]
    qc = prepare_inputs(*inputs, cache / "prepared", spec)
    print(json.dumps(qc), flush=True)
    if args.prepare_only:
        return
    if not shutil.which("pdftocairo"):
        raise RuntimeError("Install Poppler pdftocairo before the analysis; see workflow README")
    library, env = r_environment(cache, lock, args.install)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Analysis runs in a staging directory; failure cannot leave a stale success report.
    with tempfile.TemporaryDirectory(prefix="gse29819-", dir=cache) as temporary:
        staging = Path(temporary)
        run_checked(["Rscript", "--vanilla", str(HERE / "analyze.R"), str(cache / "prepared"), str(staging), str(library)], env=env)
        if not (staging / "RUN_COMPLETE.txt").exists():
            raise RuntimeError("R did not produce its completion marker")
        graphics_version = render_figures(staging)
        for path in list(staging.glob("*.tsv")):
            if path.stat().st_size > 150_000:
                canonical_compress(path)
        checks = {x.name: sha256(x) for x in staging.rglob("*") if x.is_file() and x.suffix not in {".pdf", ".png", ".svg"}}
        manifest = {"workflow_version": "0.4.0", "source_manifest_sha256": sha256(HERE / "source_manifest.json"), "environment_lock_sha256": sha256(HERE / "environment.lock.json"), "analysis_script_sha256": sha256(HERE / "analyze.R"), "runner_sha256": sha256(Path(__file__)), "inputs": spec["inputs"], "environment_lock": lock, "graphics_converter": graphics_version, "input_qc": qc, "numerical_file_sha256": checks, "run_status": "completed", "original_author_code_executed": False, "clinical_bridge_completed": False}
        if args.verify_against:
            manifest["reproducibility_check"] = verify_outputs(staging, args.verify_against.resolve())
        write_json(staging / "run_manifest.json", manifest)
        render_report(staging, spec, qc, lock)
        generated = [str(p.relative_to(staging)) for p in staging.rglob("*") if p.is_file()]
        old_manifest = out / "generated_files.json"
        if old_manifest.exists():
            for relative in json.loads(old_manifest.read_text()):
                path = out / relative
                if path.resolve().is_relative_to(out) and path.is_file() and relative not in generated:
                    path.unlink()
        out.mkdir(parents=True, exist_ok=True)
        for relative in generated:
            target = out / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging / relative, target)
        write_json(out / "generated_files.json", sorted(generated))
    print(f"COMPLETE: {out / 'index.html'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"WORKFLOW FAILED: {error}", file=sys.stderr)
        sys.exit(1)

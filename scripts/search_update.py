#!/usr/bin/env python3
"""Run a logged bibliographic update; do not screen or change the pilot corpus."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def get_json(endpoint, params):
    req = Request(endpoint + "?" + urlencode(params), headers={"User-Agent": "ACMMethodsAtlas/0.3 (bibliographic research)"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=40) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            delay = min(30, max(2, int(exc.headers.get("Retry-After", "3"))))
            time.sleep(delay)


def normalize_doi(value):
    value = (value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.strip()


def merge_records(records, studies):
    """Merge identifiers with provenance; title-only similarity never auto-merges."""
    groups, aliases = {}, {}
    for r in records:
        keys = (["doi:" + normalize_doi(r["doi"])] if r.get("doi") else [])
        keys += (["pmid:" + r["pmid"]] if r.get("pmid") else [])
        keys += [r["provider"] + ":" + r["source_id"]]
        hits = {aliases[k] for k in keys if k in aliases}
        target = sorted(hits)[0] if hits else keys[0]
        if target not in groups:
            groups[target] = {k: r.get(k, "") for k in ("title", "doi", "pmid", "year", "journal", "publication_types")}
            groups[target]["source_records"] = []
        for old in sorted(hits - {target}):
            other = groups.pop(old)
            groups[target]["source_records"] += other["source_records"]
            for k, v in list(aliases.items()):
                if v == old:
                    aliases[k] = target
            for field in ("doi", "pmid", "title", "year", "journal"):
                groups[target][field] = groups[target][field] or other[field]
        group = groups[target]
        for field in ("doi", "pmid", "title", "year", "journal"):
            group[field] = group[field] or r.get(field, "")
        group["source_records"].append({k: r[k] for k in ("provider", "source_id", "query_id")})
        for k in keys:
            aliases[k] = target
    pilot = {normalize_doi(s["doi"]): s["study_id"] for s in studies}
    out = []
    for key, row in sorted(groups.items()):
        row["record_id"] = key
        row["doi"] = normalize_doi(row["doi"])
        row["existing_pilot_study_id"] = pilot.get(row["doi"], "")
        row["screening_status"] = "not_screened_this_update"
        row["url"] = "https://doi.org/" + row["doi"] if row["doi"] else ("https://pubmed.ncbi.nlm.nih.gov/" + row["pmid"] + "/" if row["pmid"] else "")
        out.append(row)
    return out


def search_pubmed(config, cap):
    result = get_json(config["endpoint"], {"db": "pubmed", "term": config["query"], "retmode": "json", "retmax": min(cap, 9999)})["esearchresult"]
    ids, rows = result.get("idlist", []), []
    for start in range(0, len(ids), 150):
        time.sleep(0.4)
        data = get_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", {"db": "pubmed", "id": ",".join(ids[start:start+150]), "retmode": "json"})["result"]
        for pmid in data.get("uids", []):
            entry = data[pmid]
            doi = next((a["value"] for a in entry.get("articleids", []) if a["idtype"] == "doi"), "")
            rows.append({"provider": "pubmed", "source_id": pmid, "query_id": config["query_id"], "pmid": pmid, "doi": normalize_doi(doi), "title": html.unescape(entry.get("title", "")), "year": entry.get("pubdate", "")[:4], "journal": entry.get("fulljournalname", ""), "publication_types": entry.get("pubtype", [])})
    return rows, {"count": int(result["count"]), "retrieved_ids": len(ids), "retrieved_metadata": len(rows), "truncated": int(result["count"]) > len(ids), "warnings": result.get("warninglist", {}), "query_translation": result.get("querytranslation", ""), "ids": ids}


def search_europe_pmc(config, cap):
    cursor, rows, total = "*", [], None
    while len(rows) < cap:
        result = get_json(config["endpoint"], {"query": config["query"], "format": "json", "pageSize": min(1000, cap-len(rows)), "cursorMark": cursor, "resultType": "lite"})
        total = result["hitCount"]
        page = result.get("resultList", {}).get("result", [])
        for entry in page:
            source = entry.get("source", "")
            rows.append({"provider": "europe_pmc", "source_id": source + ":" + entry["id"], "query_id": config["query_id"], "pmid": entry["id"] if source == "MED" else entry.get("pmid", ""), "doi": normalize_doi(entry.get("doi", "")), "title": html.unescape(entry.get("title", "")), "year": entry.get("pubYear", ""), "journal": entry.get("journalTitle", ""), "publication_types": [entry.get("pubType", "")] if entry.get("pubType") else []})
        next_cursor = result.get("nextCursorMark")
        if not page or not next_cursor or next_cursor == cursor or len(rows) >= total:
            break
        cursor = next_cursor
        time.sleep(0.4)
    return rows, {"count": total, "retrieved_metadata": len(rows), "truncated": total > len(rows), "ids": [r["source_id"] for r in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "searches" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--max-records", type=int, default=5000)
    parser.add_argument("--strategy", type=Path, default=ROOT / "protocol/search_strategy.json")
    parser.add_argument("--protocol", type=Path, default=ROOT / "protocol/scoping_protocol.md")
    args = parser.parse_args()
    if args.max_records < 1:
        parser.error("max-records must be positive")
    if (args.out / "search_run.json").exists():
        parser.error("A search log already exists there; choose a new --out to preserve the snapshot")
    protocol_bytes = args.protocol.read_bytes()
    strategy_bytes = args.strategy.read_bytes()
    config = json.loads(strategy_bytes)
    run = {"search_started_utc": datetime.now(timezone.utc).isoformat(), "strategy": config, "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(), "max_records_per_platform": args.max_records, "platforms": {}, "status": "bibliographic_update_only_not_screened"}
    records = []
    for provider, search in (("pubmed", search_pubmed), ("europe_pmc", search_europe_pmc)):
        try:
            rows, details = search(config[provider], args.max_records)
            run["platforms"][provider] = {"status": "success", **details}
            records += rows
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
            run["platforms"][provider] = {"status": "failed", "error": str(exc)}
    studies = json.loads((ROOT / "data/studies.json").read_text())
    merged = merge_records(records, studies)
    run.update(search_completed_utc=datetime.now(timezone.utc).isoformat(), retrieved_source_records=len(records), deduplicated_candidate_records=len(merged), matched_pilot_study_ids=sorted({r["existing_pilot_study_id"] for r in merged if r["existing_pilot_study_id"]}), not_retrieved_pilot_study_ids=sorted({s["study_id"] for s in studies} - {r["existing_pilot_study_id"] for r in merged}))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "protocol_at_search_start.md").write_bytes(protocol_bytes)
    (args.out / "strategy_at_search_start.json").write_bytes(strategy_bytes)
    for name, data in (("search_run.json", run), ("source_records.json", records), ("candidates.json", merged)):
        (args.out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["record_id", "title", "doi", "pmid", "year", "journal", "url", "existing_pilot_study_id", "screening_status", "source_records"]
    with (args.out / "candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for row in merged:
            values = {k: json.dumps(row[k], ensure_ascii=False) if isinstance(row[k], list) else str(row[k]) for k in fields}
            writer.writerow({k: "'"+v if v.startswith(("=", "+", "-", "@")) else v for k, v in values.items()})
    print(json.dumps({"platforms": {k: {a:b for a,b in v.items() if a != "ids"} for k,v in run["platforms"].items()}, "candidates": len(merged), "pilot_matches": run["matched_pilot_study_ids"], "pilot_not_retrieved": run["not_retrieved_pilot_study_ids"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

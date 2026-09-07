#!/usr/bin/env python3
"""C13b0 Indexer — portable Infinity repository scanner.

Standard-library only. Scans public www-infinity4 repositories without cloning
large repositories, classifies reusable capabilities, and records the standing
Infinity carry-forward contract used whenever a web project is built or repaired.

Optional: export GITHUB_TOKEN=... for a higher GitHub API rate limit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

OWNER = "www-infinity4"
API = "https://api.github.com"
OUT = Path("phi-index")

CARRY_FORWARD = {
    "preview_artwork": ["og:image", "twitter:image", "share-preview", "preview"],
    "open_graph": ["og:title", "og:description", "og:image", "og:url"],
    "x_large_card": ["twitter:card", "summary_large_image"],
    "share_post": ["navigator.share", "share", "twitter.com/intent", "x.com/intent"],
    "unified_wallet": ["unified-wallet", "unified wallet", "infinity-wallet", "wallet"],
    "star_coin": ["starcoin", "star coin", "star-coin"],
    "share_rewards": ["share reward", "share_count", "sharecount", "reward"],
    "durable_ledger": ["ledger", "d1", "database", "receipt", "idempot"],
    "history": ["history", "watch history", "activity history"],
    "mobile_first": ["viewport", "@media", "mobile"],
    "canonical": ["rel=\"canonical\"", "rel='canonical'", "canonicalurl"],
    "infinity_manifest": ["infinity-site.json", "infinity-site/v1"],
}

CATEGORY_RULES = {
    "image-generation": ["image generator", "diffusion", "comfyui", "flux", "stable diffusion"],
    "image-analysis": ["opencv", "segment", "ocr", "yolo", "computer vision", "depth"],
    "video": ["ffmpeg", "video", "movie", "stream", "transcod"],
    "audio": ["audio", "music", "radio", "sound", "sonic"],
    "3d": ["three.js", "threejs", "blender", "3d", "webgl", "geometry"],
    "ai-models": ["model", "transformer", "diffusers", "llm", "gemma", "ai agent"],
    "search-index": ["search", "indexer", "crawler", "retrieval", "rag"],
    "wallet-economy": ["wallet", "coin", "token", "mint", "ledger", "payment"],
    "games": ["game", "arcade", "emulator", "level", "player"],
    "web-components": ["website", "frontend", "react", "next.js", "vite", "html"],
    "science-research": ["research", "experiment", "physics", "element", "quantum", "magnet"],
    "robotics-engineering": ["robot", "actuator", "cnc", "machine", "engineering"],
}

PHI_STAGE = {
    "search-index": "red",
    "image-analysis": "yellow",
    "science-research": "yellow",
    "ai-models": "orange",
    "wallet-economy": "blue",
    "video": "blue",
    "audio": "blue",
    "image-generation": "white",
    "3d": "white",
    "web-components": "white",
}

INTERESTING_NAMES = {
    "readme.md", "package.json", "pyproject.toml", "requirements.txt", "setup.py",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "infinity-site.json",
    "index.html", "manifest.json", "vercel.json", "wrangler.toml"
}
TEXT_EXTS = {".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css"}
SKIP_PARTS = {"node_modules", "vendor", "dist", "build", ".next", ".git", "coverage", "__pycache__", ".cache", "models", "weights"}
MAX_FILES_PER_REPO = 30
MAX_FILE_BYTES = 160_000


def request_json(url: str, token: str | None, retries: int = 3):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "C13b0-Indexer/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt + 1 < retries:
                wait = int(e.headers.get("Retry-After", "5"))
                time.sleep(max(wait, 2 ** attempt))
                continue
            raise


def list_repos(owner: str, token: str | None):
    page = 1
    while True:
        q = urllib.parse.urlencode({"per_page": 100, "page": page, "type": "owner", "sort": "full_name"})
        rows = request_json(f"{API}/users/{owner}/repos?{q}", token)
        if not rows:
            return
        yield from rows
        if len(rows) < 100:
            return
        page += 1


def repo_tree(repo: dict, token: str | None):
    owner = repo["owner"]["login"]
    name = repo["name"]
    branch = urllib.parse.quote(repo.get("default_branch") or "main", safe="")
    try:
        data = request_json(f"{API}/repos/{owner}/{name}/git/trees/{branch}?recursive=1", token)
        return data.get("tree", [])
    except urllib.error.HTTPError:
        return []


def relevance(path: str) -> int:
    p = path.lower()
    parts = set(Path(p).parts)
    if parts & SKIP_PARTS:
        return -100
    name = Path(p).name
    ext = Path(p).suffix
    if name in INTERESTING_NAMES:
        return 100
    if ext not in TEXT_EXTS:
        return -10
    score = 10
    for word in ("wallet", "coin", "share", "preview", "index", "search", "api", "route", "component", "schema", "plugin", "manifest", "deploy", "worker"):
        if word in p:
            score += 12
    if "/test" in p or p.startswith("test"):
        score -= 15
    return score


def raw_text(repo: dict, path: str, token: str | None) -> str:
    owner = repo["owner"]["login"]
    name = repo["name"]
    branch = urllib.parse.quote(repo.get("default_branch") or "main", safe="")
    quoted = "/".join(urllib.parse.quote(x, safe="") for x in path.split("/"))
    try:
        data = request_json(f"{API}/repos/{owner}/{name}/contents/{quoted}?ref={branch}", token)
        if not isinstance(data, dict) or data.get("size", MAX_FILE_BYTES + 1) > MAX_FILE_BYTES:
            return ""
        import base64
        if data.get("encoding") == "base64":
            return base64.b64decode(data.get("content", "")).decode("utf-8", "replace")
    except Exception:
        return ""
    return ""


def categories(text: str):
    low = text.lower()
    scored = []
    for cat, words in CATEGORY_RULES.items():
        score = sum(low.count(w) for w in words)
        if score:
            scored.append((score, cat))
    return [cat for _, cat in sorted(scored, reverse=True)[:5]] or ["uncategorized"]


def status_for(repo: dict, files: list[str], corpus: str):
    low = corpus.lower()
    has_code = any(Path(p).suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".html"} for p in files)
    has_manifest = any(Path(p).name.lower() in {"package.json", "pyproject.toml", "requirements.txt", "cargo.toml", "go.mod"} for p in files)
    has_tests = any("test" in p.lower() for p in files)
    declared = bool(re.search(r"\b(will|should|planned|todo|roadmap|proposed|goal)\b", low))
    if has_code and has_manifest and has_tests:
        return "NEEDS_TEST"
    if has_code and has_manifest:
        return "PARTIAL"
    if has_code:
        return "PARTIAL"
    if declared or "readme" in " ".join(files).lower():
        return "SHOULD_DO"
    return "ABSENT"


def carry_forward_state(corpus: str, paths: list[str]):
    haystack = (corpus + "\n" + "\n".join(paths)).lower()
    result = {}
    for feature, needles in CARRY_FORWARD.items():
        hits = [n for n in needles if n.lower() in haystack]
        result[feature] = {"status": "FOUND" if hits else "MISSING", "evidence": hits[:5]}
    return result


def scan_repo(repo: dict, token: str | None):
    tree = repo_tree(repo, token)
    blobs = [x for x in tree if x.get("type") == "blob"]
    ranked = sorted(((relevance(x.get("path", "")), x) for x in blobs), key=lambda x: x[0], reverse=True)
    selected = [x for score, x in ranked if score >= 0][:MAX_FILES_PER_REPO]
    chunks = []
    corpus_parts = [repo.get("name", ""), repo.get("description") or "", " ".join(repo.get("topics") or [])]
    for item in selected:
        path = item["path"]
        text = raw_text(repo, path, token)
        if not text:
            continue
        corpus_parts.append(text[:40_000])
        excerpt = re.sub(r"\s+", " ", text).strip()[:700]
        if excerpt:
            chunks.append({"path": path, "sha": item.get("sha"), "score": relevance(path), "excerpt": excerpt})
    corpus = "\n".join(corpus_parts)
    cats = categories(corpus)
    paths = [x.get("path", "") for x in blobs]
    stage_counts = Counter(PHI_STAGE.get(c, "red") for c in cats)
    phi_stage = stage_counts.most_common(1)[0][0]
    return {
        "repo": repo["full_name"],
        "url": repo["html_url"],
        "description": repo.get("description"),
        "fork": repo.get("fork", False),
        "language": repo.get("language"),
        "license": (repo.get("license") or {}).get("spdx_id"),
        "default_branch": repo.get("default_branch"),
        "updated_at": repo.get("updated_at"),
        "categories": cats,
        "phi_stage": phi_stage,
        "status": status_for(repo, paths, corpus),
        "carry_forward": carry_forward_state(corpus, paths),
        "important_chunks": chunks,
    }


def write_indexes(records: list[dict]):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "repos").mkdir(exist_ok=True)
    (OUT / "categories").mkdir(exist_ok=True)
    for r in records:
        safe = r["repo"].split("/", 1)[-1]
        (OUT / "repos" / f"{safe}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    by_cat = defaultdict(list)
    for r in records:
        for cat in r["categories"]:
            by_cat[cat].append({"repo": r["repo"], "status": r["status"], "phi_stage": r["phi_stage"]})
    for cat, rows in by_cat.items():
        (OUT / "categories" / f"{cat}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    catalog = {
        "schema": "c13b0-index/v1",
        "owner": OWNER,
        "repository_count": len(records),
        "status_counts": dict(Counter(r["status"] for r in records)),
        "carry_forward_contract": list(CARRY_FORWARD),
        "repositories": [{k: r[k] for k in ("repo", "url", "categories", "phi_stage", "status")} for r in records],
    }
    (OUT / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    with (OUT / "search-index.jsonl").open("w", encoding="utf-8") as f:
        for r in records:
            for c in r["important_chunks"]:
                f.write(json.dumps({"repo": r["repo"], "category": r["categories"], "phi_stage": r["phi_stage"], **c}) + "\n")
    frontend = []
    for r in records:
        missing = [k for k, v in r["carry_forward"].items() if v["status"] == "MISSING"]
        frontend.append({"repo": r["repo"], "status": r["status"], "categories": r["categories"], "phi_stage": r["phi_stage"], "missing_carry_forward": missing, "top_chunks": r["important_chunks"][:8]})
    (OUT / "frontend-index.json").write_text(json.dumps(frontend, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Scan Infinity GitHub repositories into a compact C13b0 capability index")
    parser.add_argument("--owner", default=OWNER)
    parser.add_argument("--repo", help="Scan only one repository name")
    parser.add_argument("--limit", type=int, default=0, help="Limit repositories for a quick scan")
    args = parser.parse_args()
    token = os.getenv("GITHUB_TOKEN")
    repos = list(list_repos(args.owner, token))
    if args.repo:
        repos = [r for r in repos if r["name"].lower() == args.repo.lower()]
    if args.limit:
        repos = repos[:args.limit]
    records = []
    for i, repo in enumerate(repos, 1):
        print(f"[{i}/{len(repos)}] {repo['full_name']}", flush=True)
        try:
            records.append(scan_repo(repo, token))
        except Exception as exc:
            records.append({"repo": repo["full_name"], "url": repo["html_url"], "categories": ["scan-error"], "phi_stage": "red", "status": "BLOCKED", "carry_forward": {}, "important_chunks": [], "error": str(exc)})
    write_indexes(records)
    print(f"Indexed {len(records)} repositories into {OUT}/")


if __name__ == "__main__":
    main()

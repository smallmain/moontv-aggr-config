#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}
TEXT_EXTENSIONS = {".json", ".txt"}
DEFAULT_CACHE_TIME = 7200
DEFAULT_LITE_MIN_REPO_AGREEMENT = 3
OUTPUT_FILES = {
    "lite": ("lite.json", "lite.txt"),
    "lite_plus18": ("lite-plus18.json", "lite-plus18.txt"),
    "full": ("full.json", "full.txt"),
    "full_plus18": ("full-plus18.json", "full-plus18.txt"),
}
ALIASES = {
    "lite": ("jin18.json", "jin18.txt"),
    "lite_plus18": ("jingjian.json", "jingjian.txt"),
    "full_plus18": ("LunaTV-config.json", "LunaTV-config.txt"),
}
ADULT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"🔞",
        r"(^|[\W_])AV([\W_]|$)",
        r"成人",
        r"激情",
        r"伦理",
        r"情色",
        r"麻豆",
        r"番号",
        r"无码",
        r"有码",
        r"白浆",
        r"大奶",
        r"奶香",
        r"小鸡",
        r"桃花",
        r"滴滴",
        r"玉兔",
        r"豆豆",
        r"辣椒",
        r"香蕉",
        r"鲨鱼",
        r"杏吧",
        r"乐播",
        r"老色逼",
        r"黄AV",
        r"黑料",
        r"丝袜",
        r"色猫",
        r"souav",
        r"91精品",
        r"白嫖",
    ]
]
ADULT_CATEGORY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [r"R级", r"三级", r"情色", r"成人", r"番号", r"无码", r"有码", r"麻豆"]
]
IGNORED_DIR_NAMES = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    "web-editor",
    "CORSAPI",
}


@dataclasses.dataclass
class SourceConfig:
    name: str
    repo: str
    ref: str | None = None
    preferred_files: list[str] = dataclasses.field(default_factory=list)
    exclude_patterns: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class CandidateConfig:
    relative_path: str
    parser: str
    api_count: int
    category_count: int
    score: int
    payload: dict[str, Any]


@dataclasses.dataclass
class SelectedSource:
    config: SourceConfig
    repo_path: Path
    candidate: CandidateConfig
    candidates: list[CandidateConfig]


@dataclasses.dataclass
class SiteOccurrence:
    source_name: str
    source_file: str
    raw_name: str
    api_original: str
    api_normalized: str
    detail: str
    adult: bool


@dataclasses.dataclass
class SiteRecord:
    name: str
    api: str
    detail: str
    adult: bool
    consensus: int
    sources: list[str]
    source_files: list[str]
    observed_names: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate MoonTV/LunaTV configs from multiple repositories.")
    parser.add_argument("--config-path", default="config/sources.json", help="Path to the sources config JSON file.")
    parser.add_argument(
        "--categories-path",
        default="config/categories.json",
        help="Path to the custom categories JSON file.",
    )
    parser.add_argument("--report-path", default="build/latest.json", help="Path to the generated build report.")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root where the output files should be written.",
    )
    return parser.parse_args()


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_sources(path: Path) -> tuple[list[SourceConfig], int, int]:
    payload = load_json_file(path)
    sources = []
    for item in payload.get("sources", []):
        name = str(item.get("name") or item.get("repo") or "").strip()
        repo = str(item.get("repo") or "").strip()
        if not name or not repo:
            continue
        sources.append(
            SourceConfig(
                name=name,
                repo=repo,
                ref=str(item["ref"]).strip() if item.get("ref") else None,
                preferred_files=[str(value) for value in item.get("preferred_files", [])],
                exclude_patterns=[str(value) for value in item.get("exclude_patterns", [])],
            )
        )
    cache_time = int(payload.get("cache_time", DEFAULT_CACHE_TIME))
    lite_min_repo_agreement = int(payload.get("lite_min_repo_agreement", DEFAULT_LITE_MIN_REPO_AGREEMENT))
    return sources, cache_time, lite_min_repo_agreement


def category_is_adult(name: str, query: str) -> bool:
    candidate = f"{name} {query}"
    return any(pattern.search(candidate) for pattern in ADULT_CATEGORY_PATTERNS)


def load_categories(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in load_json_file(path):
        normalized = normalize_category(item)
        if not normalized:
            continue
        key = (normalized["name"], normalized["type"], normalized["query"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def normalize_category(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name") or "").strip()
    category_type = str(item.get("type") or "").strip()
    query = str(item.get("query") or "").strip()
    if not name or not category_type or not query:
        return None
    adult = bool(item.get("adult")) or category_is_adult(name, query)
    return {"name": name, "type": category_type, "query": query, "adult": adult}


def merge_categories(base_categories: list[dict[str, Any]], source_categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in [*base_categories, *source_categories]:
        normalized = normalize_category(item)
        if not normalized:
            continue
        key = (normalized["name"], normalized["type"], normalized["query"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def repo_clone_url(repo: str) -> str:
    if re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        return f"https://github.com/{repo}.git"
    if repo.startswith("https://github.com/") and not repo.endswith(".git"):
        return f"{repo}.git"
    return repo


def repo_slug(repo: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", repo).strip("-").lower()
    return slug or "source"


def materialize_repo(source: SourceConfig, scratch_dir: Path) -> Path:
    local_path = Path(source.repo).expanduser()
    if local_path.exists():
        return local_path.resolve()

    destination = scratch_dir / repo_slug(source.name)
    command = ["git", "clone", "--depth", "1"]
    if source.ref:
        command.extend(["--branch", source.ref])
    command.extend([repo_clone_url(source.repo), str(destination)])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git clone failed")
    return destination


def is_candidate_path(path: Path, source: SourceConfig) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    if any(part in IGNORED_DIR_NAMES for part in path.parts):
        return False
    lower_path = str(path).lower()
    if any(pattern.lower() in lower_path for pattern in source.exclude_patterns):
        return False
    return path.is_file()


def iter_candidate_paths(repo_path: Path, source: SourceConfig) -> list[Path]:
    candidates: list[Path] = []
    for path in repo_path.rglob("*"):
        if not is_candidate_path(path, source):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        candidates.append(path)
    return candidates


def extract_config_payload(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    api_site = data.get("api_site")
    if not isinstance(api_site, dict) or not api_site:
        return None

    normalized_api_site: dict[str, dict[str, Any]] = {}
    for key, value in api_site.items():
        if not isinstance(value, dict):
            continue
        api = str(value.get("api") or "").strip()
        if not api:
            continue
        normalized_api_site[str(key)] = value
    if not normalized_api_site:
        return None

    custom_category = data.get("custom_category", [])
    if not isinstance(custom_category, list):
        custom_category = []

    return {
        "cache_time": int(data.get("cache_time", DEFAULT_CACHE_TIME)),
        "api_site": normalized_api_site,
        "custom_category": custom_category,
    }


def decode_base58(data: str) -> bytes:
    value = 0
    for char in data.strip():
        if char not in BASE58_INDEX:
            raise ValueError(f"invalid base58 character: {char}")
        value = (value * 58) + BASE58_INDEX[char]
    payload = value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""
    leading_zeros = 0
    for char in data:
        if char == "1":
            leading_zeros += 1
        else:
            break
    return (b"\x00" * leading_zeros) + payload


def encode_base58(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded

    leading_zeros = 0
    for byte in data:
        if byte == 0:
            leading_zeros += 1
        else:
            break
    return ("1" * leading_zeros) + (encoded or "")


def parse_candidate(path: Path) -> tuple[str, dict[str, Any]] | None:
    try:
        raw_text = path.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeDecodeError):
        return None

    if not raw_text:
        return None

    if path.suffix.lower() == ".json":
        try:
            payload = extract_config_payload(json.loads(raw_text))
        except json.JSONDecodeError:
            return None
        if payload:
            return "json", payload
        return None

    if path.suffix.lower() == ".txt":
        try:
            decoded = decode_base58(raw_text).decode("utf-8")
            payload = extract_config_payload(json.loads(decoded))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if payload:
            return "base58-json", payload
    return None


def score_candidate(relative_path: str, parser_name: str, payload: dict[str, Any], source: SourceConfig) -> int:
    lower_path = relative_path.lower()
    basename = Path(relative_path).name.lower()
    api_count = len(payload["api_site"])
    category_count = len(payload.get("custom_category", []))

    score = (min(api_count, 160) * 4) + (min(category_count, 60) * 2)
    if "/" not in relative_path:
        score += 50
    if 20 <= api_count <= 200:
        score += 50
    if api_count > 250:
        score -= 120
    if parser_name == "json":
        score += 15
    if payload.get("custom_category"):
        score += 20
    if any(preferred.lower() == relative_path.lower() or preferred.lower() == basename for preferred in source.preferred_files):
        score += 400
    if basename == "lunatv-config.json":
        score += 240
    elif basename == "config.json":
        score += 200
    elif basename == "input.json":
        score += 180
    elif basename == "output.json":
        score += 120
    elif "config" in basename:
        score += 60
    if "lunatv-config" in lower_path:
        score += 120
    if "full" in basename:
        score += 40
    if any(token in lower_path for token in ["jin18", "jingjian", "lite", "mini", "small"]):
        score -= 220
    if any(token in lower_path for token in ["初始", "initial", "template", "sample"]):
        score -= 260
    if any(token in lower_path for token in ["debug", "status", "report", "package-lock"]):
        score -= 260
    return score


def select_source_config(source: SourceConfig, repo_path: Path) -> SelectedSource:
    candidates: list[CandidateConfig] = []
    for path in iter_candidate_paths(repo_path, source):
        parsed = parse_candidate(path)
        if not parsed:
            continue
        parser_name, payload = parsed
        relative_path = path.relative_to(repo_path).as_posix()
        candidates.append(
            CandidateConfig(
                relative_path=relative_path,
                parser=parser_name,
                api_count=len(payload["api_site"]),
                category_count=len(payload.get("custom_category", [])),
                score=score_candidate(relative_path, parser_name, payload, source),
                payload=payload,
            )
        )

    if not candidates:
        raise RuntimeError("no valid config candidate found")

    candidates.sort(key=lambda item: (item.score, item.api_count, item.category_count, item.relative_path), reverse=True)
    return SelectedSource(config=source, repo_path=repo_path, candidate=candidates[0], candidates=candidates)


def strip_proxy_url(url: str) -> tuple[str, bool]:
    current = url.strip()
    was_proxied = False
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        parsed = urlsplit(current)
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        target_value = None
        for key, value in query_pairs:
            if key.lower() not in {"url", "target", "u", "api"}:
                continue
            decoded = unquote(value).strip()
            if decoded.startswith("http://") or decoded.startswith("https://"):
                target_value = decoded
                break
        if not target_value:
            break
        current = target_value
        was_proxied = True
    return current or url.strip(), was_proxied


def normalize_api_url(url: str) -> tuple[str, bool]:
    stripped_url, was_proxied = strip_proxy_url(url)
    parsed = urlsplit(stripped_url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path)
    if re.search(r"/provide$", path):
        path = f"{path}/vod"
    if not path:
        path = "/"
    filtered_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "ac" and value.lower() == "list":
            continue
        filtered_query.append((key, value))
    filtered_query.sort()
    query = urlencode(filtered_query, doseq=True)
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized, was_proxied


def site_identity(url: str) -> tuple[str, str, str]:
    parsed = urlsplit(url)
    return parsed.netloc.lower(), parsed.path.rstrip("/") or "/", parsed.query


def normalize_detail(detail: str, api: str) -> str:
    candidate = detail.strip()
    if candidate and not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate.lstrip('/')}"
    if candidate:
        parsed = urlsplit(candidate)
        if parsed.netloc:
            scheme = parsed.scheme.lower() or "https"
            path = re.sub(r"/+$", "", parsed.path)
            return urlunsplit((scheme, parsed.netloc.lower(), path, "", ""))
    api_parts = urlsplit(api)
    return f"{api_parts.scheme}://{api_parts.netloc.lower()}"


def clean_name_body(name: str) -> str:
    body = name.strip()
    body = body.replace("🎬", "").replace("🔞", "")
    body = re.sub(r"^(TV|AV视频|AV视频源|AV)\s*[-:_]*\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"^[\-_]+|[\-_]+$", "", body).strip()
    body = re.sub(r"\s+", " ", body)
    body = re.sub(r"\s*-\s*", "-", body)
    body = body.strip("- ").strip()
    return body or name.strip()


def is_adult_name(name: str) -> bool:
    return any(pattern.search(name) for pattern in ADULT_PATTERNS)


def choose_display_name(occurrences: list[SiteOccurrence], adult: bool) -> str:
    body_counter: collections.Counter[str] = collections.Counter()
    body_examples: dict[str, str] = {}
    for occurrence in occurrences:
        body = clean_name_body(occurrence.raw_name)
        body_counter[body] += 1
        body_examples.setdefault(body, occurrence.raw_name)

    ranked_bodies = sorted(
        body_counter,
        key=lambda item: (
            body_counter[item],
            len(re.sub(r"[\W_]+", "", item)),
            -item.count("-"),
            item,
        ),
        reverse=True,
    )
    body = ranked_bodies[0] if ranked_bodies else clean_name_body(occurrences[0].raw_name)
    body = body.replace("  ", " ").strip()
    if body.lower().startswith(("tv", "av")) and len(body) <= 4:
        body = body_examples.get(body, body)
    prefix = "🔞" if adult else "🎬"
    return f"{prefix}{body}"


def choose_api(occurrences: list[SiteOccurrence]) -> str:
    api_counter: collections.Counter[str] = collections.Counter()
    for occurrence in occurrences:
        api_counter[occurrence.api_normalized] += 1

    def api_score(candidate: str) -> tuple[int, int, int, str]:
        parsed = urlsplit(candidate)
        return (
            api_counter[candidate],
            1 if parsed.scheme == "https" else 0,
            0 if parsed.query else 1,
            candidate,
        )

    return max(api_counter, key=api_score)


def choose_detail(occurrences: list[SiteOccurrence], api: str) -> str:
    detail_counter: collections.Counter[str] = collections.Counter()
    for occurrence in occurrences:
        detail_counter[normalize_detail(occurrence.detail, api)] += 1
    return max(detail_counter, key=lambda item: (detail_counter[item], item.startswith("https://"), item))


def make_site_key(api: str, used: set[str]) -> str:
    parsed = urlsplit(api)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    path_tokens = [token for token in parsed.path.strip("/").split("/") if token]
    base = "_".join([host, *path_tokens[-2:]])
    slug = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") or "api"
    if slug not in used:
        used.add(slug)
        return slug
    suffix = hashlib.sha1(api.encode("utf-8")).hexdigest()[:6]
    key = f"{slug}_{suffix}"
    used.add(key)
    return key


def aggregate_sites(selected_sources: list[SelectedSource]) -> tuple[list[SiteRecord], list[dict[str, Any]]]:
    grouped_occurrences: dict[tuple[str, str, str], list[SiteOccurrence]] = collections.defaultdict(list)
    source_categories: list[dict[str, Any]] = []

    for selected in selected_sources:
        payload = selected.candidate.payload
        source_categories.extend(payload.get("custom_category", []))
        for item in payload["api_site"].values():
            raw_name = str(item.get("name") or "").strip()
            raw_api = str(item.get("api") or "").strip()
            if not raw_name or not raw_api:
                continue
            normalized_api, _ = normalize_api_url(raw_api)
            occurrence = SiteOccurrence(
                source_name=selected.config.name,
                source_file=selected.candidate.relative_path,
                raw_name=raw_name,
                api_original=raw_api,
                api_normalized=normalized_api,
                detail=str(item.get("detail") or "").strip(),
                adult=is_adult_name(raw_name),
            )
            grouped_occurrences[site_identity(normalized_api)].append(occurrence)

    site_records: list[SiteRecord] = []
    for occurrences in grouped_occurrences.values():
        source_names = sorted({item.source_name for item in occurrences})
        adult = any(item.adult for item in occurrences)
        api = choose_api(occurrences)
        site_records.append(
            SiteRecord(
                name=choose_display_name(occurrences, adult),
                api=api,
                detail=choose_detail(occurrences, api),
                adult=adult,
                consensus=len(source_names),
                sources=source_names,
                source_files=sorted({f"{item.source_name}:{item.source_file}" for item in occurrences}),
                observed_names=sorted({item.raw_name for item in occurrences}),
            )
        )

    site_records.sort(key=lambda item: (item.adult, -item.consensus, item.name, item.api))
    return site_records, source_categories


def build_config(
    records: list[SiteRecord],
    categories: list[dict[str, Any]],
    cache_time: int,
    allow_adult: bool,
    min_repo_agreement: int,
) -> dict[str, Any]:
    selected_records = [
        record
        for record in records
        if record.consensus >= min_repo_agreement and (allow_adult or not record.adult)
    ]
    api_site: dict[str, dict[str, Any]] = {}
    used_keys: set[str] = set()
    for record in selected_records:
        api_site[make_site_key(record.api, used_keys)] = {
            "name": record.name,
            "api": record.api,
            "detail": record.detail,
        }

    filtered_categories = [
        {"name": item["name"], "type": item["type"], "query": item["query"]}
        for item in categories
        if allow_adult or not item["adult"]
    ]
    return {"cache_time": cache_time, "api_site": api_site, "custom_category": filtered_categories}


def write_json_and_base58(path_json: Path, path_txt: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path_json.write_text(serialized, encoding="utf-8")
    path_txt.write_text(encode_base58(serialized.encode("utf-8")), encoding="utf-8")


def write_alias(source_json: Path, source_txt: Path, alias_json: Path, alias_txt: Path) -> None:
    shutil.copyfile(source_json, alias_json)
    shutil.copyfile(source_txt, alias_txt)


def build_report(
    selected_sources: list[SelectedSource],
    site_records: list[SiteRecord],
    categories: list[dict[str, Any]],
    outputs: dict[str, dict[str, Any]],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "source_repositories": len(selected_sources),
            "unique_api_sites": len(site_records),
            "safe_api_sites": sum(1 for item in site_records if not item.adult),
            "adult_api_sites": sum(1 for item in site_records if item.adult),
            "custom_categories": len(categories),
            "failed_sources": len(errors),
        },
        "sources": [
            {
                "name": selected.config.name,
                "repo": selected.config.repo,
                "ref": selected.config.ref,
                "selected_file": selected.candidate.relative_path,
                "parser": selected.candidate.parser,
                "api_count": selected.candidate.api_count,
                "category_count": selected.candidate.category_count,
                "score": selected.candidate.score,
                "top_candidates": [
                    {
                        "file": candidate.relative_path,
                        "parser": candidate.parser,
                        "api_count": candidate.api_count,
                        "category_count": candidate.category_count,
                        "score": candidate.score,
                    }
                    for candidate in selected.candidates[:5]
                ],
            }
            for selected in selected_sources
        ],
        "outputs": outputs,
        "categories": [
            {"name": item["name"], "type": item["type"], "query": item["query"], "adult": item["adult"]}
            for item in categories
        ],
        "top_sites": [
            {
                "name": record.name,
                "api": record.api,
                "detail": record.detail,
                "adult": record.adult,
                "consensus": record.consensus,
                "sources": record.sources,
                "observed_names": record.observed_names,
            }
            for record in site_records[:40]
        ],
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    config_path = (repo_root / args.config_path).resolve() if not Path(args.config_path).is_absolute() else Path(args.config_path)
    categories_path = (
        (repo_root / args.categories_path).resolve()
        if not Path(args.categories_path).is_absolute()
        else Path(args.categories_path)
    )
    report_path = (repo_root / args.report_path).resolve() if not Path(args.report_path).is_absolute() else Path(args.report_path)

    sources, cache_time, lite_min_repo_agreement = load_sources(config_path)
    if not sources:
        print("No sources configured.", file=sys.stderr)
        return 1

    selected_sources: list[SelectedSource] = []
    errors: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="moontv-aggr-") as temp_dir:
        scratch_dir = Path(temp_dir)
        for source in sources:
            try:
                repo_path = materialize_repo(source, scratch_dir)
                selected_sources.append(select_source_config(source, repo_path))
            except Exception as exc:  # noqa: BLE001
                errors.append({"source": source.name, "repo": source.repo, "error": str(exc)})

    if not selected_sources:
        print("No source repository produced a usable config.", file=sys.stderr)
        for error in errors:
            print(f"- {error['source']}: {error['error']}", file=sys.stderr)
        return 1

    site_records, source_categories = aggregate_sites(selected_sources)
    merged_categories = merge_categories(load_categories(categories_path), source_categories)

    outputs_to_write = {
        "lite": build_config(
            records=site_records,
            categories=merged_categories,
            cache_time=cache_time,
            allow_adult=False,
            min_repo_agreement=lite_min_repo_agreement,
        ),
        "lite_plus18": build_config(
            records=site_records,
            categories=merged_categories,
            cache_time=cache_time,
            allow_adult=True,
            min_repo_agreement=lite_min_repo_agreement,
        ),
        "full": build_config(
            records=site_records,
            categories=merged_categories,
            cache_time=cache_time,
            allow_adult=False,
            min_repo_agreement=1,
        ),
        "full_plus18": build_config(
            records=site_records,
            categories=merged_categories,
            cache_time=cache_time,
            allow_adult=True,
            min_repo_agreement=1,
        ),
    }

    for output_name, payload in outputs_to_write.items():
        json_name, txt_name = OUTPUT_FILES[output_name]
        write_json_and_base58(repo_root / json_name, repo_root / txt_name, payload)

    for output_name, alias_names in ALIASES.items():
        source_json_name, source_txt_name = OUTPUT_FILES[output_name]
        alias_json_name, alias_txt_name = alias_names
        write_alias(
            repo_root / source_json_name,
            repo_root / source_txt_name,
            repo_root / alias_json_name,
            repo_root / alias_txt_name,
        )

    output_report = {
        key: {
            "json": OUTPUT_FILES[key][0],
            "txt": OUTPUT_FILES[key][1],
            "api_count": len(payload["api_site"]),
            "category_count": len(payload["custom_category"]),
        }
        for key, payload in outputs_to_write.items()
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            build_report(
                selected_sources=selected_sources,
                site_records=site_records,
                categories=merged_categories,
                outputs=output_report,
                errors=errors,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Build completed.")
    for output_name, report in output_report.items():
        print(f"- {output_name}: {report['api_count']} APIs, {report['category_count']} categories")
    if errors:
        print(f"- warnings: {len(errors)} source(s) failed, see {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

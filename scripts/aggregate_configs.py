#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_INDEX = {char: index for index, char in enumerate(BASE58_ALPHABET)}
TEXT_EXTENSIONS = {".json", ".txt"}
DEFAULT_CACHE_TIME = 7200
DEFAULT_LITE_MIN_REPO_AGREEMENT = 3
DEFAULT_HEALTH_TIMEOUT_SECONDS = 6.0
DEFAULT_HEALTH_MAX_WORKERS = 16
DEFAULT_HEALTH_ATTEMPTS = 3
DEFAULT_HEALTH_SEARCH_KEYWORDS = ("斗罗", "仙逆")
DEFAULT_HEALTH_ADULT_SEARCH_KEYWORDS = ("斗罗", "无码")
HEALTH_HISTORY_LIMIT = 14
README_HEALTH_START = "<!-- API_HEALTH_REPORT_START -->"
README_HEALTH_END = "<!-- API_HEALTH_REPORT_END -->"
HEALTH_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
HEALTH_VALIDATION_ORDER = {"invalid": 0, "no_results": 1, "valid": 2}
SEARCH_UNSUPPORTED_PATTERNS = (
    "暂不支持搜索",
    "不支持搜索",
    "搜索功能关闭",
    "search not support",
    "not support search",
)
PLAYABLE_MEDIA_URL_PATTERN = re.compile(
    r"https?://[^\"'\s]+(?:\.m3u8|/index\.m3u8|\.mp4|\.flv|\.ts|\.mkv|\.avi)[^\"'\s]*",
    re.IGNORECASE,
)
OUTPUT_FILES = {
    "lite": ("lite.json", "lite.txt"),
    "lite_plus18": ("lite-plus18.json", "lite-plus18.txt"),
    "full": ("full.json", "full.txt"),
    "full_plus18": ("full-plus18.json", "full-plus18.txt"),
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


@dataclasses.dataclass
class HealthCheckResult:
    name: str
    api: str
    detail: str
    adult: bool
    config_type: str
    checked_url: str
    ok: bool
    validation_status: str
    matched_keyword: str
    status_code: int | None
    latency_ms: int | None
    result_count: int
    response_bytes: int
    signature: str
    error: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate MoonTV/LunaTV configs from multiple repositories.")
    parser.add_argument("--config-path", default="config/sources.json", help="Path to the sources config JSON file.")
    parser.add_argument("--report-path", default="build/latest.json", help="Path to the generated build report.")
    parser.add_argument("--readme-path", default="README.md", help="Path to the README file to update.")
    parser.add_argument(
        "--readme-zh-path",
        default="README_zh-CN.md",
        help="Path to the Simplified Chinese README file to update.",
    )
    parser.add_argument(
        "--health-report-path",
        default="build/health-report.json",
        help="Path to the machine-readable health report JSON file.",
    )
    parser.add_argument(
        "--health-history-path",
        default="build/health-history.json",
        help="Path to the rolling API health history JSON file.",
    )
    parser.add_argument(
        "--health-timeout",
        default=DEFAULT_HEALTH_TIMEOUT_SECONDS,
        type=float,
        help="Per-request timeout in seconds for API health checks.",
    )
    parser.add_argument(
        "--health-workers",
        default=DEFAULT_HEALTH_MAX_WORKERS,
        type=int,
        help="Concurrent workers to use for API health checks.",
    )
    parser.add_argument(
        "--health-attempts",
        default=DEFAULT_HEALTH_ATTEMPTS,
        type=int,
        help="Attempts per probe URL during a single health-check round.",
    )
    parser.add_argument(
        "--health-search-keyword",
        action="append",
        default=[],
        help=(
            "Repeatable MoonTVPlus-style search keyword for regular-source validation. "
            f"Defaults to: {', '.join(DEFAULT_HEALTH_SEARCH_KEYWORDS)}."
        ),
    )
    parser.add_argument(
        "--health-adult-search-keyword",
        action="append",
        default=[],
        help=(
            "Repeatable MoonTVPlus-style search keyword for adult-source validation. "
            f"Defaults to: {', '.join(DEFAULT_HEALTH_ADULT_SEARCH_KEYWORDS)}."
        ),
    )
    parser.add_argument(
        "--skip-health-report",
        action="store_true",
        help="Skip API health checks and README report generation.",
    )
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

    return {
        "cache_time": int(data.get("cache_time", DEFAULT_CACHE_TIME)),
        "api_site": normalized_api_site,
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

    score = min(api_count, 160) * 4
    if "/" not in relative_path:
        score += 50
    if 20 <= api_count <= 200:
        score += 50
    if api_count > 250:
        score -= 120
    if parser_name == "json":
        score += 15
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
    if any(token in lower_path for token in ["lite", "mini", "small"]):
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
                score=score_candidate(relative_path, parser_name, payload, source),
                payload=payload,
            )
        )

    if not candidates:
        raise RuntimeError("no valid config candidate found")

    candidates.sort(key=lambda item: (item.score, item.api_count, item.relative_path), reverse=True)
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


def aggregate_sites(selected_sources: list[SelectedSource]) -> list[SiteRecord]:
    grouped_occurrences: dict[tuple[str, str, str], list[SiteOccurrence]] = collections.defaultdict(list)

    for selected in selected_sources:
        payload = selected.candidate.payload
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
    return site_records


def build_config(
    records: list[SiteRecord],
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

    return {"cache_time": cache_time, "api_site": api_site}


def write_json_and_base58(path_json: Path, path_txt: Path, payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path_json.write_text(serialized, encoding="utf-8")
    path_txt.write_text(encode_base58(serialized.encode("utf-8")), encoding="utf-8")


def build_report(
    selected_sources: list[SelectedSource],
    site_records: list[SiteRecord],
    outputs: dict[str, dict[str, Any]],
    errors: list[dict[str, str]],
    health_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "source_repositories": len(selected_sources),
            "unique_api_sites": len(site_records),
            "safe_api_sites": sum(1 for item in site_records if not item.adult),
            "adult_api_sites": sum(1 for item in site_records if item.adult),
            "failed_sources": len(errors),
        },
        "sources": [
            {
                "name": selected.config.name,
                "repo": selected.config.repo,
                "ref": selected.config.ref,
                "parser": selected.candidate.parser,
                "api_count": selected.candidate.api_count,
                "score": selected.candidate.score,
            }
            for selected in selected_sources
        ],
        "outputs": outputs,
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
    if health_summary:
        report["health"] = health_summary
    return report


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def normalize_keyword_list(values: list[str], defaults: tuple[str, ...]) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    candidates = values or list(defaults)
    for value in candidates:
        for token in re.split(r"[,\n]", value):
            keyword = token.strip()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            keywords.append(keyword)
    return keywords or list(defaults)


def build_probe_targets(api: str, keywords: list[str]) -> list[tuple[str, str]]:
    parsed = urlsplit(api)
    params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"ac", "wd", "pg"}
    ]
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for keyword in keywords:
        probe_query = urlencode([*params, ("ac", "videolist"), ("wd", keyword)], doseq=True)
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, probe_query, ""))
        if url in seen:
            continue
        seen.add(url)
        targets.append((url, keyword))
    return targets


def build_api_probe_url(api: str, extra_params: list[tuple[str, str]]) -> str:
    parsed = urlsplit(api)
    params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"ac", "wd", "pg", "ids", "t"}
    ]
    query = urlencode([*params, *extra_params], doseq=True)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def parse_json_body(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8-sig", errors="ignore"))
    except json.JSONDecodeError:
        return None


def extract_json_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    items = payload.get("list")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def extract_class_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    classes = payload.get("class")
    if not isinstance(classes, list):
        return []
    class_ids: list[str] = []
    for item in classes:
        if not isinstance(item, dict):
            continue
        class_id = str(item.get("type_id") or "").strip()
        if class_id:
            class_ids.append(class_id)
    return class_ids


def count_playable_urls(item: dict[str, Any]) -> int:
    play_url = str(item.get("vod_play_url") or "").strip()
    playable_count = 0
    if play_url:
        for group in play_url.split("$$$"):
            for episode in group.split("#"):
                chunk = episode.strip()
                if not chunk:
                    continue
                parts = chunk.split("$", 1)
                url = parts[1].strip() if len(parts) == 2 else parts[0].strip()
                if url.startswith(("http://", "https://")):
                    playable_count += 1
    if playable_count:
        return playable_count
    content = str(item.get("vod_content") or "")
    return len(PLAYABLE_MEDIA_URL_PATTERN.findall(content))


def fetch_probe_response(url: str, timeout_seconds: float) -> dict[str, Any]:
    request = Request(url, headers=HEALTH_REQUEST_HEADERS)
    started_at = perf_counter()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            latency_ms = int((perf_counter() - started_at) * 1000)
            status_code = getattr(response, "status", response.getcode())
            return {
                "checked_url": url,
                "status_code": status_code,
                "latency_ms": latency_ms,
                "response_bytes": len(body),
                "body": body,
                "error": "",
            }
    except HTTPError as error:
        body = error.read()
        latency_ms = int((perf_counter() - started_at) * 1000)
        return {
            "checked_url": url,
            "status_code": error.code,
            "latency_ms": latency_ms,
            "response_bytes": len(body),
            "body": body,
            "error": f"HTTP {error.code}",
        }
    except URLError as error:
        latency_ms = int((perf_counter() - started_at) * 1000)
        reason = getattr(error, "reason", error)
        return {
            "checked_url": url,
            "status_code": None,
            "latency_ms": latency_ms,
            "response_bytes": 0,
            "body": b"",
            "error": str(reason),
        }
    except Exception as error:  # noqa: BLE001
        latency_ms = int((perf_counter() - started_at) * 1000)
        return {
            "checked_url": url,
            "status_code": None,
            "latency_ms": latency_ms,
            "response_bytes": 0,
            "body": b"",
            "error": str(error),
        }


def evaluate_search_response(body: bytes, keyword: str) -> dict[str, Any]:
    text = body.decode("utf-8", errors="ignore").strip()
    lowered = text.lower()
    if any(pattern in text for pattern in SEARCH_UNSUPPORTED_PATTERNS) or any(
        pattern in lowered for pattern in SEARCH_UNSUPPORTED_PATTERNS
    ):
        return {
            "ok": False,
            "validation_status": "invalid",
            "result_count": 0,
            "signature": "search-unsupported",
            "error": "",
        }

    try:
        payload = json.loads(body.decode("utf-8-sig", errors="ignore"))
    except json.JSONDecodeError:
        return {
            "ok": False,
            "validation_status": "invalid",
            "result_count": 0,
            "signature": "invalid-json",
            "error": "",
        }

    items = payload.get("list") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        return {
            "ok": False,
            "validation_status": "no_results",
            "result_count": len(items) if isinstance(items, list) else 0,
            "signature": "empty-list",
            "error": "",
        }

    keyword_lower = keyword.lower()
    if any(keyword_lower in str(item.get("vod_name") or "").lower() for item in items if isinstance(item, dict)):
        return {
            "ok": True,
            "validation_status": "valid",
            "result_count": len(items),
            "signature": "search-hit",
            "error": "",
        }

    return {
        "ok": False,
        "validation_status": "no_results",
        "result_count": len(items),
        "signature": "title-mismatch",
        "error": "",
    }


def probe_rank(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        HEALTH_VALIDATION_ORDER.get(str(candidate.get("validation_status")), -1),
        1 if candidate.get("status_code") and 200 <= int(candidate["status_code"]) < 300 else 0,
        int(candidate.get("result_count") or 0),
        -(candidate.get("latency_ms") or 999999),
    )


def probe_url(url: str, keyword: str, timeout_seconds: float) -> dict[str, Any]:
    response = fetch_probe_response(url, timeout_seconds)
    status_code = response["status_code"]
    if status_code is None or not 200 <= status_code < 300:
        return {
            "checked_url": url,
            "ok": False,
            "validation_status": "invalid",
            "matched_keyword": keyword,
            "status_code": status_code,
            "latency_ms": response["latency_ms"],
            "result_count": 0,
            "response_bytes": response["response_bytes"],
            "signature": "http-error" if status_code is not None else "network-error",
            "error": str(response["error"]),
        }
    evaluation = evaluate_search_response(response["body"], keyword)
    return {
        "checked_url": url,
        "ok": bool(evaluation["ok"]),
        "validation_status": str(evaluation["validation_status"]),
        "matched_keyword": keyword,
        "status_code": status_code,
        "latency_ms": response["latency_ms"],
        "result_count": int(evaluation["result_count"]),
        "response_bytes": response["response_bytes"],
        "signature": str(evaluation["signature"]),
        "error": str(evaluation["error"]),
    }


def resolve_playable_item(api: str, items: list[dict[str, Any]], timeout_seconds: float) -> dict[str, Any] | None:
    for item in items:
        playable_count = count_playable_urls(item)
        if playable_count > 0:
            return {
                "checked_url": "",
                "ok": True,
                "validation_status": "valid",
                "matched_keyword": "",
                "status_code": 200,
                "latency_ms": 0,
                "result_count": playable_count,
                "response_bytes": 0,
                "signature": "playable-fallback-list",
                "error": "",
            }

    for item in items:
        vod_id = str(item.get("vod_id") or "").strip()
        if not vod_id:
            continue
        detail_url = build_api_probe_url(api, [("ac", "videolist"), ("ids", vod_id)])
        detail_response = fetch_probe_response(detail_url, timeout_seconds)
        status_code = detail_response["status_code"]
        if status_code is None or not 200 <= status_code < 300:
            continue
        payload = parse_json_body(detail_response["body"])
        detail_items = extract_json_list(payload)
        if not detail_items:
            continue
        playable_count = count_playable_urls(detail_items[0])
        if playable_count <= 0:
            continue
        return {
            "checked_url": detail_url,
            "ok": True,
            "validation_status": "valid",
            "matched_keyword": "",
            "status_code": status_code,
            "latency_ms": detail_response["latency_ms"],
            "result_count": playable_count,
            "response_bytes": detail_response["response_bytes"],
            "signature": "playable-fallback-detail",
            "error": "",
        }

    return None


def probe_playable_fallback(api: str, timeout_seconds: float) -> dict[str, Any] | None:
    fallback_url = build_api_probe_url(api, [("ac", "videolist"), ("pg", "1")])
    fallback_response = fetch_probe_response(fallback_url, timeout_seconds)
    status_code = fallback_response["status_code"]
    if status_code is not None and 200 <= status_code < 300:
        payload = parse_json_body(fallback_response["body"])
        items = extract_json_list(payload)
        resolved = resolve_playable_item(api, items, timeout_seconds)
        if resolved:
            resolved["checked_url"] = resolved["checked_url"] or fallback_url
            resolved["latency_ms"] = (resolved["latency_ms"] or 0) + (fallback_response["latency_ms"] or 0)
            resolved["response_bytes"] = max(int(resolved["response_bytes"]), fallback_response["response_bytes"])
            return resolved

    class_url = build_api_probe_url(api, [("ac", "list")])
    class_response = fetch_probe_response(class_url, timeout_seconds)
    status_code = class_response["status_code"]
    if status_code is None or not 200 <= status_code < 300:
        return None
    payload = parse_json_body(class_response["body"])
    class_ids = extract_class_ids(payload)
    for class_id in class_ids[:3]:
        category_url = build_api_probe_url(api, [("ac", "videolist"), ("t", class_id), ("pg", "1")])
        category_response = fetch_probe_response(category_url, timeout_seconds)
        status_code = category_response["status_code"]
        if status_code is None or not 200 <= status_code < 300:
            continue
        payload = parse_json_body(category_response["body"])
        items = extract_json_list(payload)
        resolved = resolve_playable_item(api, items, timeout_seconds)
        if resolved:
            resolved["checked_url"] = resolved["checked_url"] or category_url
            resolved["latency_ms"] = (resolved["latency_ms"] or 0) + (category_response["latency_ms"] or 0)
            resolved["response_bytes"] = max(int(resolved["response_bytes"]), category_response["response_bytes"])
            return resolved
    return None


def probe_site(
    record: SiteRecord,
    timeout_seconds: float,
    config_type: str,
    max_attempts: int,
    search_keywords: list[str],
    adult_search_keywords: list[str],
) -> HealthCheckResult:
    keywords = adult_search_keywords if record.adult else search_keywords
    best_result: dict[str, Any] | None = None
    for url, keyword in build_probe_targets(record.api, keywords):
        for _ in range(max(1, max_attempts)):
            candidate = probe_url(url, keyword, timeout_seconds)
            if best_result is None or probe_rank(candidate) > probe_rank(best_result):
                best_result = candidate
            if candidate["ok"]:
                break
        if best_result and best_result["ok"]:
            break

    if best_result is None or not best_result["ok"]:
        fallback_candidate = probe_playable_fallback(record.api, timeout_seconds)
        if fallback_candidate and (best_result is None or probe_rank(fallback_candidate) > probe_rank(best_result)):
            best_result = fallback_candidate

    assert best_result is not None
    return HealthCheckResult(
        name=record.name,
        api=record.api,
        detail=record.detail,
        adult=record.adult,
        config_type=config_type,
        checked_url=best_result["checked_url"],
        ok=bool(best_result["ok"]),
        validation_status=str(best_result["validation_status"]),
        matched_keyword=str(best_result["matched_keyword"]),
        status_code=best_result["status_code"],
        latency_ms=best_result["latency_ms"],
        result_count=int(best_result["result_count"]),
        response_bytes=int(best_result["response_bytes"]),
        signature=str(best_result["signature"]),
        error=str(best_result["error"]),
    )


def run_health_checks(
    records: list[SiteRecord],
    timeout_seconds: float,
    max_workers: int,
    lite_min_repo_agreement: int,
    max_attempts: int,
    search_keywords: list[str],
    adult_search_keywords: list[str],
) -> list[HealthCheckResult]:
    if not records:
        return []

    workers = max(1, min(max_workers, len(records)))
    results: list[HealthCheckResult] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(
                probe_site,
                record,
                timeout_seconds,
                classify_config_type(record, lite_min_repo_agreement),
                max_attempts,
                search_keywords,
                adult_search_keywords,
            ): record.api
            for record in records
        }
        for future in as_completed(future_map):
            results.append(future.result())
    results.sort(key=lambda item: (item.ok, item.name.lower(), item.api))
    return results


def classify_config_type(record: SiteRecord, lite_min_repo_agreement: int) -> str:
    if record.adult:
        return "plus18"
    if record.consensus >= lite_min_repo_agreement:
        return "lite"
    return "full"


def update_health_history(history_path: Path, results: list[HealthCheckResult], generated_at: str) -> dict[str, Any]:
    previous = load_optional_json(history_path).get("apis", {})
    current: dict[str, Any] = {}
    for result in results:
        previous_entry = previous.get(result.api, {})
        samples = previous_entry.get("history", [])
        if not isinstance(samples, list):
            samples = []
        samples.append(
            {
                "timestamp": generated_at,
                "ok": result.ok,
                "validation_status": result.validation_status,
                "status_code": result.status_code,
                "latency_ms": result.latency_ms,
                "matched_keyword": result.matched_keyword,
                "result_count": result.result_count,
                "response_bytes": result.response_bytes,
                "signature": result.signature,
                "error": result.error,
                "checked_url": result.checked_url,
            }
        )
        current[result.api] = {
            "name": result.name,
            "detail": result.detail,
            "adult": result.adult,
            "config_type": result.config_type,
            "history": samples[-HEALTH_HISTORY_LIMIT:],
        }

    payload = {
        "generated_at": generated_at,
        "samples_kept": HEALTH_HISTORY_LIMIT,
        "apis": current,
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def format_report_timestamp(timestamp: str) -> str:
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return timestamp
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def evaluate_history_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    success_count = sum(1 for sample in samples if sample.get("ok"))
    failure_count = max(0, len(samples) - success_count)
    availability_rate = (success_count / len(samples)) if samples else 0.0
    consecutive_failures = 0
    for sample in reversed(samples):
        if sample.get("ok"):
            break
        consecutive_failures += 1

    if consecutive_failures >= 3:
        health_state = "unhealthy"
        status = "❌"
        output_enabled = False
    elif failure_count > 0:
        health_state = "subhealthy"
        status = "⚠️"
        output_enabled = True
    else:
        health_state = "healthy"
        status = "✅"
        output_enabled = True

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "availability_rate": availability_rate,
        "consecutive_failures": consecutive_failures,
        "health_state": health_state,
        "status": status,
        "output_enabled": output_enabled,
    }


def build_health_policy(history_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    policy: dict[str, dict[str, Any]] = {}
    for api, entry in history_payload.get("apis", {}).items():
        samples = entry.get("history", [])
        if not isinstance(samples, list):
            samples = []
        policy[api] = evaluate_history_samples(samples)
    return policy


def summarize_history(history_payload: dict[str, Any], results: list[HealthCheckResult]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result_map = {result.api: result for result in results}
    rows: list[dict[str, Any]] = []
    rates: list[float] = []
    healthy_count = subhealthy_count = unhealthy_count = enabled_count = 0

    for api, entry in history_payload.get("apis", {}).items():
        samples = entry.get("history", [])
        if not isinstance(samples, list):
            samples = []
        evaluation = evaluate_history_samples(samples)
        rates.append(evaluation["availability_rate"])
        current = result_map[api]
        if evaluation["health_state"] == "healthy":
            healthy_count += 1
        elif evaluation["health_state"] == "subhealthy":
            subhealthy_count += 1
        else:
            unhealthy_count += 1
        if evaluation["output_enabled"]:
            enabled_count += 1

        if current.signature in {"playable-fallback-list", "playable-fallback-detail"}:
            result_text = f"{current.status_code or 200} / {current.signature} / {current.result_count} playable links"
        elif current.validation_status == "valid":
            result_text = f"{current.status_code or 200} / valid / wd={current.matched_keyword} / {current.result_count} results"
        elif current.validation_status == "no_results":
            result_text = (
                f"{current.status_code or 200} / {current.signature} / "
                f"wd={current.matched_keyword} / {current.result_count} results"
            )
        elif current.status_code is not None:
            if current.status_code >= 400:
                result_text = f"HTTP {current.status_code} / wd={current.matched_keyword}"
            else:
                result_text = f"{current.status_code} / {current.signature} / wd={current.matched_keyword}"
        else:
            result_text = current.error or current.signature

        rows.append(
            {
                "status": evaluation["status"],
                "health_state": evaluation["health_state"],
                "output_enabled": evaluation["output_enabled"],
                "type": str(entry.get("config_type", current.config_type)),
                "name": entry.get("name", current.name),
                "api": api,
                "checked_url": current.checked_url,
                "validation_status": current.validation_status,
                "matched_keyword": current.matched_keyword,
                "result_count": current.result_count,
                "result": result_text,
                "latency_ms": current.latency_ms,
                "success_count": evaluation["success_count"],
                "failure_count": evaluation["failure_count"],
                "availability_rate": evaluation["availability_rate"],
                "trend": "".join("✅" if sample.get("ok") else "❌" for sample in samples[-7:]) or "—",
                "consecutive_failures": evaluation["consecutive_failures"],
                "adult": bool(entry.get("adult", current.adult)),
            }
        )

    type_order = {"lite": 0, "full": 1, "plus18": 2}
    health_order = {"healthy": 0, "subhealthy": 1, "unhealthy": 2}

    rows.sort(
        key=lambda item: (
            health_order.get(item["health_state"], 99),
            type_order.get(item["type"], 99),
            -item["availability_rate"],
            item["consecutive_failures"],
            item["name"],
        )
    )

    summary = {
        "generated_at": history_payload.get("generated_at"),
        "target_file": OUTPUT_FILES["full_plus18"][0],
        "total_apis": len(results),
        "current_success": sum(1 for result in results if result.ok),
        "current_failure": sum(1 for result in results if not result.ok),
        "enabled_apis": enabled_count,
        "healthy_apis": healthy_count,
        "subhealthy_apis": subhealthy_count,
        "unhealthy_apis": unhealthy_count,
        "average_availability_rate": (sum(rates) / len(rates)) if rates else 0.0,
    }
    return summary, rows


def render_health_report_markdown_localized(summary: dict[str, Any], rows: list[dict[str, Any]], language: str) -> str:
    is_zh = language.lower().startswith("zh")
    search_keywords = " / ".join(summary.get("search_keywords", [])) or "—"
    adult_search_keywords = " / ".join(summary.get("adult_search_keywords", [])) or "—"
    if is_zh:
        lines = [
            f"### API 状态（最近更新：{format_report_timestamp(summary['generated_at'])}）",
            "",
            "- 检测范围：全部聚合源",
            "- 输出规则：连续三轮检测失败的源会从所有输出文件中剔除",
            "- 检测方式：优先采用 MoonTVPlus 同款搜索校验（`ac=videolist&wd=关键词`），若源不支持搜索但默认列表/详情可提取播放地址，仍视为有效",
            f"- 普通源关键词：{search_keywords}",
            f"- 成人源关键词：{adult_search_keywords}",
            "- 重试策略：按关键词顺序尝试，单个关键词可重试多次，降低瞬时误判",
            f"- API 数量：{summary['enabled_apis']}/{summary['total_apis']}",
            "",
            "<details>",
            "<summary>展开查看全部 API 明细</summary>",
            "",
            "| 状态 | 类型 | API 名称 | API 地址 | 结果 | 可用率 | 最近7次趋势 |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    else:
        lines = [
            f"### API Status (Last Updated: {format_report_timestamp(summary['generated_at'])})",
            "",
            "- Scope: all aggregated APIs",
            "- Output rule: sources failing 3 consecutive rounds are removed from all output files",
            "- Validation mode: MoonTVPlus-style search checks run first, but search-disabled sources are still kept when listing/detail endpoints expose playable URLs",
            f"- Safe-source keywords: {search_keywords}",
            f"- Adult-source keywords: {adult_search_keywords}",
            "- Retry mode: keywords are tried in order and each request may be retried to reduce transient false negatives",
            f"- API Count: {summary['enabled_apis']}/{summary['total_apis']}",
            "",
            "<details>",
            "<summary>Expand full API details</summary>",
            "",
            "| Status | Type | API Name | API URL | Result | Availability | Last 7 Samples |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]

    for row in rows:
        lines.append(
            "| {status} | {type} | {name} | `{api}` | {result} | {rate:.1f}% | {trend} |".format(
                status=row["status"],
                type=row["type"],
                name=escape_markdown_cell(str(row["name"])),
                api=row["api"],
                result=escape_markdown_cell(str(row["result"])),
                rate=row["availability_rate"] * 100,
                trend=row["trend"],
            )
        )

    lines.extend(["", "</details>"])
    return "\n".join(lines)


def update_readme_health_report(readme_path: Path, markdown_block: str, language: str) -> None:
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
    else:
        content = "# MoonTV Aggregator Config\n"

    replacement = f"{README_HEALTH_START}\n{markdown_block}\n{README_HEALTH_END}"
    if README_HEALTH_START in content and README_HEALTH_END in content:
        content = re.sub(
            rf"{re.escape(README_HEALTH_START)}.*?{re.escape(README_HEALTH_END)}",
            replacement,
            content,
            flags=re.DOTALL,
        )
    else:
        suffix = "\n" if content.endswith("\n") else "\n\n"
        if language.lower().startswith("zh"):
            content = (
                f"{content}{suffix}## API 健康报告\n\n"
                "以下数据由 GitHub Actions 自动生成，检测目标为 `full-plus18.json` 中的全部 API。\n\n"
                f"{replacement}\n"
            )
        else:
            content = (
                f"{content}{suffix}## API Health Report\n\n"
                "The data below is generated automatically by GitHub Actions and checks every API in `full-plus18.json`.\n\n"
                f"{replacement}\n"
            )
    readme_path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    config_path = (repo_root / args.config_path).resolve() if not Path(args.config_path).is_absolute() else Path(args.config_path)
    report_path = (repo_root / args.report_path).resolve() if not Path(args.report_path).is_absolute() else Path(args.report_path)
    readme_path = (repo_root / args.readme_path).resolve() if not Path(args.readme_path).is_absolute() else Path(args.readme_path)
    readme_zh_path = (
        (repo_root / args.readme_zh_path).resolve()
        if not Path(args.readme_zh_path).is_absolute()
        else Path(args.readme_zh_path)
    )
    health_report_path = (
        (repo_root / args.health_report_path).resolve()
        if not Path(args.health_report_path).is_absolute()
        else Path(args.health_report_path)
    )
    health_history_path = (
        (repo_root / args.health_history_path).resolve()
        if not Path(args.health_history_path).is_absolute()
        else Path(args.health_history_path)
    )

    sources, cache_time, lite_min_repo_agreement = load_sources(config_path)
    if not sources:
        print("No sources configured.", file=sys.stderr)
        return 1
    health_search_keywords = normalize_keyword_list(
        list(args.health_search_keyword),
        DEFAULT_HEALTH_SEARCH_KEYWORDS,
    )
    health_adult_search_keywords = normalize_keyword_list(
        list(args.health_adult_search_keyword),
        DEFAULT_HEALTH_ADULT_SEARCH_KEYWORDS,
    )

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

    site_records = aggregate_sites(selected_sources)
    history_payload = load_optional_json(health_history_path)
    health_policy = build_health_policy(history_payload)
    health_summary: dict[str, Any] | None = None

    if not args.skip_health_report:
        print(f"Running API health checks for {len(site_records)} APIs...")
        health_results = run_health_checks(
            records=site_records,
            timeout_seconds=max(0.5, args.health_timeout),
            max_workers=max(1, args.health_workers),
            lite_min_repo_agreement=lite_min_repo_agreement,
            max_attempts=max(1, args.health_attempts),
            search_keywords=health_search_keywords,
            adult_search_keywords=health_adult_search_keywords,
        )
        generated_at = datetime.now(timezone.utc).isoformat()
        history_payload = update_health_history(health_history_path, health_results, generated_at)
        health_policy = build_health_policy(history_payload)
        health_summary, health_rows = summarize_history(history_payload, health_results)
        health_summary["validation_mode"] = "moontvplus-search"
        health_summary["search_keywords"] = health_search_keywords
        health_summary["adult_search_keywords"] = health_adult_search_keywords
        health_report_payload = {
            "generated_at": generated_at,
            "summary": health_summary,
            "items": health_rows,
        }
        health_report_path.parent.mkdir(parents=True, exist_ok=True)
        health_report_path.write_text(
            json.dumps(health_report_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        update_readme_health_report(
            readme_path,
            render_health_report_markdown_localized(health_summary, health_rows, "en"),
            "en",
        )
        update_readme_health_report(
            readme_zh_path,
            render_health_report_markdown_localized(health_summary, health_rows, "zh-CN"),
            "zh-CN",
        )

    filtered_site_records = [
        record for record in site_records if health_policy.get(record.api, {"output_enabled": True})["output_enabled"]
    ]

    outputs_to_write = {
        "lite": build_config(
            records=filtered_site_records,
            cache_time=cache_time,
            allow_adult=False,
            min_repo_agreement=lite_min_repo_agreement,
        ),
        "lite_plus18": build_config(
            records=filtered_site_records,
            cache_time=cache_time,
            allow_adult=True,
            min_repo_agreement=lite_min_repo_agreement,
        ),
        "full": build_config(
            records=filtered_site_records,
            cache_time=cache_time,
            allow_adult=False,
            min_repo_agreement=1,
        ),
        "full_plus18": build_config(
            records=filtered_site_records,
            cache_time=cache_time,
            allow_adult=True,
            min_repo_agreement=1,
        ),
    }

    for output_name, payload in outputs_to_write.items():
        json_name, txt_name = OUTPUT_FILES[output_name]
        write_json_and_base58(repo_root / json_name, repo_root / txt_name, payload)

    output_report = {
        key: {
            "json": OUTPUT_FILES[key][0],
            "txt": OUTPUT_FILES[key][1],
            "api_count": len(payload["api_site"]),
        }
        for key, payload in outputs_to_write.items()
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            build_report(
                selected_sources=selected_sources,
                site_records=site_records,
                outputs=output_report,
                errors=errors,
                health_summary=health_summary,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Build completed.")
    for output_name, report in output_report.items():
        print(f"- {output_name}: {report['api_count']} APIs")
    if health_summary:
        print(
            f"- health states: {health_summary['healthy_apis']} healthy, "
            f"{health_summary['subhealthy_apis']} subhealthy, "
            f"{health_summary['unhealthy_apis']} unhealthy, "
            f"{health_summary['enabled_apis']}/{health_summary['total_apis']} published "
            f"at {health_summary['generated_at']}"
        )
    if errors:
        print(f"- warnings: {len(errors)} source(s) failed, see {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

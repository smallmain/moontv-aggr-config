[English](README.md) | [简体中文](README_zh-CN.md)

# MoonTV Aggregator Config

Automatically aggregates multiple MoonTV/LunaTV config repositories into one continuously updated config set.

This repository does more than mirror upstream files:

- clones and scans multiple upstream repositories
- detects the most likely primary config file instead of assuming one fixed path
- normalizes `api`, `name`, and `detail`
- unwraps proxy-style URLs such as `?url=...` back to the real API endpoint
- deduplicates and ranks entries by cross-repo consensus
- outputs four config variants
- runs MoonTVPlus-style search validation and writes the latest report back into both README files

## Output Files

Each build generates:

- `lite.json` / `lite.txt`
  Safe-only sources with a higher cross-repo consensus threshold.
- `lite-plus18.json` / `lite-plus18.txt`
  Lite set including adult sources.
- `full.json` / `full.txt`
  Full safe-only set.
- `full-plus18.json` / `full-plus18.txt`
  Full set including adult sources.

`*.txt` files are Base58-encoded versions of the corresponding JSON payloads.

Build metadata is written to [latest.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/latest.json), and API health data is written to [health-report.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/health-report.json) and [health-history.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/health-history.json).

## Local Usage

```bash
python3 scripts/aggregate_configs.py
```

Useful options:

```bash
python3 scripts/aggregate_configs.py \
  --config-path config/sources.json \
  --report-path build/latest.json
```

Override the default MoonTVPlus-style validation keywords:

```bash
python3 scripts/aggregate_configs.py \
  --health-search-keyword 斗罗 \
  --health-search-keyword 仙逆 \
  --health-adult-search-keyword 斗罗 \
  --health-adult-search-keyword 无码
```

Skip API health checks and only rebuild config files:

```bash
python3 scripts/aggregate_configs.py --skip-health-report
```

## Upstream Sources

Edit [sources.json](/Users/smallmain/Documents/Work/moontv-aggr-config/config/sources.json) to change upstream repositories.

Supported fields:

- `repo`: `https://github.com/owner/repo`, `https://github.com/owner/repo.git`, or a local directory path
- `ref`: optional branch or tag
- `preferred_files`: optional hints for unusual repository layouts

The current default upstream set is:

- `hafrey1/LunaTV-config`
- `qianqikun/LunaTV-config`
- `vodtv/api`
- `oooopera/moontv_config`
- `heardic/shipinyuan`

## How It Works

The aggregator follows this pipeline:

1. Scan `.json` and Base58 `.txt` files in each upstream repository.
2. Detect candidate files that contain `api_site`.
3. Score candidates by filename, depth, and site count.
4. Select the most likely primary config file.
5. Normalize API URLs by removing proxy wrappers, trimming noisy suffixes, and fixing obvious `/provide` endpoints.
6. Merge entries by normalized API identity.
7. Detect adult sources from naming patterns.
8. Generate the four output variants.
9. Validate aggregated APIs with MoonTVPlus-style `ac=videolist&wd=<keyword>` searches before publishing.

The `lite` variant is not copied from any single upstream repository. It is built from APIs that appear across multiple upstream sources, which makes it more stable as upstream projects change.

## GitHub Actions

Two workflows are included:

### 1. Daily Config Refresh

[update-config.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/update-config.yml)

- runs on a daily schedule
- supports manual dispatch
- rebuilds configs
- refreshes the API health report in both README files
- commits and pushes changes back to this repository when needed

### 2. Remote Deployment

[deploy-remote.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/deploy-remote.yml)

- runs after config files change on `main`
- supports manual dispatch
- uploads build artifacts to a remote server via `sftp`, `ftps`, or `ftp`

Recommended repository variable:

- `DEPLOY_PROTOCOL`: `sftp`, `ftps`, or `ftp` (defaults to `sftp`)
- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USERNAME`
- `DEPLOY_REMOTE_DIR`

Required GitHub secrets:

- `DEPLOY_PASSWORD` for password-based `sftp`, `ftps`, or `ftp`
- `DEPLOY_PRIVATE_KEY` for key-based `sftp`

`DEPLOY_HOST`, `DEPLOY_PORT`, `DEPLOY_USERNAME`, and `DEPLOY_REMOTE_DIR` can be configured in either repository variables or secrets.

## Subscription URLs

After pushing to GitHub, raw files can be used directly:

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/full-plus18.txt
https://raw.githubusercontent.com/<owner>/<repo>/main/lite.txt
```

## API Health Report

The data below is generated automatically by GitHub Actions and tracks all aggregated APIs before publishing.

<!-- API_HEALTH_REPORT_START -->
### API Status (Last Updated: 2026-03-17 05:03:17 UTC)

- Scope: all aggregated APIs
- Output rule: sources failing 3 consecutive rounds are removed from all output files
- Validation mode: MoonTVPlus-style search checks run first, but search-disabled sources are still kept when listing/detail endpoints expose playable URLs
- Safe-source keywords: 斗罗 / 仙逆
- Adult-source keywords: 斗罗 / 无码
- Retry mode: keywords are tried in order and each request may be retried to reduce transient false negatives
- API Count: 112/143

<details>
<summary>Expand full API details</summary>

| Status | Type | API Name | API URL | Result | Availability | Last 7 Samples |
| --- | --- | --- | --- | --- | ---: | --- |
| ✅ | lite | 🎬360 资源 | `https://360zyzz.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬360资源 | `https://360zy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬U酷影视 | `https://api.ukuapi88.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬U酷资源 | `https://api.ukuapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬iKun资源 | `https://ikunzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬优质资源 | `https://api.yzzy-api.com/inc/apijson.php` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬如意资源 | `https://cj.rycjapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 11 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬新浪资源 | `https://api.xinlangapi.com/xinlangapi.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬无尽资源 | `https://api.wujinapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬无尽资源 | `https://api.wujinapi.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬暴风资源 | `https://bfzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬最大点播 | `https://zuidazy.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬最大资源 | `https://api.zuidapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬极速资源 | `https://jszyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬爱奇艺 | `https://iqiyizyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬猫眼资源 | `https://api.maoyanapi.top/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬电影天堂 | `http://caiji.dyttzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬百度云zy | `https://api.apibdzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬红牛资源 | `https://www.hongniuzy2.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬艾旦影视 | `https://lovedan.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬茅台资源 | `https://caiji.maotaizy.cc/api.php/provide/vod` | 200 / playable-fallback-list / 2 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬虎牙资源 | `https://www.huyaapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬豆瓣资源 | `https://caiji.dbzy5.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬量子资源 | `https://cj.lzcaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬量子资源 | `https://cj.lziapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬金蝉影视 | `https://zy.jinchancaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 30 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬金鹰点播 | `https://jinyingzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬非凡资源 | `https://api.ffzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬飘零资源 | `https://p2100.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 17 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬魔都动漫 | `https://caiji.moduapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬魔都资源 | `https://www.mdzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬789官采资源站采集接口 | `https://www.caiji.cyou/api.php/provide/vod` | 200 / valid / wd=斗罗 / 40 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬Ikun资源（备用） | `https://www.ikunzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬OK资源采集网采集接口 | `http://api.okzyw.net/api.php/provide/vod` | 200 / playable-fallback-list / 14 playable links | 100.0% | ✅✅ |
| ✅ | full | 🎬ikun资源 | `https://ikunzyapi.com/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬旺旺短剧 | `https://www.wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬猫眼资源 | `https://api.maoyanapi.top/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬神马云 | `https://api.1080zyku.com/inc/apijson.php` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬索尼资源 | `https://www.suoniapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 6 playable links | 100.0% | ✅✅✅ |
| ✅ | full | 🎬红牛 | `https://www.hongniuzy2.com/api.php/provide/vod/at/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬红牛资源3 | `https://www.hongniuzy3.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬虎牙 | `https://www.huyaapi.com/api.php/provide/vod/from/hym3u8` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬虎牙资源 | `https://www.huyaapi.com/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬豆瓣\|点播 | `https://caiji.dbzy.tv/api.php/provide/vod/at/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬豆瓣资源 | `https://caiji.dbzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬豆瓣资源 | `https://dbzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源 | `https://jyzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源 | `https://jyzyapi.com/provide/vod/from/jinyingyun/at/json` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源采集网 | `https://jyzyapi.com/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬非凡资源 | `https://cj.ffzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬黄色资源啊啊 | `https://hsckzy888.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 6 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞155资源 | `https://155api.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 18 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞AIvin | `http://lbapiby.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞CK资源 | `https://ckzy.me/api.php/provide/vod` | 200 / valid / wd=无码 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞jkun资源 | `https://jkunzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 22 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞souavZY | `https://api.souavzyw.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞乐播资源 | `https://lbapi9.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞优优资源 | `https://www.yyzywcj.com/api.php/provide/vod` | 200 / valid / wd=无码 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞大奶子 | `https://apidanaizi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞奶香资源 | `https://naixxzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 5 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞小鸡资源 | `https://api.xiaojizy.live/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞桃花资源 | `https://thzy1.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞森林资源 | `https://beiyong.slapibf.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞淫水机资源 | `https://www.xrbsp.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞玉兔资源 | `https://apiyutu.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞番号资源 | `http://fhapi9.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞白嫖资源 | `https://www.kxgav.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞百万资源 | `https://api.bwzyz.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞精品资源 | `https://www.jingpinx.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 8 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞细胞资源 | `https://www.xxibaozyw.com/api.php/provide/vod` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞美少女 | `https://www.msnii.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞老色逼 | `https://apilsbzy1.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞辣椒资源 | `https://apilj.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞香奶儿资源 | `https://www.gdlsp.com/api/json.php` | 200 / valid / wd=斗罗 / 2 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞香蕉资源 | `https://www.xiangjiaozyw.com/api.php/provide/vod` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞鲨鱼资源 | `https://shayuapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞麻豆视频 | `https://91md.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 2 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黄AVZY | `https://www.pgxdy.com/api/json.php` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黄色仓库 | `https://hsckzy.xyz/api.php/provide/vod` | 200 / valid / wd=斗罗 / 6 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黑料资源 | `https://www.heiliaozyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 22 results | 100.0% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬光速资源 | `https://api.guangsuapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 20 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬卧龙点播 | `https://collect.wolongzyw.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬卧龙资源 | `https://wolongzyw.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬天涯资源 | `https://tyyszy.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬快车资源 | `https://caiji.kuaichezy.org/api.php/provide/vod` | 200 / playable-fallback-list / 14 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬旺旺短剧 | `https://wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬旺旺资源 | `https://api.wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬樱花资源 | `https://m3u8.apiyhzy.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬索尼资源 | `https://suoniapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 6 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬豪华资源 | `https://hhzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 20 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬速播资源 | `https://subocaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬闪电资源 | `https://xsd.sdzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 14 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬鸭鸭资源 | `https://cj.yayazy.net/api.php/provide/vod` | 200 / playable-fallback-list / 6 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬1080资源 | `https://api.1080zyku.com/inc/api_mac10.php` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬1080资源 | `https://api.yzzy-api.com/inc/api_mac10.php` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬wujinapi无尽 | `https://api.wujinapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬优质资源库 | `https://api.yzzy-api.com/inc/api_mac10_all.php` | 200 / playable-fallback-list / 2 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬卧龙资源 | `https://collect.wolongzy.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬天涯影视 | `https://tyyszyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬建安资源站 | `http://154.219.117.232:9981/jacloudapi.php/provide/vod` | 200 / playable-fallback-list / 1558 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬无尽资源 | `https://api.wujinapi.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬无水印资源网采集接口 | `https://api.wsyzy.net/api.php/provide/vod` | 200 / playable-fallback-list / 10 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬牛牛点播 | `https://api.niuniuzy.me/api.php/provide/vod` | 200 / playable-fallback-list / 6 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬速播资源 | `https://subocj.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | full | 🎬閃電资源 | `https://sdzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 14 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | plus18 | 🔞森林资源 | `https://slapibf.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅❌✅ |
| ⚠️ | plus18 | 🔞滴滴资源 | `https://api.ddapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 2 results | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | plus18 | 🔞色猫资源 | `https://caiji.semaozy.net/inc/apijson_vod.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 92.9% | ✅✅✅✅✅✅✅ |
| ⚠️ | plus18 | 🔞豆豆资源 | `https://api.douapi.cc/api.php/provide/vod` | HTTP 500 / wd=无码 | 92.9% | ✅✅✅✅✅✅❌ |
| ⚠️ | plus18 | 🔞丝袜资源 | `https://siwazyw.tv/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 85.7% | ✅✅✅✅✅✅✅ |
| ⚠️ | plus18 | 🔞丝袜资源 | `https://siwazyw.tv/api.php/provide/vod/at/json` | 200 / playable-fallback-list / 1 playable links | 85.7% | ✅✅✅✅✅✅✅ |
| ⚠️ | plus18 | 🔞奥斯卡 | `https://aosikazy.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 85.7% | ✅✅✅✅✅✅✅ |
| ❌ | full | 🎬1080源 | `https://api.1080zyku.com/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬优质资源库1080zyk6.com高清 | `https://api.yzzy-api.com/inc/ldg_api_all.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬大地资源网络 | `https://dadiapi.com/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬步步高资源 | `https://api.yparse.com/api/json` | HTTP 403 / wd=仙逆 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬茶杯狐 | `http://caihy.zone.id/%E8%8C%B6%E6%9D%AF%E7%8B%90.php?filter=true` | 200 / empty-list / wd=仙逆 / 0 results | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬麒麟资源站全站采集接口 | `https://www.qilinzyz.com/api.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬iqiyi资源 | `https://www.iqiyizyapi.com/api.php/provide/vod` | [Errno -5] No address associated with hostname | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬七七影视 | `https://www.qiqidys.com/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬华为吧资源 | `https://huawei8.live/api.php/provide/vod` | The read operation timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬小猫咪资源 | `https://zy.xmm.hk/api.php/provide/vod` | [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1016) | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬山海资源 | `https://zy.sh0o.cn/api.php/provide/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬快播资源网站 | `https://gayapi.com/api.php/provide/vod` | [Errno 111] Connection refused | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬淘片资源 | `https://taopianapi.com/cjapi/sda/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬爱短剧.cc | `https://www.aiduanju.cc/` | Remote end closed connection without response | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬番茄资源 | `https://api.fqzy.cc/api.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬蜂巢片库 | `https://api.fczy888.me/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬金马资源网 | `https://api.jmzy.com/api.php/provide/vod` | HTTP 444 / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬饭团影视 | `https://www.fantuan.tv/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬魔爪资源 | `https://mozhuazy.com/api.php/provide/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬黑木耳 | `https://json.heimuer.xyz/api.php/provide/vod` | [Errno -3] Temporary failure in name resolution | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬黑木耳点播 | `https://json02.heimuer.xyz/api.php/provide/vod` | [Errno -3] Temporary failure in name resolution | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞大地资源 | `https://dadiapi.com/feifei` | 200 / title-mismatch / wd=无码 / 35 results | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞大地资源 | `https://dadiapi.com/feifei2` | 200 / title-mismatch / wd=无码 / 35 results | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞杏吧资源 | `https://xingba111.com/api.php/provide/vod` | HTTP 403 / wd=无码 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞杏吧资源 | `https://xingba222.com/api.php/provide/vod` | HTTP 403 / wd=无码 | 7.1% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞91-精品 | `https://91jpzyw.com/api.php/provide/vod` | HTTP 521 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞souav资源 | `https://api.souavzy.vip/api.php/provide/vod` | HTTP 404 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞幸资源 | `https://xzybb2.com/api.php/provide/vod` | The read operation timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞最色资源 | `https://api.zuiseapi.com/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞色南国 | `https://api.sexnguon.com/api.php/provide/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞色猫资源 | `https://api.maozyapi.com/inc/apijson_vod.php` | HTTP 521 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |

</details>
<!-- API_HEALTH_REPORT_END -->

## References

This project is informed by the structure and output style of:

- <https://github.com/hafrey1/LunaTV-config>
- <https://github.com/qianqikun/LunaTV-config>
- <https://github.com/vodtv/api>
- <https://github.com/oooopera/moontv_config>
- <https://github.com/heardic/shipinyuan>

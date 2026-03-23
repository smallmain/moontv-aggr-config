[English](README.md) | [简体中文](README_zh-CN.md)

# MoonTV Aggregator Config

自动聚合多个 MoonTV/LunaTV 配置仓库，生成一套持续更新的统一配置。

这个仓库不只是简单转存上游文件，还会做这些事：

- 自动克隆并扫描多个上游仓库
- 自动识别最可能的主配置文件，而不是假设固定路径
- 统一清洗 `api`、`name`、`detail`
- 将 `?url=...` 这类代理包装地址还原为真实 API
- 按跨仓库共识度去重并排序
- 输出四种配置变体
- 自动执行 MoonTVPlus 风格的搜索有效性检测，并把最新报告写回两份 README

## 输出文件

每次构建会生成：

- `lite.json` / `lite.txt`
  仅普通源，且采用更高的跨仓库共识阈值。
- `lite-plus18.json` / `lite-plus18.txt`
  精简版，包含成人源。
- `full.json` / `full.txt`
  完整版，仅普通源。
- `full-plus18.json` / `full-plus18.txt`
  完整版，包含成人源。

`*.txt` 文件是对应 JSON 的 Base58 编码版本。

构建元数据会写入 [latest.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/latest.json)，API 健康数据会写入 [health-report.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/health-report.json) 和 [health-history.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/health-history.json)。

## 本地使用

```bash
python3 scripts/aggregate_configs.py
```

常用参数：

```bash
python3 scripts/aggregate_configs.py \
  --config-path config/sources.json \
  --report-path build/latest.json
```

如果想覆盖默认的 MoonTVPlus 风格检测关键词：

```bash
python3 scripts/aggregate_configs.py \
  --health-search-keyword 斗罗 \
  --health-search-keyword 仙逆 \
  --health-adult-search-keyword 斗罗 \
  --health-adult-search-keyword 无码
```

如果只想重建配置，不跑 API 健康检测：

```bash
python3 scripts/aggregate_configs.py --skip-health-report
```

## 上游仓库配置

编辑 [sources.json](/Users/smallmain/Documents/Work/moontv-aggr-config/config/sources.json) 即可调整上游仓库。

支持的字段：

- `repo`：`https://github.com/owner/repo`、`https://github.com/owner/repo.git`，或本地目录路径
- `ref`：可选，指定分支或标签
- `preferred_files`：可选，用于处理特殊仓库结构的优先文件提示

当前默认上游为：

- `hafrey1/LunaTV-config`
- `qianqikun/LunaTV-config`
- `vodtv/api`
- `oooopera/moontv_config`
- `heardic/shipinyuan`

## 工作原理

聚合流程如下：

1. 扫描每个上游仓库里的 `.json` 和 Base58 `.txt` 文件。
2. 找出包含 `api_site` 的候选配置。
3. 按文件名、层级深度和站点数量打分。
4. 选择最像主配置的文件。
5. 归一化 API 地址，移除代理包装、清洗噪声后缀，并修正明显缺失的 `/provide` 端点。
6. 按归一化后的 API 身份合并条目。
7. 基于命名模式识别成人源。
8. 生成四种输出版本。
9. 发布前按 MoonTVPlus 同款 `ac=videolist&wd=<keyword>` 搜索校验聚合 API。

`lite` 版本不是照搬某个单独的上游仓库，而是从多个上游都出现的 API 中构建出来，因此面对上游变化更稳。

## GitHub Actions

仓库内包含两个工作流：

### 1. 每日配置更新

[update-config.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/update-config.yml)

- 每日定时运行
- 支持手动触发
- 自动重建配置
- 自动刷新两份 README 中的 API 健康报告
- 如有变化则自动提交并推送回当前仓库

### 2. 远程发布

[deploy-remote.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/deploy-remote.yml)

- `main` 分支配置文件变更后自动运行
- 支持手动触发
- 支持通过 `sftp`、`ftps` 或 `ftp` 将产物上传到远程服务器

推荐配置仓库变量：

- `DEPLOY_PROTOCOL`：`sftp`、`ftps` 或 `ftp`，默认是 `sftp`
- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USERNAME`
- `DEPLOY_REMOTE_DIR`

需要配置这些 GitHub Secrets：

- `DEPLOY_PASSWORD`：用于密码登录的 `sftp`、`ftps`、`ftp`
- `DEPLOY_PRIVATE_KEY`：用于基于密钥的 `sftp`

`DEPLOY_HOST`、`DEPLOY_PORT`、`DEPLOY_USERNAME`、`DEPLOY_REMOTE_DIR` 可以放在仓库变量或 Secrets 中。

## 订阅链接

推送到 GitHub 后，可以直接使用 Raw 文件地址：

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/full-plus18.txt
https://raw.githubusercontent.com/<owner>/<repo>/main/lite.txt
```

## API 健康报告

以下数据由 GitHub Actions 自动生成，会在发布前跟踪全部聚合 API 的健康状态。

<!-- API_HEALTH_REPORT_START -->
### API 状态（最近更新：2026-03-23 05:15:11 UTC）

- 检测范围：全部聚合源
- 输出规则：连续三轮检测失败的源会从所有输出文件中剔除
- 检测方式：优先采用 MoonTVPlus 同款搜索校验（`ac=videolist&wd=关键词`），若源不支持搜索但默认列表/详情可提取播放地址，仍视为有效
- 普通源关键词：斗罗 / 仙逆
- 成人源关键词：斗罗 / 无码
- 重试策略：按关键词顺序尝试，单个关键词可重试多次，降低瞬时误判
- API 数量：116/149

<details>
<summary>展开查看全部 API 明细</summary>

| 状态 | 类型 | API 名称 | API 地址 | 结果 | 可用率 | 最近7次趋势 |
| --- | --- | --- | --- | --- | ---: | --- |
| ✅ | lite | 🎬360 资源 | `https://360zyzz.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬360资源 | `https://360zy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬U酷影视 | `https://api.ukuapi88.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬U酷资源 | `https://api.ukuapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬iKun资源 | `https://ikunzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬优质资源 | `https://api.yzzy-api.com/inc/apijson.php` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬光速资源 | `https://api.guangsuapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 48 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬卧龙点播 | `https://collect.wolongzyw.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬卧龙资源 | `https://wolongzyw.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬天涯资源 | `https://tyyszy.com/api.php/provide/vod` | 200 / playable-fallback-list / 20 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬如意资源 | `https://cj.rycjapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 11 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬快车资源 | `https://caiji.kuaichezy.org/api.php/provide/vod` | 200 / playable-fallback-list / 83 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬新浪资源 | `https://api.xinlangapi.com/xinlangapi.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬无尽资源 | `https://api.wujinapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬无尽资源 | `https://api.wujinapi.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬旺旺短剧 | `https://wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬旺旺资源 | `https://api.wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬暴风资源 | `https://bfzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬最大点播 | `https://zuidazy.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬最大资源 | `https://api.zuidapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬极速资源 | `https://jszyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬樱花资源 | `https://m3u8.apiyhzy.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬爱奇艺 | `https://iqiyizyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬猫眼资源 | `https://api.maoyanapi.top/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬电影天堂 | `http://caiji.dyttzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬百度云zy | `https://api.apibdzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬索尼资源 | `https://suoniapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 10 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬红牛资源 | `https://www.hongniuzy2.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬茅台资源 | `https://caiji.maotaizy.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬虎牙资源 | `https://www.huyaapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬豆瓣资源 | `https://caiji.dbzy5.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬豪华资源 | `https://hhzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 48 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬速播资源 | `https://subocaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬量子资源 | `https://cj.lzcaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬量子资源 | `https://cj.lziapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬金蝉影视 | `https://zy.jinchancaiji.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 30 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬金鹰点播 | `https://jinyingzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬闪电资源 | `https://xsd.sdzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 8 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬非凡资源 | `https://api.ffzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬飘零资源 | `https://p2100.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 17 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬魔都动漫 | `https://caiji.moduapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | lite | 🎬鸭鸭资源 | `https://cj.yayazy.net/api.php/provide/vod` | 200 / playable-fallback-list / 141 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬1080资源 | `https://api.1080zyku.com/inc/api_mac10.php` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬1080资源 | `https://api.yzzy-api.com/inc/api_mac10.php` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬789官采资源站采集接口 | `https://www.caiji.cyou/api.php/provide/vod` | 200 / valid / wd=斗罗 / 40 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬Ikun资源（备用） | `https://www.ikunzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬OK资源采集网采集接口 | `http://api.okzyw.net/api.php/provide/vod` | 200 / playable-fallback-list / 142 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬ikun资源 | `https://ikunzyapi.com/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 15 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬wujinapi无尽 | `https://api.wujinapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬优质资源库 | `https://api.yzzy-api.com/inc/api_mac10_all.php` | 200 / playable-fallback-list / 2 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬卧龙资源 | `https://collect.wolongzy.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬天涯影视 | `https://tyyszyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 20 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬建安资源站 | `http://154.219.117.232:9981/jacloudapi.php/provide/vod` | 200 / playable-fallback-list / 24 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬新浪 | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅ |
| ✅ | full | 🎬无尽资源 | `https://api.wujinapi.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬无水印资源网采集接口 | `https://api.wsyzy.net/api.php/provide/vod` | 200 / playable-fallback-list / 41 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬旺旺短剧 | `https://www.wwzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬牛牛点播 | `https://api.niuniuzy.me/api.php/provide/vod` | 200 / playable-fallback-list / 11 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬猫眼资源 | `https://api.maoyanapi.top/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 13 results | 100.0% | ✅ |
| ✅ | full | 🎬神马云 | `https://api.1080zyku.com/inc/apijson.php` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬索尼资源 | `https://www.suoniapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 10 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬红牛 | `https://www.hongniuzy2.com/api.php/provide/vod/at/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬红牛资源3 | `https://www.hongniuzy3.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬聚合资源 | `https://vod.korge.cn/kapi.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅ |
| ✅ | full | 🎬茅台资源 | `https://caiji.maotaizy.cc/api.php/provide/vod/at/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅ |
| ✅ | full | 🎬虎牙 | `https://www.huyaapi.com/api.php/provide/vod/from/hym3u8` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬虎牙资源 | `https://www.huyaapi.com/api.php/provide/vod/at/json` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬豆瓣\|点播 | `https://caiji.dbzy.tv/api.php/provide/vod/at/josn` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅ |
| ✅ | full | 🎬豆瓣资源 | `https://caiji.dbzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬豆瓣资源 | `https://dbzy.tv/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬速播资源 | `https://subocj.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源 | `https://jyzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源 | `https://jyzyapi.com/provide/vod/from/jinyingm3u8/at/json` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源 | `https://jyzyapi.com/provide/vod/from/jinyingyun/at/json` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬金鹰资源采集网 | `https://jyzyapi.com/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬閃電资源 | `https://sdzyapi.com/api.php/provide/vod` | 200 / playable-fallback-list / 8 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬非凡资源 | `https://cj.ffzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | full | 🎬黄色资源啊啊 | `https://hsckzy888.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 6 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞155资源 | `https://155api.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 18 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞CK资源 | `https://ckzy.me/api.php/provide/vod` | 200 / valid / wd=无码 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞jkun资源 | `https://jkunzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 22 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞souavZY | `https://api.souavzyw.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞丝袜资源 | `https://siwazyw.tv/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞丝袜资源 | `https://siwazyw.tv/api.php/provide/vod/at/json` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞乐播资源 | `https://lbapi9.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞优优资源 | `https://www.yyzywcj.com/api.php/provide/vod` | 200 / valid / wd=无码 / 10 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞大奶子 | `https://apidanaizi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞奥斯卡 | `https://aosikazy.com/api.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞奶香资源 | `https://naixxzy.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 5 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞小鸡资源 | `https://api.xiaojizy.live/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞桃花资源 | `https://thzy1.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 16 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞森林资源 | `https://beiyong.slapibf.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞淫水机资源 | `https://www.xrbsp.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞滴滴资源 | `https://api.ddapi.cc/api.php/provide/vod` | 200 / valid / wd=斗罗 / 2 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞玉兔资源 | `https://apiyutu.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞番号资源 | `http://fhapi9.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞白嫖资源 | `https://www.kxgav.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞百万资源 | `https://api.bwzyz.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞精品资源 | `https://www.jingpinx.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 8 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞细胞资源 | `https://www.xxibaozyw.com/api.php/provide/vod` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞美少女 | `https://www.msnii.com/api/json.php` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞老色逼 | `https://apilsbzy1.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞色猫资源 | `https://caiji.semaozy.net/inc/apijson_vod.php/provide/vod` | 200 / playable-fallback-list / 1 playable links | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞辣椒资源 | `https://apilj.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞香奶儿资源 | `https://www.gdlsp.com/api/json.php` | 200 / valid / wd=斗罗 / 2 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞香蕉资源 | `https://www.xiangjiaozyw.com/api.php/provide/vod` | 200 / valid / wd=无码 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞鲨鱼资源 | `https://shayuapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞麻豆视频 | `https://91md.me/api.php/provide/vod` | 200 / valid / wd=斗罗 / 2 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黄AVZY | `https://www.pgxdy.com/api/json.php` | 200 / valid / wd=斗罗 / 1 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黄色仓库 | `https://hsckzy.xyz/api.php/provide/vod` | 200 / valid / wd=斗罗 / 6 results | 100.0% | ✅✅✅✅✅✅✅ |
| ✅ | plus18 | 🔞黑料资源 | `https://www.heiliaozyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 22 results | 100.0% | ✅✅✅✅✅✅✅ |
| ⚠️ | lite | 🎬艾旦影视 | `https://lovedan.net/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅❌✅✅✅✅✅ |
| ⚠️ | lite | 🎬魔都资源 | `https://www.mdzyapi.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅❌✅✅✅✅✅ |
| ⚠️ | full | 🎬雨哥哥资源 | `http://cj.baozi66.top:66/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 0.0% | ❌❌ |
| ⚠️ | plus18 | 🔞AIvin | `http://lbapiby.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅❌✅ |
| ⚠️ | plus18 | 🔞森林资源 | `https://slapibf.com/api.php/provide/vod` | 200 / valid / wd=斗罗 / 20 results | 92.9% | ✅✅✅✅✅✅✅ |
| ❌ | full | 🎬U酷资源 | `https://api.ukuapi88.com/api.php/provide/art` | 200 / title-mismatch / wd=斗罗 / 2 results | 0.0% | ❌❌❌❌❌❌ |
| ❌ | full | 🎬1080源 | `https://api.1080zyku.com/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬iqiyi资源 | `https://www.iqiyizyapi.com/api.php/provide/vod` | [Errno -5] No address associated with hostname | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬七七影视 | `https://www.qiqidys.com/api.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬优质资源库1080zyk6.com高清 | `https://api.yzzy-api.com/inc/ldg_api_all.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬华为吧资源 | `https://huawei8.live/api.php/provide/vod` | The read operation timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬大地资源网络 | `https://dadiapi.com/api.php/provide/vod` | 200 / invalid-json / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬小猫咪资源 | `https://zy.xmm.hk/api.php/provide/vod` | [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: certificate has expired (_ssl.c:1016) | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬山海资源 | `https://zy.sh0o.cn/api.php/provide/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬快播资源网站 | `https://gayapi.com/api.php/provide/vod` | [Errno 111] Connection refused | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬步步高资源 | `https://api.yparse.com/api/json` | HTTP 403 / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬淘片资源 | `https://taopianapi.com/cjapi/sda/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬爱短剧.cc | `https://www.aiduanju.cc/` | Remote end closed connection without response | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬番茄资源 | `https://api.fqzy.cc/api.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬茶杯狐 | `http://caihy.zone.id/%E8%8C%B6%E6%9D%AF%E7%8B%90.php?filter=true` | 200 / empty-list / wd=仙逆 / 0 results | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬蜂巢片库 | `https://api.fczy888.me/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬金马资源网 | `https://api.jmzy.com/api.php/provide/vod` | HTTP 520 / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬饭团影视 | `https://www.fantuan.tv/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬魔爪资源 | `https://mozhuazy.com/api.php/provide/vod` | [Errno 111] Connection refused | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬麒麟资源站全站采集接口 | `https://www.qilinzyz.com/api.php/provide/vod` | 200 / invalid-json / wd=仙逆 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬黑木耳 | `https://json.heimuer.xyz/api.php/provide/vod` | [Errno -3] Temporary failure in name resolution | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | full | 🎬黑木耳点播 | `https://json02.heimuer.xyz/api.php/provide/vod` | [Errno -3] Temporary failure in name resolution | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞豆豆资源 | `https://api.douapi.cc/api.php/provide/vod` | HTTP 500 / wd=无码 | 50.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞91-精品 | `https://91jpzyw.com/api.php/provide/vod` | HTTP 521 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞souav资源 | `https://api.souavzy.vip/api.php/provide/vod` | The read operation timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞大地资源 | `https://dadiapi.com/feifei` | 200 / title-mismatch / wd=无码 / 35 results | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞大地资源 | `https://dadiapi.com/feifei2` | 200 / title-mismatch / wd=无码 / 35 results | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞幸资源 | `https://xzybb2.com/api.php/provide/vod` | The read operation timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞最色资源 | `https://api.zuiseapi.com/api.php/provide/vod` | [Errno -2] Name or service not known | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞杏吧资源 | `https://xingba111.com/api.php/provide/vod` | HTTP 403 / wd=斗罗 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞杏吧资源 | `https://xingba222.com/api.php/provide/vod` | HTTP 403 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞色南国 | `https://api.sexnguon.com/api.php/provide/vod` | timed out | 0.0% | ❌❌❌❌❌❌❌ |
| ❌ | plus18 | 🔞色猫资源 | `https://api.maozyapi.com/inc/apijson_vod.php` | HTTP 521 / wd=无码 | 0.0% | ❌❌❌❌❌❌❌ |

</details>
<!-- API_HEALTH_REPORT_END -->

## 参考来源

这个项目参考了以下仓库的结构和输出方式：

- <https://github.com/hafrey1/LunaTV-config>
- <https://github.com/qianqikun/LunaTV-config>
- <https://github.com/vodtv/api>
- <https://github.com/oooopera/moontv_config>
- <https://github.com/heardic/shipinyuan>

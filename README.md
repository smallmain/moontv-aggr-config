# MoonTV Aggregator Config

自动聚合多个 MoonTV/LunaTV 配置仓库，生成一套可持续更新的统一配置。

这个仓库不是简单转存上游文件，而是做了几件事：

- 自动克隆并扫描多个上游仓库
- 智能识别最可能的主配置文件，而不是写死单一路径
- 统一清洗 `api`、`name`、`detail`
- 自动去掉上游代理壳，将 `?url=` 形式的中转地址还原为真实 API
- 按来源仓库共识度去重、排序，并输出 4 套配置
- 生成兼容常见 LunaTV 命名的别名文件

## 输出文件

每次构建会生成以下文件：

- `lite.json` / `lite.txt`
  仅普通源，且只保留至少被多个上游仓库共同收录的来源
- `lite-plus18.json` / `lite-plus18.txt`
  精简版，包含普通源和 18+ 源
- `full.json` / `full.txt`
  完整版，仅普通源
- `full-plus18.json` / `full-plus18.txt`
  完整版，包含普通源和 18+ 源

兼容别名：

- `jin18.json` / `jin18.txt` 指向精简禁 18 版本
- `jingjian.json` / `jingjian.txt` 指向精简 + 18 版本
- `LunaTV-config.json` / `LunaTV-config.txt` 指向完整 + 18 版本

`*.txt` 文件是对应 JSON 的 Base58 编码，可直接用于订阅链接。

每次构建的来源识别结果、候选文件打分和最终统计都会写入 [build/latest.json](/Users/smallmain/Documents/Work/moontv-aggr-config/build/latest.json)。

## 本地使用

```bash
python3 scripts/aggregate_configs.py
```

可选参数：

```bash
python3 scripts/aggregate_configs.py \
  --config-path config/sources.json \
  --categories-path config/categories.json \
  --report-path build/latest.json
```

## 配置上游仓库

编辑 [config/sources.json](/Users/smallmain/Documents/Work/moontv-aggr-config/config/sources.json) 即可：

- `repo`: 支持 `https://github.com/owner/repo`、`https://github.com/owner/repo.git`，也支持本地目录路径
- `ref`: 可选，指定分支或标签
- `preferred_files`: 可选，仓库结构特殊时可显式提高某些文件的优先级

默认已经包含这 5 个上游仓库：

- `hafrey1/LunaTV-config`
- `qianqikun/LunaTV-config`
- `vodtv/api`
- `oooopera/moontv_config`
- `heardic/shipinyuan`

## 生成规则

聚合脚本默认按下面的逻辑工作：

1. 扫描仓库内的 `.json` 和 Base58 `.txt` 文件
2. 找出包含 `api_site` 的候选配置
3. 按文件名、目录层级、站点数量、是否携带分类等信号打分
4. 选择最像“主配置”的文件
5. 对所有站点做归一化：
   - 还原代理后的真实 API
   - 去掉结尾多余斜杠
   - 清洗 `?ac=list`
   - 对明显缺失 `/vod` 的 `provide` 地址做补全
6. 以“同一个真实 API”为维度聚合
7. 根据名称特征识别是否为 18+ 源
8. 生成四个输出版本

精简版不是硬编码某个上游仓库的结果，而是按 `lite_min_repo_agreement` 选择被多个仓库共同收录的 API。这种方式在上游增删时更稳。

## GitHub Actions

仓库内包含两个工作流：

### 1. 每日更新配置

[update-config.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/update-config.yml)

- 每日自动执行一次
- 也支持手动触发
- 自动运行聚合脚本
- 若配置有变更，则自动提交并推送回当前仓库

### 2. 通过 SFTP 发布配置

[deploy-sftp.yml](/Users/smallmain/Documents/Work/moontv-aggr-config/.github/workflows/deploy-sftp.yml)

- 监听配置文件变更后自动执行
- 也支持手动触发
- 使用原生 `sftp` 上传到指定服务器目录

需要设置这些 GitHub Secrets：

- `SFTP_HOST`
- `SFTP_PORT`
- `SFTP_USERNAME`
- `SFTP_PRIVATE_KEY`
- `SFTP_REMOTE_DIR`

## 订阅链接

推送到 GitHub 后，可使用仓库 Raw 文件地址作为订阅来源，例如：

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/full-plus18.txt
https://raw.githubusercontent.com/<owner>/<repo>/main/lite.txt
```

如果你想兼容现有 LunaTV 配置链接习惯，也可以使用：

```text
https://raw.githubusercontent.com/<owner>/<repo>/main/LunaTV-config.txt
https://raw.githubusercontent.com/<owner>/<repo>/main/jingjian.txt
https://raw.githubusercontent.com/<owner>/<repo>/main/jin18.txt
```

## 参考来源

项目适配并吸收了以下仓库的输出格式和组织方式：

- <https://github.com/hafrey1/LunaTV-config>
- <https://github.com/qianqikun/LunaTV-config>
- <https://github.com/vodtv/api>
- <https://github.com/oooopera/moontv_config>
- <https://github.com/heardic/shipinyuan>

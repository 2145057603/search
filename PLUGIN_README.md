# astrbot_plugin_github_repo_analyzer

一个 AstrBot 插件，用来在 GitHub 海量仓库中搜索你想要的项目，并把结果整理后返回给机器人。

## 功能

- `/repo_find <关键词>`
  - 直接搜索 GitHub 仓库。
- `/repo_find_preset <名称>`
  - 使用插件配置里的预设搜索词搜索。
- `/repo_find_list`
  - 查看当前已配置的预设搜索词。

## 安装

把本目录放到 AstrBot 的 `data/plugins/` 下，然后在 AstrBot WebUI 中安装或重载插件。

## 配置

- `github_token`
  - 可选，建议填写细粒度只读 Token，降低匿名搜索限流影响。
- `request_timeout_seconds`
  - GitHub API 请求超时秒数。
- `result_limit`
  - 每次最多返回多少条结果。
- `sort_by`
  - 搜索排序字段，默认 `stars`。
- `sort_order`
  - 排序方向，默认 `desc`。
- `preset_queries`
  - JSON 对象，格式如下：

```json
{
  "modloader": "slay the spire mod loader",
  "astrbot": "astrbot plugin"
}
```

## 输出内容

每个搜索结果会输出：

- 仓库名
- GitHub 地址
- 简介
- Star 数
- 主语言
- 所有者类型
- 最近更新时间
- Topics
- 是否为 archived / fork

## 说明

这个插件现在做的是“找仓库并输出结果”，不是深入解析单个仓库源码内容。如果你下一步想要的是：

- 在搜索结果里再筛选“最适合下载/接入”的仓库
- 读取仓库 README 后做摘要
- 搜索某类文件或某段代码

也可以继续在这个插件上往下扩展。

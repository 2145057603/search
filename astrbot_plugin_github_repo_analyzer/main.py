import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


API_BASE = "https://api.github.com"


@dataclass
class RepoSearchResult:
    full_name: str
    html_url: str
    description: str
    stars: int
    language: str
    updated_at: str
    topics: list[str]
    owner_type: str
    archived: bool
    fork: bool


@register(
    "astrbot_plugin_github_repo_analyzer",
    "Codex",
    "在 GitHub 海量仓库中搜索目标项目，并整理结果返回给机器人。",
    "0.2.0",
    "https://github.com/example/astrbot_plugin_github_repo_analyzer",
)
class GithubRepoAnalyzerPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.timeout = aiohttp.ClientTimeout(
            total=int(self.config.get("request_timeout_seconds", 20))
        )

    @filter.command("repo_find")
    async def find_repositories(self, event: AstrMessageEvent):
        raw = event.message_str.strip()
        query = self._extract_argument(raw, "repo_find")
        if not query:
            yield event.plain_result(
                "用法: /repo_find <关键词>\n例如: /repo_find slay the spire mod loader"
            )
            return

        report = await self._search_and_format(query)
        yield event.plain_result(report)

    @filter.command("repo_find_preset")
    async def find_repositories_by_preset(self, event: AstrMessageEvent):
        raw = event.message_str.strip()
        preset_name = self._extract_argument(raw, "repo_find_preset")
        if not preset_name:
            presets = self._load_preset_queries()
            if not presets:
                yield event.plain_result(
                    "当前没有预设搜索词。请先在插件配置 `preset_queries` 中填写 JSON。"
                )
                return

            names = ", ".join(sorted(presets.keys()))
            yield event.plain_result(
                f"可用预设: {names}\n用法: /repo_find_preset <预设名>"
            )
            return

        presets = self._load_preset_queries()
        query = presets.get(preset_name)
        if not query:
            yield event.plain_result(
                f"未找到预设 `{preset_name}`。请先执行 /repo_find_preset 查看可用项。"
            )
            return

        report = await self._search_and_format(query, preset_name=preset_name)
        yield event.plain_result(report)

    @filter.command("repo_find_list")
    async def list_presets(self, event: AstrMessageEvent):
        presets = self._load_preset_queries()
        if not presets:
            yield event.plain_result(
                "当前没有预设搜索词。请在插件配置 `preset_queries` 中填写 JSON。"
            )
            return

        lines = ["已配置预设搜索词:"]
        for key, value in sorted(presets.items()):
            lines.append(f"- {key}: {value}")
        yield event.plain_result("\n".join(lines))

    async def _search_and_format(
        self, query: str, preset_name: str | None = None
    ) -> str:
        try:
            payload = await self._search_repositories(query)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 403:
                return (
                    "GitHub API 请求被拒绝，可能触发了匿名访问限流。\n"
                    "建议在插件配置中填写 `github_token` 后重试。"
                )
            logger.warning("GitHub search error for %s: %s", query, exc)
            return f"搜索失败，HTTP {exc.status}。"
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to search repositories for %s: %s", query, exc)
            return f"搜索失败: {type(exc).__name__}: {exc}"

        items = payload.get("items") or []
        if not items:
            return f"没有找到和 `{query}` 相关的仓库。"

        results = [self._parse_repo(item) for item in items]
        title = f"预设 `{preset_name}` 的搜索结果" if preset_name else "GitHub 搜索结果"
        lines = [
            title,
            f"关键词: {query}",
            f"总匹配数: {payload.get('total_count', 0)}",
            "",
        ]

        for idx, repo in enumerate(results, start=1):
            lines.extend(self._format_repo_block(idx, repo))
            lines.append("")

        return "\n".join(lines).rstrip()

    async def _search_repositories(self, query: str) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.config.get(
                "user_agent",
                "astrbot-plugin-github-repo-analyzer/0.2.0",
            ),
        }
        token = str(self.config.get("github_token", "")).strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        per_page = max(1, min(10, int(self.config.get("result_limit", 5))))
        sort_by = str(self.config.get("sort_by", "stars")).strip() or "stars"
        order = str(self.config.get("sort_order", "desc")).strip() or "desc"

        url = (
            f"{API_BASE}/search/repositories?q={quote_plus(query)}"
            f"&sort={quote_plus(sort_by)}&order={quote_plus(order)}&per_page={per_page}"
        )
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

    def _parse_repo(self, payload: dict[str, Any]) -> RepoSearchResult:
        return RepoSearchResult(
            full_name=payload.get("full_name", ""),
            html_url=payload.get("html_url", ""),
            description=payload.get("description") or "",
            stars=int(payload.get("stargazers_count") or 0),
            language=payload.get("language") or "未知",
            updated_at=payload.get("updated_at") or "",
            topics=list(payload.get("topics") or []),
            owner_type=((payload.get("owner") or {}).get("type") or "Unknown"),
            archived=bool(payload.get("archived", False)),
            fork=bool(payload.get("fork", False)),
        )

    def _format_repo_block(self, index: int, repo: RepoSearchResult) -> list[str]:
        flags: list[str] = []
        if repo.archived:
            flags.append("archived")
        if repo.fork:
            flags.append("fork")
        flags_text = f" [{', '.join(flags)}]" if flags else ""

        topic_text = ", ".join(repo.topics[:5]) if repo.topics else "无"
        updated_text = self._format_updated_at(repo.updated_at)
        return [
            f"{index}. {repo.full_name}{flags_text}",
            f"   地址: {repo.html_url}",
            f"   描述: {repo.description or '无'}",
            f"   Stars: {repo.stars} | 语言: {repo.language} | 所有者: {repo.owner_type}",
            f"   最近更新: {updated_text}",
            f"   Topics: {topic_text}",
        ]

    def _load_preset_queries(self) -> dict[str, str]:
        raw = self.config.get("preset_queries", "{}")
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items()}

        text = str(raw).strip()
        if not text:
            return {}

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("preset_queries is not valid JSON")
            return {}

        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}

    def _extract_argument(self, message: str, command_name: str) -> str:
        parts = message.split(maxsplit=1)
        if not parts:
            return ""

        first = parts[0].lstrip("/")
        if first != command_name:
            return ""
        return parts[1].strip() if len(parts) > 1 else ""

    def _format_updated_at(self, updated_at: str) -> str:
        if not updated_at:
            return "未知"
        try:
            dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return updated_at

        days = max(0, (datetime.now(timezone.utc) - dt).days)
        return f"{updated_at} ({days} 天前)"

    async def terminate(self):
        logger.info("astrbot_plugin_github_repo_analyzer terminated")

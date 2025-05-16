import re
from typing import Pattern
from aiogram.utils.text_decorations import TextDecoration



class DiscordDecoration(TextDecoration):
    MARKDOWN_QUOTE_PATTERN: Pattern[str] = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

    def link(self, value: str, link: str) -> str:
        return f"[{value}]({link})"

    def bold(self, value: str) -> str:
        return f"**{value}**"

    def italic(self, value: str) -> str:
        return f"_\r{value}_\r"

    def code(self, value: str) -> str:
        return f"`{value}`"

    def pre(self, value: str) -> str:
        return f"```\n{value}\n```"

    def pre_language(self, value: str, language: str) -> str:
        return f"```{language}\n{value}\n```"

    def underline(self, value: str) -> str:
        return f"__\r{value}__\r"

    def strikethrough(self, value: str) -> str:
        return f"~~{value}~~"

    def spoiler(self, value: str) -> str:
        return f"||{value}||"

    def quote(self, value: str) -> str:
        return re.sub(pattern=self.MARKDOWN_QUOTE_PATTERN, repl=r"\\\1", string=value)

    def custom_emoji(self, value: str, custom_emoji_id: str) -> str:
        return custom_emoji_id

    def blockquote(self, value: str) -> str:
        return "\n".join(f"> {line}" for line in value.splitlines())

    def expandable_blockquote(self, value: str) -> str:
        return self.blockquote(self, value)


discord_decoration = DiscordDecoration()
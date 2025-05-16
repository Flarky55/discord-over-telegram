from abc import abstractmethod
from aiogram.types import Message as TgMessage, MessageEntity
from discord import Message as DsMessage
from aiogram.utils.text_decorations import MarkdownDecoration


WRAP_STRINGS = {
    "bold": "**",
    "italic": "*",
    "underline": "__",
    "strikethrough": "~~",
    "spoiler": "||",
    "code": "`",
    "pre": "```"
}


class Transformer:
    def __init__(self, entity: MessageEntity):
        self.start  = entity.offset
        self.end    = self.start + entity.length
    
    def __lt__(self, other: "Transformer"):
        return self.start < other.start
    
    @abstractmethod
    def transform(self, content: str) -> str:
        pass


class WrapTransformer(Transformer):
    def __init__(self, entity: MessageEntity):
        super().__init__(entity)

        self.str = WRAP_STRINGS[entity.type]

    def transform(self, content):
        return content[:self.start] + self.str + content[self.start:self.end] + self.str + content[self.end:]

class PreWrapTransformer(WrapTransformer):
    def __init__(self, entity):
        super().__init__(entity)

        self.language = entity.language

    def transform(self, content):
        return content[:self.start] + self.str + self.language + "\n" + content[self.start:self.end] + self.str + content[self.end:]


class QuoteTransformer(Transformer):
    def transform(self, content):
        entity_content = content[self.start:self.end]
        entity_content = entity_content.replace("\n", "\n> ")

        return content[:self.start] + "> " + entity_content + content[self.end:]


def telegram_to_discord(message: TgMessage) -> str:
    content = message.text

    if message.entities:
        transformers: list[Transformer] = []

        for entity in message.entities:
            match entity.type:
                case "pre":
                    transformers.append(PreWrapTransformer(entity))
                case "blockquote" | "expandable_blockquote":
                    transformers.append(QuoteTransformer(entity))
                case _:
                    if entity.type not in WRAP_STRINGS: 
                        continue

                    transformers.append(WrapTransformer(entity))

        transformers.sort(reverse=True)

        for transformer in transformers:
            content = transformer.transform(content)

    return content

def discord_to_telegram(message: DsMessage) -> str:
    pass
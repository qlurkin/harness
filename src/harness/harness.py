from collections.abc import AsyncGenerator


class Content(str): ...


class Thinking(str): ...


Event = Content | Thinking


async def harness() -> AsyncGenerator[Event]:

    prompt = yield Content("")


if __name__ == "__main__":
    c = Content("ceci est un contenu")
    print(c)
    print(isinstance(c, Content))
    print(isinstance(c, Thinking))
    print(type(c))

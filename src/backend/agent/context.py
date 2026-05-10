from typing_extensions import TypedDict


class EnvContext(TypedDict, total=False):
    thread_id: str

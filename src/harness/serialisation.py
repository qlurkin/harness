import json
from dataclasses import MISSING, asdict, fields, is_dataclass


def default_object_hook(obj):
    return obj


OBJECT_HOOK = default_object_hook


def make_object_hook(types):
    global OBJECT_HOOK

    types = sorted(
        types,
        key=lambda cls: len(fields(cls)),
        reverse=True,
    )

    def object_hook(obj):
        keys = set(obj)

        for cls in types:
            fs = fields(cls)
            names = {f.name for f in fs}

            required = {
                f.name
                for f in fs
                if f.default is MISSING and f.default_factory is MISSING
            }

            if required <= keys:
                data = {k: v for k, v in obj.items() if k in names}
                return cls(**data)

        return obj

    OBJECT_HOOK = object_hook


def json_default(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    raise TypeError(f"Type non sérialisable : {type(obj)}")


def dumps(obj):
    return json.dumps(obj, default=json_default)


def loads(doc):
    return json.loads(doc, object_hook=OBJECT_HOOK)

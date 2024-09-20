from typing import Any, Dict

# Copied from core python because its containing module `distutils` is deprecated.


def strtobool(val):
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


# Samme som item[key1][key2][key3] ...
# men giver ikke KeyError hvis en key ikke findes
# eller ValueError hvis et af leddene er None i stedet for en dict
# Der returneres enten den ønskede værdi eller None
def lenient_get(item, *keys: str | int):
    for key in keys:
        if item is not None:
            if isinstance(item, dict) and type(key) is str:
                item = item.get(key)
            elif isinstance(item, list) and type(key) is int and len(item) > key:
                item = item[key]
            else:
                return None
    return item


def omit(item: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    return {key: value for key, value in item.items() if key not in keys}

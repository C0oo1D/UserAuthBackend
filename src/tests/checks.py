from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from functools import partial
from json import JSONDecodeError
from re import escape
from typing import Any

import pytest
from httpx import Response

type CheckResult[T] = Callable[[T], bool]
_sort_t = dict | list | tuple


@contextmanager
def check_exc(result, msg: str = ""):
    raises_obj = None
    if isinstance(result, type) and issubclass(result, Exception):
        raises_obj = pytest.raises(result, match=escape(msg) or None)
    elif isinstance(result, Exception):
        raises_obj = pytest.raises(type(result), match=escape(result.args[0]))

    with raises_obj or nullcontext() as context:
        yield context


def _fmt_exc(
    _header: tuple[str, str],
    _lines: tuple[str, ...],
    info: str,
    name: str,
    sep: str,
    *args,
    invert: bool,
    **kwargs,
) -> AssertionError:
    if args or kwargs:
        args = tuple(arg() if isinstance(arg, Callable) else arg for arg in args)
        kwargs = {k: v() if isinstance(v, Callable) else v for k, v in kwargs.items()}
        info = info.format(*args, **kwargs)
    header = (f"{name[0].capitalize() + name[1:]} is " if name else "") + _header[invert]
    return AssertionError(sep.join(line for line in (header, *_lines, info) if line))


def equal(
    expected: Any,
    received: Any,
    info: str = "",
    *args,
    invert: bool = False,
    name: str = "",
    sep: str = "\n\t",
    **kwargs,
):
    if (expected == received) if invert else (expected != received):
        __tracebackhide__ = True
        _equal = ("not equal", "equal, but must not")
        _lines = f"Expected: {expected!r}", f"Received: {received!r}"
        raise _fmt_exc(_equal, _lines, info, name, sep, *args, invert=invert, **kwargs)


def inside(
    item: Any,
    items: Any,
    info: str = "",
    *args,
    invert: bool = False,
    name: str = "",
    sep: str = "\n\t",
    **kwargs,
):
    if (item in items) if invert else (item not in items):
        __tracebackhide__ = True
        _inside = ("not inside", "inside, but must not")
        _lines = f"Item: {item!r}", f"Items: {items!r}"
        raise _fmt_exc(_inside, _lines, info, name, sep, *args, invert=invert, **kwargs)


def equal_resp[T: Response](
    code: int = 0,
    json: dict | None = None,
    *,
    set_cookie: bool | None = None,
    json_handler: Callable | None = None,
) -> CheckResult[T]:
    """Response equality checker"""

    def try_json(resp: T):
        try:
            return resp.json()
        except JSONDecodeError:
            return repr(resp)

    def wrapper(resp: T):
        if code:
            arg = partial(try_json, resp)
            equal(code, resp.status_code, "Response: {!r}", arg, name="Status code", sep=". ")

        if json is not None:
            r_json = resp.json()
            r_json_handled = json_handler(r_json) if json_handler else r_json
            equal(json, r_json_handled, "Received RAW: {!r}", r_json, name="JSON")

        if set_cookie is not None:
            inside("set-cookie", resp.headers, name="Cookie", invert=not set_cookie)

        return True

    return wrapper


def sort_recursively[T: _sort_t](data: T, dict_key: str = "name") -> T:
    """For repeatable tests with possible not ordered data"""
    if isinstance(data, list | tuple):
        result = []
        for item in data:
            sort_key = item[dict_key] if isinstance(item, dict) else item
            value = sort_recursively(item) if isinstance(item, _sort_t) else item
            result.append((sort_key, value))
        return type(data)(tuple(zip(*sorted(result, key=lambda x: x[0]), strict=True))[1])
    if isinstance(data, dict):
        return {k: sort_recursively(v) if isinstance(v, _sort_t) else v for k, v in data.items()}
    return data


def msg_422(data: dict) -> dict:
    return {"detail": [{"msg": data["detail"][0]["msg"]}]}

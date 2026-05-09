from typing import Callable

from httpx import Response


type CheckResult[T] = Callable[[T], bool]
_sorting_types = dict | list | tuple


def is_equal[T: Response](code=0, json: dict | None = None, *, set_cookie: bool | None = None,
                          json_handler: Callable | None = None) -> CheckResult[T]:
    def wrapper(response: T):
        if code:
            r_code = response.status_code
            assert code == r_code, (f"Expected {code}, but received {r_code}"
                                    f"\n\tResponse: {response.json()!r}")
        if json is not None:
            r_json = response.json()
            if json_handler:
                r_json = json_handler(r_json)
            assert json == r_json, ("JSON responses is not equal"
                                    f"\n\tExpected: {json!r}"
                                    f"\n\tReceived: {r_json!r}")
        if set_cookie is not None:
            if set_cookie:
                assert "set-cookie" in response.headers, "Cookie is not set, but must"
            else:
                assert "set-cookie" not in response.headers, "Cookie is set, but must not"
        return True
    return wrapper


def sort_recursively[T: _sorting_types](data: T, dict_key: str = 'name') -> T:
    if isinstance(data, list | tuple):
        result = []
        for item in data:
            result.append((item[dict_key] if isinstance(item, dict) else item,
                           sort_recursively(item) if isinstance(item, _sorting_types) else item))
        return type(data)(tuple(zip(*sorted(result, key=lambda x: x[0])))[1])
    if isinstance(data, dict):
        return {k: sort_recursively(v) if isinstance(v, _sorting_types) else v
                for k, v in data.items()}
    return data

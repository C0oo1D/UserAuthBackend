from collections.abc import Callable

from httpx import Response

type CheckResult[T] = Callable[[T], bool]
_sort_t = dict | list | tuple


def check(equal, error_message: str = ""):
    """Assert replacement in case of enabled optimizations"""
    if not equal:
        raise AssertionError(error_message) if error_message else AssertionError


def is_equal[T: Response](
    code: int = 0,
    json: dict | None = None,
    *,
    set_cookie: bool | None = None,
    json_handler: Callable | None = None,
) -> CheckResult[T]:
    """Response equality checker"""

    def wrapper(response: T):
        if code:
            r_code = response.status_code
            check(
                code == r_code,
                f"Expected {code}, but received {r_code}\n\tResponse: {response.json()!r}",
            )
        if json is not None:
            r_json = response.json()
            if json_handler:
                r_json = json_handler(r_json)
            check(
                json == r_json,
                f"JSON responses is not equal\n\tExpected: {json!r}\n\tReceived: {r_json!r}",
            )
        if set_cookie is not None:
            if set_cookie:
                check("set-cookie" in response.headers, "Cookie is not set, but must")
            else:
                check("set-cookie" not in response.headers, "Cookie is set, but must not")
        return True

    return wrapper


# noinspection PyTypeChecker
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

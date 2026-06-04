from typing import Literal

from schemas import Error


def fmt_errors(*codes: int) -> dict[int, dict[Literal['model'], type[Error]]]:
    """Format possible response codes as errors"""
    return {code: {'model': Error} for code in codes}

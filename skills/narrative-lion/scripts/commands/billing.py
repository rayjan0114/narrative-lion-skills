"""Billing command: usage."""

from lib.client import rest_get
from lib.formatters import as_json


def usage(args: list[str], json_mode: bool = False) -> None:
    data = rest_get("/api/billing/usage")

    if json_mode:
        print(as_json(data))
        return

    print("Credit Usage:")
    for key, val in data.items():
        if isinstance(val, dict):
            used = val.get("used", 0)
            limit = val.get("limit", 0)
            label = key.replace("_", " ").title()
            bar = f"{used}/{limit}" if limit > 0 else str(used)
            print(f"  {label:20s}  {bar}")
        else:
            print(f"  {key:20s}  {val}")

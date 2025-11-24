from datetime import date, datetime, timedelta
from time import strptime
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


def get_midnight(datetime_in: datetime) -> datetime:
    """
    Set the time of the given datetime object to midnight (00:00:00).

    Args:
        datetime_in (datetime): The input datetime object to be modified.

    Returns:
        datetime: A new datetime object with the time set to midnight.
        ValueError: If the input datetime is None.

    Raises:
        TypeError: If datetime_in is not a datetime object.

    Example:
        `>>> dt = datetime(2023, 10, 5, 15, 30)`
        `>>> make_midnight(dt)`
        `datetime.datetime(2023, 10, 5, 0, 0)`
    """
    if datetime_in is None:
        raise ValueError("Input datetime cannot be None.")
    if not isinstance(datetime_in, datetime):
        raise TypeError("Input must be a datetime object.")

    return datetime_in.replace(hour=0, minute=0, second=0, microsecond=0)


def get_next_week(datetime_in: datetime) -> datetime:
    """
    Returns a datetime object that is one week later than the input datetime.

    Parameters:
    datetime_in (datetime): The input datetime from which to calculate the next week.

    Raises:
        ValueError: If the input datetime is None.
        TypeError: If the input is not a datetime object.

    Returns:
    datetime: A new datetime object representing the date and
        time one week after the input.

    Example:
        `>>> now = datetime(2023, 10, 1, 12, 0)`
        `>>> next_week(now)`
        `datetime.datetime(2023, 10, 8, 12, 0)`
    """
    if datetime_in is None:
        raise ValueError("Input datetime cannot be None.")
    if not isinstance(datetime_in, datetime):
        raise TypeError("Input must be a datetime object.")

    return datetime_in + timedelta(weeks=1)


def new_taxrate_start_datetime(datetime_in: datetime) -> datetime:
    """
    Calculate the midnight time of the day one week from the given datetime.
    Initially for use in havneafgifter/views.py:TaxRateFormView:get_initial()
    as the default start datetime for a new tax rate.

    Args:
        datetime_in (datetime): The input datetime object.

    Returns:
        datetime: A new datetime object representing midnight one
            week from the input date.
        ValueError: If the input datetime is None.

    Raises:
        TypeError: If datetime_in is not a datetime object.

    Example:
        `>>> dt = datetime(2023, 10, 5, 15, 30)`
        `>>> next_midnight_in_1_week(dt)`
        `datetime.datetime(2023, 10, 12, 0, 0)`
    """
    if datetime_in is None:
        raise ValueError("Input datetime cannot be None.")
    if not isinstance(datetime_in, datetime):
        raise TypeError("Input must be a datetime object.")

    return get_midnight(get_next_week(datetime_in)) + timedelta(days=1)


def parse_isodate(input: str) -> date:
    return date(*(strptime(input, "%Y-%m-%d")[0:3]))

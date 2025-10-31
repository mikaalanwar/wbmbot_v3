import re

import requests


def contains_filter_keywords(flat_elem, user_filters):
    """Check if the flat contains any of the exclude keywords and return the keywords."""

    # Find all keywords that are in the flat_elem's text
    keywords_found = [
        keyword
        for keyword in user_filters
        if str(keyword).strip().lower() in flat_elem.text.lower()
    ]

    # Return a tuple of boolean and keywords found
    return (bool(keywords_found), keywords_found)


def verify_flat_rent(flat_rent, user_flat_rent):
    """Check if the flat rent is <= the user specified flat rent."""

    # If the rent is "" it means the listing has some improper values and
    # we couldn't fetch the correct numbers from the texts
    # so we apply regardless
    if flat_rent == "":
        return True

    try:
        rent_value = float(flat_rent)
        user_flat_rent_value = float(user_flat_rent)
    except (TypeError, ValueError):
        return True

    # Check rent numbers
    if rent_value <= user_flat_rent_value:
        return True
    else:
        return False


def verify_flat_size(flat_size, user_flat_size):
    """Check if the flat size is >= the user specified flat size."""

    # If the size is "" it means the listing has some improper values and
    # we couldn't fetch the correct numbers from the texts
    # so we apply regardless
    if flat_size in ("", None):
        return True

    try:
        flat_size_value = float(flat_size)
        user_flat_size_value = float(user_flat_size)
    except (TypeError, ValueError):
        return True

    # Check size numbers
    if flat_size_value >= user_flat_size_value:
        return True
    else:
        return False


def verify_flat_rooms(flat_rooms, user_flat_rooms):
    """Check if the flat rooms is >= the user specified flat rooms."""

    # If the size is "" it means the listing has some improper values and
    # we couldn't fetch the correct numbers from the texts
    # so we apply regardless
    if flat_rooms in ("", None):
        return True

    try:
        flat_rooms_value = float(flat_rooms)
        user_flat_rooms_value = float(user_flat_rooms)
    except (TypeError, ValueError):
        return True

    # Check size numbers
    if flat_rooms_value >= user_flat_rooms_value:
        return True
    else:
        return False


def check_internet_connection():
    """
    Check internet connection by sending a GET request to www.google.com using HTTPS.

    Returns:
        bool: True if internet connection is available, False otherwise.
    """

    try:
        response = requests.get("https://www.google.com", timeout=1)
        return response.status_code in [200, 201, 204]
    except requests.Timeout:
        return False
    except requests.ConnectionError:
        return False
    except requests.TooManyRedirects:
        return False
    except requests.InvalidURL:
        return False
    except requests.RequestException:
        return False


def convert_rent(rent_text: str) -> str:
    """
    Convert a rent string to a numerical value.

    Args:
        rent_text (str): The rent string containing numeric and non-numeric characters.

    Returns:
        str: The numerical value of the rent string formatted with two decimal places.

    Example:
        >>> convert_rent("Warmmiete 1.404,40 €")
        '1404.40'
    """
    # Check if the string contains the euro symbol
    if "€" not in rent_text:
        return ""

    # Remove non-numeric characters
    numeric_string = re.sub(r"[^\d.,]", "", rent_text)

    # Replace comma with dot for decimal point uniformity
    numeric_string = numeric_string.replace(",", ".")

    # Remove extra dots in thousands separators
    numeric_string = numeric_string.replace(".", "", numeric_string.count(".") - 1)

    # Convert to float
    numeric_value = float(numeric_string)

    return numeric_value


def convert_size(size_text: str) -> str:
    """
    Convert a size string to a numerical value.

    Args:
        size_text (str): The size string containing numeric and non-numeric characters.

    Returns:
        str: The numerical value of the size string formatted with two decimal places.

    Example:
        >>> convert_size("Größe 60,09 m²")
        '60.09'
    """
    # Check if the string contains the euro symbol
    if "m²" not in size_text:
        return 0.0

    # Remove non-numeric characters
    numeric_string = re.sub(r"[^\d.,]", "", size_text)

    # Replace comma with dot for decimal point uniformity
    numeric_string = numeric_string.replace(",", ".")

    # Remove extra dots in thousands separators
    numeric_string = numeric_string.replace(".", "", numeric_string.count(".") - 1)

    # Convert to float
    numeric_value = float(numeric_string)

    return numeric_value


def get_zimmer_count(text: str) -> int:
    """
    Extract the count of "Zimmer" from the given text.

    Args:
        text (str): The input text containing the count of "Zimmer".

    Returns:
        int: The count of "Zimmer" extracted from the text.

    Example:
        >>> get_zimmer_count("Zimmer2")
        2
    """
    # Extract the number using regular expressions
    if not text:
        return None

    matches = re.findall(r"\d+", str(text))
    if matches:
        return int(matches[0])

    return None


def parse_delay_to_seconds(value, default_seconds: int = 10) -> int:
    """
    Convert a human-readable delay string (e.g. 30s, 1m, 2h) to seconds.

    Args:
        value (str | int | float): Delay value provided by the user.
        default_seconds (int): Fallback delay when parsing fails.

    Returns:
        int: Delay in seconds.
    """

    if value is None or value == "":
        return max(default_seconds, 0)

    if isinstance(value, (int, float)):
        return max(int(value), 0)

    match = re.match(r"^\s*(\d+(?:\.\d*)?)\s*([smhSMH]?)\s*$", str(value))
    if not match:
        return max(default_seconds, 0)

    amount = float(match.group(1))
    unit = match.group(2).lower() if match.group(2) else "s"

    multiplier = 1
    if unit == "m":
        multiplier = 60
    elif unit == "h":
        multiplier = 3600

    return max(int(amount * multiplier), 0)

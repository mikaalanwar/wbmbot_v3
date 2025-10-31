import hashlib
import html
import re
import unicodedata


class Flat:
    """
    Parse a single flat entry either from HTML or plain text.
    """

    def __init__(self, flat_source: str, test: bool):
        self.test = test
        self.flat_source = flat_source or ""
        self.raw_html = flat_source if self._looks_like_html(flat_source) else ""
        self.flat_text = self._to_text(flat_source)
        self.flat_attr = [
            line.strip() for line in self.flat_text.split("\n") if line.strip()
        ]
        self.attr_size = len(self.flat_attr)
        print(self.flat_attr) if self.test else None

        self.title = ""
        self.district = ""
        self.street = ""
        self.zip_code = ""
        self.city = ""
        self.total_rent = ""
        self.size = ""
        self.rooms = ""

        if self.raw_html:
            self._parse_from_html()
        else:
            self._parse_from_text(self.flat_attr)

        # Fallback to text parsing if html parsing missed anything important
        if not self.total_rent or not self.size or not self.rooms:
            self._parse_from_text(self.flat_attr, overwrite_missing=True)

        self.wbs = "wbs" in (self.title or "").lower() or "wbs" in self.flat_text.lower()
        identifier = self.raw_html or self.flat_text
        self.hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def _parse_from_html(self):
        self.title = self._extract_html_value(
            r'<h2[^>]*class="[^"]*imageTitle[^"]*"[^>]*>(.*?)</h2>'
        )
        self.district = self._extract_html_value(
            r'<div[^>]*class="[^"]*area[^"]*"[^>]*>(.*?)</div>'
        )
        address_line = self._extract_html_value(
            r'<div[^>]*class="[^"]*address[^"]*"[^>]*>(.*?)</div>'
        )
        self.street, self.zip_code, self.city = self._split_address(address_line)
        self.total_rent = self._extract_html_value(
            r'<div[^>]*class="[^"]*main-property-value[^"]*main-property-rent[^"]*"[^>]*>(.*?)</div>'
        )
        self.size = self._extract_html_value(
            r'<div[^>]*class="[^"]*main-property-value[^"]*main-property-size[^"]*"[^>]*>(.*?)</div>'
        )
        self.rooms = self._extract_html_value(
            r'<div[^>]*class="[^"]*main-property-value[^"]*main-property-rooms[^"]*"[^>]*>(.*?)</div>'
        )

    def _parse_from_text(self, attributes, overwrite_missing: bool = False):
        attributes = attributes or []
        if overwrite_missing or not getattr(self, "title", None):
            self.title = attributes[0] if attributes else ""
        if overwrite_missing or not getattr(self, "district", None):
            self.district = attributes[1] if len(attributes) > 1 else ""

        street_parts = []
        address_index = 2
        while address_index < len(attributes):
            candidate = attributes[address_index]
            normalized_candidate = self._normalize_text(candidate)
            if re.search(r"\b\d{5}\b", candidate):
                break
            if any(
                keyword in normalized_candidate
                for keyword in ("warmmiete", "kaltmiete", "grosse", "zimmer")
            ):
                break
            street_parts.append(candidate)
            address_index += 1

        zip_code = getattr(self, "zip_code", "")
        city = getattr(self, "city", "")
        if address_index < len(attributes):
            address_line = attributes[address_index]
            parsed_zip, parsed_city, zip_start = self._parse_zip_city(address_line)
            if parsed_zip:
                street_candidate = address_line[:zip_start].strip().rstrip(",")
                if street_candidate:
                    street_parts.append(street_candidate)
                zip_code = parsed_zip
                city = parsed_city
                address_index += 1
            else:
                street_parts.append(address_line)
                address_index += 1
                if address_index < len(attributes):
                    address_line = attributes[address_index]
                    parsed_zip, parsed_city, zip_start = self._parse_zip_city(
                        address_line
                    )
                    if parsed_zip:
                        street_candidate = address_line[:zip_start].strip().rstrip(",")
                        if street_candidate and not street_parts:
                            street_parts.append(street_candidate)
                        zip_code = parsed_zip
                        city = parsed_city
                        address_index += 1

        if overwrite_missing or not getattr(self, "street", None):
            self.street = " ".join(part.strip(", ") for part in street_parts).strip()
        if overwrite_missing or not getattr(self, "zip_code", None):
            self.zip_code = zip_code.strip()
        if overwrite_missing or not getattr(self, "city", None):
            self.city = city.strip()

        details = attributes[address_index:]
        if overwrite_missing or not getattr(self, "total_rent", None):
            self.total_rent = self._extract_detail(details, "warmmiete")
        if overwrite_missing or not getattr(self, "size", None):
            self.size = self._extract_detail(details, "gr\u00f6\u00df\u0065")
        if overwrite_missing or not getattr(self, "rooms", None):
            self.rooms = self._extract_detail(details, "zimmer")

    def _extract_html_value(self, pattern: str) -> str:
        if not self.raw_html:
            return ""
        match = re.search(pattern, self.raw_html, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        value = match.group(1)
        value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", " ", value)
        value = html.unescape(value)
        return " ".join(value.replace("\xa0", " ").split())

    @staticmethod
    def _extract_detail(tokens, label: str) -> str:
        label_lower = label.lower()
        for index, token in enumerate(tokens):
            stripped = token.strip()
            token_lower = stripped.lower()
            position = token_lower.find(label_lower)
            if position != -1:
                remainder = stripped[position + len(label_lower) :].strip(" :")
                if remainder:
                    return remainder
                if index + 1 < len(tokens):
                    return tokens[index + 1].strip()
        return ""

    @staticmethod
    def _normalize_text(value: str) -> str:
        cleaned = value.replace("ß", "ss")
        normalized = unicodedata.normalize("NFKD", cleaned)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        return normalized.lower()

    @staticmethod
    def _parse_zip_city(text: str):
        match = re.search(r"\b(\d{5})\b\s*(.*)", text)
        if match:
            return match.group(1), match.group(2).strip(), match.start(1)
        return "", "", -1

    @staticmethod
    def _looks_like_html(value: str) -> bool:
        return bool(value) and "<" in value and "</" in value

    @staticmethod
    def _to_text(value: str) -> str:
        if not value:
            return ""
        if Flat._looks_like_html(value):
            stripped = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
            stripped = re.sub(r"<[^>]+>", "\n", stripped)
            stripped = html.unescape(stripped)
            return "\n".join(line.strip() for line in stripped.splitlines())
        return value

    @staticmethod
    def _split_address(address_line: str):
        street = ""
        zip_code = ""
        city = ""
        if address_line:
            parts = [part.strip() for part in address_line.split(",") if part.strip()]
            if len(parts) == 1:
                street = parts[0]
            elif len(parts) >= 2:
                street = ", ".join(parts[:-1])
                candidate = parts[-1]
                match = re.search(r"(\d{5})\s+(.*)", candidate)
                if match:
                    zip_code = match.group(1).strip()
                    city = match.group(2).strip()
                else:
                    city = candidate
            match_zip = re.search(r"\b(\d{5})\b\s*(.*)", street)
            if match_zip:
                zip_code = zip_code or match_zip.group(1).strip()
                city = city or match_zip.group(2).strip()
                street = street[: match_zip.start(1)].strip(", ")
        return street, zip_code, city

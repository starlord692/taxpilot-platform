"""GST jurisdiction partitioning and state code validation under TAX-01.

Categorizes Indian GST state codes into:
- 31 States / UTs with Legislature (attracting CGST + SGST for intra-state supply)
- 5 Domestic Commercial Union Territories without Legislature (attracting CGST + UTGST for intra-state supply)
- Code 97 ("Other Territory" offshore territorial waters / EEZ - fails closed)
- Legacy Code 25 (Daman & Diu - merged into 26 in 2020 - fails closed)
"""

from __future__ import annotations

from typing import Final

from app.common.exceptions import ValidationException


class InvalidStateCodeException(ValidationException):
    """Raised when an invalid GST state code is provided."""

    status_code = 422
    error_code = "sales.invoice_invalid_state_code"


class LegacyStateCodeObsoleteException(ValidationException):
    """Raised when deprecated state code 25 is provided."""

    status_code = 422
    error_code = "sales.invoice_legacy_state_code_obsolete"


class OffshoreTerritoryUnsupportedException(ValidationException):
    """Raised when offshore code 97 is provided."""

    status_code = 422
    error_code = "sales.invoice_offshore_territory_unsupported"


# 31 States and Union Territories WITH Legislature (CGST + SGST)
SGST_JURISDICTIONS: Final[frozenset[str]] = frozenset(
    {
        "01",  # Jammu and Kashmir
        "02",  # Himachal Pradesh
        "03",  # Punjab
        "05",  # Uttarakhand
        "06",  # Haryana
        "07",  # Delhi
        "08",  # Rajasthan
        "09",  # Uttar Pradesh
        "10",  # Bihar
        "11",  # Sikkim
        "12",  # Arunachal Pradesh
        "13",  # Nagaland
        "14",  # Manipur
        "15",  # Mizoram
        "16",  # Tripura
        "17",  # Meghalaya
        "18",  # Assam
        "19",  # West Bengal
        "20",  # Jharkhand
        "21",  # Odisha
        "22",  # Chhattisgarh
        "23",  # Madhya Pradesh
        "24",  # Gujarat
        "27",  # Maharashtra
        "29",  # Karnataka
        "30",  # Goa
        "32",  # Kerala
        "33",  # Tamil Nadu
        "34",  # Puducherry
        "36",  # Telangana
        "37",  # Andhra Pradesh
    }
)

# 5 Domestic Commercial Union Territories WITHOUT Legislature (CGST + UTGST)
# Ratified under FD-TAX-01-03
UTGST_JURISDICTIONS: Final[frozenset[str]] = frozenset(
    {
        "04",  # Chandigarh
        "26",  # Dadra and Nagar Haveli and Daman and Diu
        "31",  # Lakshadweep
        "35",  # Andaman and Nicobar Islands
        "38",  # Ladakh
    }
)

ALL_DOMESTIC_JURISDICTIONS: Final[frozenset[str]] = frozenset(
    SGST_JURISDICTIONS | UTGST_JURISDICTIONS
)

OFFSHORE_JURISDICTIONS: Final[frozenset[str]] = frozenset({"97"})
LEGACY_OBSOLETE_JURISDICTIONS: Final[frozenset[str]] = frozenset({"25"})

JURISDICTION_NAMES: Final[dict[str, str]] = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu (Obsolete)",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
    "97": "Other Territory (Offshore)",
}


def is_utgst_jurisdiction(state_code: str | None) -> bool:
    """Return True if the state code is an approved domestic commercial UTGST territory."""
    if not state_code:
        return False
    return state_code.strip().zfill(2) in UTGST_JURISDICTIONS


def is_sgst_jurisdiction(state_code: str | None) -> bool:
    """Return True if the state code is a state or UT with legislature (SGST)."""
    if not state_code:
        return False
    return state_code.strip().zfill(2) in SGST_JURISDICTIONS


def validate_state_code(state_code: str | None) -> str:
    """Validate and normalize a 2-digit GST state code fail-closed.

    Raises:
        InvalidStateCodeException: If format is invalid or code is unmapped.
        OffshoreTerritoryUnsupportedException: If code 97 is provided.
        LegacyStateCodeObsoleteException: If obsolete code 25 is provided.
    """
    if state_code is None:
        raise InvalidStateCodeException(
            "State code is required",
            details={"state_code": None},
        )

    code = str(state_code).strip()
    if len(code) == 1 and code.isdigit():
        code = code.zfill(2)

    if len(code) != 2 or not code.isdigit():
        raise InvalidStateCodeException(
            f"State code must be a 2-digit numeric string, got: '{state_code}'",
            details={"state_code": state_code},
        )

    if code in OFFSHORE_JURISDICTIONS:
        raise OffshoreTerritoryUnsupportedException(
            "GST code 97 (Other Territory) offshore supplies are unsupported in domestic commercial invoicing",
            details={"state_code": code},
        )

    if code in LEGACY_OBSOLETE_JURISDICTIONS:
        raise LegacyStateCodeObsoleteException(
            "State code 25 (Daman and Diu) is obsolete and merged into code 26",
            details={"state_code": code, "merged_into": "26"},
        )

    if code not in ALL_DOMESTIC_JURISDICTIONS:
        raise InvalidStateCodeException(
            f"Unknown or unsupported GST state code: '{code}'",
            details={"state_code": code},
        )

    return code

"""Small, typed USDA FoodData Central client for planned-meal foods."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Protocol

import requests

try:
    from meal_plan_nutrients import NutrientProfile
except ModuleNotFoundError:
    from .meal_plan_nutrients import NutrientProfile


DEFAULT_BASE_URL = "https://api.nal.usda.gov/fdc"
DEFAULT_TIMEOUT_SECONDS = 10.0
PER_100_GRAM_DATA_TYPES = {"Foundation", "SR Legacy", "Survey (FNDDS)"}

_NUTRIENT_IDS = {
    "sodium_mg": {1093},
    "potassium_mg": {1092},
    "energy_kcal": {1008},
    "sat_fat_g": {1258},
    "protein_g": {1003},
    "carbs_g": {1005},
    "fiber_g": {1079},
    "calcium_mg": {1087},
    "magnesium_mg": {1090},
    "vitamin_c_mg": {1162},
}
_ENERGY_KJ_ID = 1062
_NUTRIENT_NAME_ALIASES = {
    "sodium_mg": {"sodium, na", "sodium"},
    "potassium_mg": {"potassium, k", "potassium"},
    "energy_kcal": {"energy", "energy, kcal", "energy (atwater general factors)"},
    "sat_fat_g": {
        "fatty acids, total saturated",
        "saturated fat",
        "saturated fatty acids",
    },
    "protein_g": {"protein"},
    "carbs_g": {"carbohydrate, by difference", "carbohydrate"},
    "fiber_g": {"fiber, total dietary", "dietary fiber"},
    "calcium_mg": {"calcium, ca", "calcium"},
    "magnesium_mg": {"magnesium, mg", "magnesium"},
    "vitamin_c_mg": {"vitamin c, total ascorbic acid", "vitamin c"},
}


class USDAFoodDataError(Exception):
    """Base exception for FoodData Central configuration, transport, or data errors."""


class USDAConfigurationError(USDAFoodDataError):
    """The client is missing valid configuration."""


class USDARequestError(USDAFoodDataError):
    """The USDA request failed before a usable response was obtained."""


class USDAResponseError(USDAFoodDataError):
    """The USDA response was malformed or could not be interpreted."""


class USDAEmptySearchError(USDAResponseError):
    """The USDA search completed successfully but returned no foods."""


class USDAUnsupportedUnitError(USDAResponseError):
    """A required nutrient used an unsupported or missing unit."""


class HTTPResponse(Protocol):
    status_code: int

    def raise_for_status(self) -> None:
        ...

    def json(self) -> object:
        ...


class HTTPTransport(Protocol):
    def get(
        self,
        url: str,
        *,
        params: Mapping[str, object],
        timeout: float,
    ) -> HTTPResponse:
        ...


@dataclass(frozen=True)
class FoodSearchResult:
    """A candidate returned by FoodData Central search."""

    fdc_id: int
    description: str
    data_type: str
    serving_size: float | None
    serving_size_unit: str | None


@dataclass(frozen=True)
class USDAFoodRecord:
    """A selected USDA food with normalized nutrients and explicit basis."""

    fdc_id: int
    description: str
    data_type: str
    nutrients: NutrientProfile
    reference_quantity: float
    reference_unit: str
    serving_size: float | None = None
    serving_size_unit: str | None = None


def _positive_finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise USDAResponseError(f"{name} must be a finite non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise USDAResponseError(f"{name} must be a finite non-negative number")
    return number


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise USDAResponseError(f"USDA response field {name} is missing or invalid")
    return value


def _food_id(value: object, name: str = "fdc_id") -> int:
    if isinstance(value, bool):
        raise USDAResponseError(f"{name} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise USDAResponseError(f"{name} must be a positive integer") from error
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise USDAResponseError(f"{name} must be a positive integer")
    return parsed


def _canonical_name(value: object) -> str:
    return " ".join(str(value).casefold().strip().split())


def _nutrient_fields(record: Mapping[str, object]) -> tuple[object, object, object, object]:
    nested_nutrient = record.get("nutrient")
    if nested_nutrient is not None:
        if not isinstance(nested_nutrient, dict):
            raise USDAResponseError("USDA nutrient field must be an object")
        return (
            nested_nutrient.get("id"),
            nested_nutrient.get("name"),
            nested_nutrient.get("unitName"),
            record.get("amount"),
        )
    return (
        record.get("nutrientId"),
        record.get("nutrientName"),
        record.get("unitName"),
        record.get("value"),
    )


def _nutrient_target(record: Mapping[str, object]) -> str | None:
    nutrient_id, nutrient_name, _, _ = _nutrient_fields(record)
    for target, ids in _NUTRIENT_IDS.items():
        if nutrient_id in ids:
            return target
    if nutrient_id == _ENERGY_KJ_ID:
        return "energy_kcal"

    name = _canonical_name(nutrient_name or "")
    for target, aliases in _NUTRIENT_NAME_ALIASES.items():
        if name in aliases:
            return target
    return None


def _normalize_nutrient(target: str, value: object, unit: object) -> float | None:
    if value is None:
        return None
    amount = _positive_finite_number(value, f"{target} value")
    if not isinstance(unit, str) or not unit.strip():
        raise USDAUnsupportedUnitError(f"Missing source unit for {target}")
    normalized_unit = unit.casefold().replace(" ", "")
    if target in {"sodium_mg", "potassium_mg", "calcium_mg", "magnesium_mg", "vitamin_c_mg"}:
        if normalized_unit != "mg":
            raise USDAUnsupportedUnitError(f"Unsupported source unit for {target}: {unit}")
        return amount
    if target == "energy_kcal":
        if normalized_unit in {"kcal", "kilocalorie", "kilocalories"}:
            return amount
        if normalized_unit in {"kj", "kilojoule", "kilojoules"}:
            return amount / 4.184
        raise USDAUnsupportedUnitError(f"Unsupported source unit for {target}: {unit}")
    if normalized_unit in {"g", "gram", "grams"}:
        return amount
    if normalized_unit in {"mg", "milligram", "milligrams"}:
        return amount / 1000
    raise USDAUnsupportedUnitError(f"Unsupported source unit for {target}: {unit}")



def _parse_food_nutrients(records: object) -> dict[str, float | None]:
    if not isinstance(records, list):
        raise USDAResponseError("USDA response foodNutrients must be a list")

    values: dict[str, float | None] = {field: None for field in _NUTRIENT_IDS}
    seen: set[str] = set()
    energy_ids_seen: set[int] = set()
    for record in records:
        if not isinstance(record, dict):
            raise USDAResponseError("USDA nutrient records must be objects")
        target = _nutrient_target(record)
        if target is None:
            continue
        nutrient_id, _, unit, amount = _nutrient_fields(record)
        if target == "energy_kcal":
            if nutrient_id not in {1008, _ENERGY_KJ_ID}:
                raise USDAResponseError(
                    "USDA energy record has an unrecognized nutrient ID"
                )
            if nutrient_id in energy_ids_seen:
                raise USDAResponseError(
                    "USDA response contains duplicate energy_kcal records"
                )
            normalized = _normalize_nutrient(target, amount, unit)
            if energy_ids_seen and not math.isclose(
                values[target], normalized, rel_tol=0.05, abs_tol=1.0
            ):
                raise USDAResponseError(
                    "USDA response contains duplicate energy_kcal records with conflicting values"
                )
            energy_ids_seen.add(nutrient_id)
            if nutrient_id == 1008 or not energy_ids_seen - {nutrient_id}:
                values[target] = normalized
            continue
        if target in seen:
            raise USDAResponseError(
                f"USDA response contains duplicate {target} records"
            )
        values[target] = _normalize_nutrient(target, amount, unit)
        seen.add(target)
    return values


def _parse_label_nutrients(label_nutrients: object) -> dict[str, float | None]:
    if not isinstance(label_nutrients, dict):
        raise USDAResponseError("USDA response labelNutrients must be an object")
    labels = {
        "sodium_mg": ("sodium", "mg"),
        "potassium_mg": ("potassium", "mg"),
        "energy_kcal": ("calories", "kcal"),
        "sat_fat_g": ("saturatedFat", "g"),
    }
    values: dict[str, float | None] = {}
    for target, (label, unit) in labels.items():
        record = label_nutrients.get(label)
        if record is None:
            values[target] = None
            continue
        if not isinstance(record, dict) or "value" not in record:
            raise USDAResponseError(f"USDA label nutrient {label} is malformed")
        values[target] = _normalize_nutrient(target, record["value"], unit)
    return values


class USDAFoodDataClient:
    """Client for searching and retrieving explicitly selected USDA foods."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        session: HTTPTransport | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        configured_key = os.getenv("USDA_FDC_API_KEY") if api_key is None else api_key
        if not isinstance(configured_key, str) or not configured_key.strip():
            raise USDAConfigurationError("USDA_FDC_API_KEY is missing or blank")
        if isinstance(timeout, bool) or not isinstance(timeout, Real) or not math.isfinite(float(timeout)) or timeout <= 0:
            raise USDAConfigurationError("timeout must be a positive finite number")
        if not isinstance(base_url, str) or not base_url.strip():
            raise USDAConfigurationError("base_url must be a non-empty string")
        self._api_key = configured_key
        self._session = session if session is not None else requests.Session()
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout)

    def _get_json(self, path: str, params: Mapping[str, object]) -> object:
        request_params = {**params, "api_key": self._api_key}
        try:
            response = self._session.get(
                f"{self._base_url}{path}",
                params=request_params,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.Timeout as error:
            raise USDARequestError("USDA request timed out") from error
        except requests.ConnectionError as error:
            raise USDARequestError("USDA connection failed") from error
        except requests.HTTPError as error:
            status = getattr(response, "status_code", "unknown")
            raise USDARequestError(f"USDA request failed with HTTP status {status}") from error
        except requests.RequestException as error:
            raise USDARequestError("USDA request failed") from error

        try:
            return response.json()
        except (TypeError, ValueError) as error:
            raise USDAResponseError("USDA response was not valid JSON") from error

    def search_foods(self, query: str, *, page_size: int = 25) -> list[FoodSearchResult]:
        """Return all mapped candidates for a query; never select one implicitly."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0:
            raise ValueError("page_size must be a positive integer")
        payload = self._get_json("/v1/foods/search", {"query": query, "pageSize": page_size})
        if not isinstance(payload, dict) or not isinstance(payload.get("foods"), list):
            raise USDAResponseError("USDA search response must contain a foods list")
        if not payload["foods"]:
            raise USDAEmptySearchError("USDA search returned no foods")

        results = []
        for food in payload["foods"]:
            if not isinstance(food, dict):
                raise USDAResponseError("USDA search food records must be objects")
            fdc_id = _food_id(food.get("fdcId"), "fdcId")
            description = _required_string(food.get("description"), "description")
            data_type = _required_string(food.get("dataType"), "dataType")
            serving_size = food.get("servingSize")
            if serving_size is not None:
                serving_size = _positive_finite_number(serving_size, "servingSize")
            serving_unit = food.get("servingSizeUnit")
            if serving_unit is not None and (not isinstance(serving_unit, str) or not serving_unit.strip()):
                raise USDAResponseError("servingSizeUnit must be a non-empty string")
            results.append(FoodSearchResult(fdc_id, description, data_type, serving_size, serving_unit))
        return results

    def get_food(self, fdc_id: int | str) -> USDAFoodRecord:
        """Retrieve and parse the explicitly selected FoodData Central ID."""
        selected_id = _food_id(fdc_id)
        payload = self._get_json(f"/v1/food/{selected_id}", {})
        if not isinstance(payload, dict):
            raise USDAResponseError("USDA food response must be an object")
        response_id = _food_id(payload.get("fdcId"), "fdcId")
        if response_id != selected_id:
            raise USDAResponseError("USDA response fdcId did not match the selected food")
        description = _required_string(payload.get("description"), "description")
        data_type = _required_string(payload.get("dataType"), "dataType")

        if isinstance(payload.get("labelNutrients"), dict) and payload.get("labelNutrients"):
            serving_size = _positive_finite_number(payload.get("servingSize"), "servingSize")
            serving_unit = _required_string(payload.get("servingSizeUnit"), "servingSizeUnit")
            values = _parse_label_nutrients(payload["labelNutrients"])

            # For gram-based branded servings, FoodData Central's foodNutrients
            # amounts are expressed per 100 g while labelNutrients are per the
            # declared serving. Use the per-100 g values only to fill label gaps,
            # scaling them to the serving. Do not infer a mass basis for ml or
            # other volume/household units because density may be unknown.
            gram_units = {"g", "grm", "gram", "grams"}
            if (
                serving_unit.strip().casefold() in gram_units
                and any(value is None for value in values.values())
            ):
                food_values = _parse_food_nutrients(payload.get("foodNutrients"))
                serving_scale = serving_size / 100.0
                for target, label_value in values.items():
                    if label_value is None:
                        food_value = food_values.get(target)
                        if food_value is not None:
                            values[target] = food_value * serving_scale

            reference_quantity = 1.0
            reference_unit = "serving"
        else:
            if data_type not in PER_100_GRAM_DATA_TYPES:
                raise USDAResponseError("USDA nutrient reference basis could not be determined")
            values = _parse_food_nutrients(payload.get("foodNutrients"))
            reference_quantity = 100.0
            reference_unit = "g"
            serving_size = None
            serving_unit = None

        return USDAFoodRecord(
            fdc_id=response_id,
            description=description,
            data_type=data_type,
            nutrients=NutrientProfile(**values),
            reference_quantity=reference_quantity,
            reference_unit=reference_unit,
            serving_size=serving_size,
            serving_size_unit=serving_unit,
        )
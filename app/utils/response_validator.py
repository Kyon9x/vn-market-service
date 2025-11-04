"""
Centralized response validation utilities to eliminate duplicated validation logic.
"""

import logging
from typing import Dict, Any, Optional
from app.constants import (
    ASSET_CLASSIFICATION,
    ASSET_TYPE_FUND,
    ASSET_TYPE_STOCK,
    ASSET_TYPE_INDEX,
    ASSET_TYPE_GOLD,
    CURRENCY_VND,
    CURRENCY_USD,
    DATA_SOURCE_VN_MARKET
)

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Centralized validator for API responses."""

    @staticmethod
    def validate_asset_classification(
        asset_type: str,
        asset_class: str,
        asset_sub_class: str
    ) -> bool:
        """
        Validate that the asset classification matches the expected values for the asset type.

        Args:
            asset_type: The type of asset (FUND, STOCK, INDEX, GOLD)
            asset_class: The asset class from response
            asset_sub_class: The asset sub-class from response

        Returns:
            bool: True if validation passes, False otherwise
        """
        asset_type = asset_type.upper()

        expected = ASSET_CLASSIFICATION.get(asset_type)
        if not expected:
            # For unknown asset types, allow any classification
            return True

        return (
            asset_class == expected["asset_class"] and
            asset_sub_class == expected["asset_sub_class"]
        )

    @staticmethod
    def validate_response_fields(
        response: Dict[str, Any],
        expected_asset_type: str,
        allow_missing_fields: bool = False
    ) -> bool:
        """
        Validate that the response contains all required fields with correct values.

        Args:
            response: The response dictionary to validate
            expected_asset_type: The expected asset type
            allow_missing_fields: If True, don't fail on missing fields

        Returns:
            bool: True if validation passes, False otherwise
        """
        required_fields = ["asset_class", "asset_sub_class", "currency", "data_source"]

        # Check that all required fields are present
        for field in required_fields:
            if field not in response:
                if not allow_missing_fields:
                    logger.warning(f"Missing required field: {field}")
                    return False
                else:
                    continue

        # Validate asset classification
        if not ResponseValidator.validate_asset_classification(
            expected_asset_type,
            response.get("asset_class", ""),
            response.get("asset_sub_class", "")
        ):
            logger.warning(f"Invalid asset classification for {expected_asset_type}")
            return False

        # Validate currency (should be VND or USD)
        currency = response.get("currency")
        if currency and currency not in [CURRENCY_VND, CURRENCY_USD]:
            logger.warning(f"Invalid currency: {currency}")
            return False

        # Validate data_source
        data_source = response.get("data_source")
        if data_source and data_source != DATA_SOURCE_VN_MARKET:
            logger.warning(f"Invalid data_source: {data_source}")
            return False

        return True

    @staticmethod
    def enrich_response_with_classification(
        response: Dict[str, Any],
        asset_type: str
    ) -> Dict[str, Any]:
        """
        Enrich a response dictionary with proper asset classification fields.

        Args:
            response: The response dictionary to enrich
            asset_type: The asset type (FUND, STOCK, INDEX, GOLD)

        Returns:
            The enriched response dictionary
        """
        asset_type = asset_type.upper()
        classification = ASSET_CLASSIFICATION.get(asset_type)

        if classification:
            response.update({
                "asset_class": classification["asset_class"],
                "asset_sub_class": classification["asset_sub_class"],
                "data_source": classification["data_source"]
            })

            # Set currency if not already set
            if "currency" not in response:
                response["currency"] = classification["currency"]

        return response

    @staticmethod
    def get_expected_classification(asset_type: str) -> Dict[str, str]:
        """
        Get the expected classification for an asset type.

        Args:
            asset_type: The asset type

        Returns:
            Dictionary with asset_class, asset_sub_class, currency, data_source
        """
        return ASSET_CLASSIFICATION.get(asset_type.upper(), {})

    @staticmethod
    def enrich_search_result(result_dict: Dict[str, Any], asset_type: str) -> Dict[str, Any]:
        """
        Enrich a search result dictionary with proper asset classification for search endpoints.

        Args:
            result_dict: The search result dictionary to enrich
            asset_type: The asset type (FUND, STOCK, INDEX, GOLD)

        Returns:
            The enriched search result dictionary
        """
        from app.constants import ASSET_TYPE_FUND, ASSET_TYPE_STOCK, ASSET_TYPE_INDEX, ASSET_TYPE_GOLD

        # Set asset_type if not present
        if "asset_type" not in result_dict:
            result_dict["asset_type"] = asset_type

        # Enrich with classification
        result_dict = ResponseValidator.enrich_response_with_classification(result_dict, asset_type)

        # Ensure all required fields for SearchResult are present
        if "exchange" not in result_dict:
            if asset_type == ASSET_TYPE_FUND:
                result_dict["exchange"] = "VN"
            elif asset_type == ASSET_TYPE_INDEX:
                symbol = result_dict.get("symbol", "")
                result_dict["exchange"] = "HOSE" if symbol.startswith("VN") else "HNX"
            else:
                result_dict["exchange"] = ""

        return result_dict

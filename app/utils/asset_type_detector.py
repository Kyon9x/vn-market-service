"""
Asset type detection utilities to eliminate duplicated logic in universal endpoints.
"""

from typing import Optional, Dict, Any
from app.constants import (
    INDEX_SYMBOLS,
    GOLD_PROVIDERS,
    ASSET_TYPE_INDEX,
    ASSET_TYPE_GOLD,
    ASSET_TYPE_FUND,
    ASSET_TYPE_STOCK
)


class AssetTypeDetector:
    """Utility for detecting asset types from symbols."""

    @staticmethod
    def detect_asset_type(symbol: str, clients: Optional[Dict[str, Any]] = None) -> str:
        """
        Detect the asset type from a symbol.

        Args:
            symbol: The symbol to analyze
            clients: Dictionary of client instances for validation

        Returns:
            Asset type string (FUND, STOCK, INDEX, GOLD)
        """
        symbol_upper = symbol.upper()

        # Check indices first (fastest check)
        if symbol_upper in INDEX_SYMBOLS:
            return ASSET_TYPE_INDEX

        # Check gold providers
        if symbol_upper in GOLD_PROVIDERS:
            return ASSET_TYPE_GOLD

        # Check gold patterns (more flexible)
        gold_patterns = ["gold", "vn gold", "vn_gold", "vngold", "sjc", "btmc", "msn"]
        symbol_normalized = symbol_upper.replace("_", " ").replace("-", " ").strip()
        if any(pattern.upper() in symbol_normalized for pattern in gold_patterns):
            return ASSET_TYPE_GOLD

        # Use clients for validation if available
        if clients:
            # Check funds
            fund_client = clients.get('fund_client')
            if fund_client:
                try:
                    fund_symbols = [f["symbol"] for f in fund_client.get_funds_list()]
                    if symbol_upper in fund_symbols:
                        return ASSET_TYPE_FUND
                except Exception:
                    pass  # Continue with other checks

        # Default to STOCK for remaining symbols
        return ASSET_TYPE_STOCK

    @staticmethod
    def get_asset_type_from_response(response: Dict[str, Any]) -> str:
        """
        Extract asset type from a response dictionary.

        Args:
            response: Response dictionary that may contain asset_type

        Returns:
            Asset type string
        """
        return response.get("asset_type", ASSET_TYPE_STOCK).upper()

    @staticmethod
    def is_index_symbol(symbol: str) -> bool:
        """Check if symbol is an index."""
        return symbol.upper() in INDEX_SYMBOLS

    @staticmethod
    def is_gold_symbol(symbol: str) -> bool:
        """Check if symbol is a gold provider."""
        symbol_upper = symbol.upper()
        return symbol_upper in GOLD_PROVIDERS or any(
            pattern.upper() in symbol_upper.replace("_", " ").replace("-", " ")
            for pattern in ["gold", "vn gold", "vn_gold", "vngold", "sjc", "btmc", "msn"]
        )

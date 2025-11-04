import random
from typing import Dict, Any, List


class TestDataGenerator:
    """Generate test data for BDD scenarios"""
    
    STOCK_SYMBOLS = ["VNM", "FPT", "ACB", "VCB", "TCB", "HPG", "MSN", "GAS", "BID", "CTG"]
    FUND_SYMBOLS = [ "SSIAMCA", "DCDS", "VCB", "VDCS", "VEOF", "VESAF", "VNDBF", "BVFED", "MAMF"]
    INDEX_SYMBOLS = ["VNINDEX", "HNXINDEX", "UPCOM", "VN30", "HNX30"]
    GOLD_SYMBOLS = ["VN.GOLD", "VN.GOLD.C"]
    
    INVALID_SYMBOLS = ["INVALID123", "NOTFOUND", "FAKE_SYMBOL"]
    
    @classmethod
    def get_random_stock_symbol(cls) -> str:
        return random.choice(cls.STOCK_SYMBOLS)
    
    @classmethod
    def get_random_fund_symbol(cls) -> str:
        return random.choice(cls.FUND_SYMBOLS)
    
    @classmethod
    def get_random_index_symbol(cls) -> str:
        return random.choice(cls.INDEX_SYMBOLS)
    
    @classmethod
    def get_random_gold_symbol(cls) -> str:
        return random.choice(cls.GOLD_SYMBOLS)
    
    @classmethod
    def get_invalid_symbol(cls) -> str:
        return random.choice(cls.INVALID_SYMBOLS)
    
    @classmethod
    def get_symbol_for_asset_type(cls, asset_type: str) -> str:
        """Get a random symbol for the specified asset type"""
        if asset_type.lower() == "stocks":
            return cls.get_random_stock_symbol()
        elif asset_type.lower() == "funds":
            return cls.get_random_fund_symbol()
        elif asset_type.lower() == "indices":
            return cls.get_random_index_symbol()
        elif asset_type.lower() == "gold":
            return cls.get_random_gold_symbol()
        else:
            raise ValueError(f"Unknown asset type: {asset_type}")
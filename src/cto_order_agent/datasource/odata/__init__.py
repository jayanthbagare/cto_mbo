"""Live SAP S/4HANA OData adapter (same port, same behavior)."""

from .client import ODataDataSource
from .mapping import (
    map_confirmation,
    map_material_stock,
    map_product,
    map_production_order,
    map_sales_order,
)

__all__ = [
    "ODataDataSource",
    "map_confirmation",
    "map_material_stock",
    "map_product",
    "map_production_order",
    "map_sales_order",
]

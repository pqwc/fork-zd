"""Окно создания bin — см. bin_creator_window."""
from src.features.tools.ui.bin_creator_window import BinCreatorWindow, get_bin_creator_window

# Совместимость со старым именем
BinCreatorDialog = BinCreatorWindow

__all__ = ["BinCreatorWindow", "BinCreatorDialog", "get_bin_creator_window"]

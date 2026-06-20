#!/usr/bin/env python3
"""Одноразовая миграция src/ на Feature-Sliced Design (FSD)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# (old relative to src/, new relative to src/)
FILE_MOVES: list[tuple[str, str]] = [
    # shared
    ("core/translator.py", "shared/i18n/translator.py"),
    ("core/path_utils.py", "shared/lib/path_utils.py"),
    ("core/version_utils.py", "shared/lib/version_utils.py"),
    ("core/text_encoding.py", "shared/lib/text_encoding.py"),
    ("core/github_utils.py", "shared/lib/github_utils.py"),
    ("core/app_logging.py", "shared/lib/app_logging.py"),
    ("ui/theme.py", "shared/ui/theme.py"),
    ("ui/standard_window.py", "shared/ui/standard_window.py"),
    ("ui/standard_dialog.py", "shared/ui/standard_dialog.py"),
    ("ui/message_box_utils.py", "shared/ui/message_box_utils.py"),
    ("ui/system_tray.py", "shared/ui/system_tray.py"),
    ("ui/update_progress.py", "shared/ui/update_progress.py"),
    ("core/window_styles.py", "shared/ui/window_styles.py"),
    ("core/native_window_styles.py", "shared/ui/native_window_styles.py"),
    ("core/embedded_assets.py", "shared/ui/assets/embedded_assets.py"),
    ("core/embedded_style.py", "shared/ui/assets/embedded_style.py"),
    ("core/codicons_manager.py", "shared/ui/assets/codicons_manager.py"),
    ("core/codicon_utils.py", "shared/ui/assets/codicon_utils.py"),
    # entities
    ("core/config_manager.py", "entities/config/config_manager.py"),
    ("core/winws_manager.py", "entities/winws/winws_manager.py"),
    ("core/winws_version.py", "entities/winws/winws_version.py"),
    ("core/bat_generator.py", "entities/strategy/bat_generator.py"),
    ("core/diagnostics_runner.py", "entities/diagnostics/diagnostics_runner.py"),
    ("core/diagnostics_config.py", "entities/diagnostics/diagnostics_config.py"),
    ("core/network_status.py", "entities/network/network_status.py"),
    ("core/domain_variants.py", "entities/domain/domain_variants.py"),
    ("core/zapret_updater.py", "entities/zapret/zapret_updater.py"),
    # features
    ("core/app_updater.py", "features/updates/app_updater.py"),
    ("core/autostart_manager.py", "features/autostart/autostart_manager.py"),
    ("core/export_bundle.py", "features/export/export_bundle.py"),
    ("dialogs/settings_dialog.py", "features/settings/ui/settings_dialog.py"),
    ("dialogs/diagnostics_dialog.py", "features/diagnostics/ui/diagnostics_dialog.py"),
    ("dialogs/winws_setup_dialog.py", "features/winws_setup/ui/winws_setup_dialog.py"),
    ("dialogs/vs_update_dialog.py", "features/updates/ui/vs_update_dialog.py"),
    ("dialogs/addons_dialog.py", "features/updates/ui/addons_dialog.py"),
    ("dialogs/strategy_creator_window.py", "features/strategy/ui/strategy_creator_window.py"),
    ("dialogs/bin_creator_dialog.py", "features/tools/ui/bin_creator_dialog.py"),
    ("dialogs/export_bundle_dialog.py", "features/export/ui/export_bundle_dialog.py"),
    ("dialogs/country_blocklist_dialog.py", "features/editor/ui/country_blocklist_dialog.py"),
    ("dialogs/domain_variants_dialog.py", "features/editor/ui/domain_variants_dialog.py"),
    ("dialogs/find_replace_dialog.py", "features/editor/ui/find_replace_dialog.py"),
    ("dialogs/find_in_files_dialog.py", "features/editor/ui/find_in_files_dialog.py"),
    ("dialogs/critical_error_dialog.py", "app/critical_error_dialog.py"),
    ("dialogs/first_run_window.py", "features/setup/ui/first_run_window.py"),
    ("editor/unified_editor_window.py", "features/editor/ui/unified_editor_window.py"),
    ("editor/lists_editor_window.py", "features/editor/ui/lists_editor_window.py"),
    ("editor/etcdrivers_editor_window.py", "features/editor/ui/etcdrivers_editor_window.py"),
    ("editor/line_number_editor.py", "features/editor/lib/line_number_editor.py"),
    ("editor/editor_highlighters.py", "features/editor/lib/editor_highlighters.py"),
    ("editor/editor_prompts.py", "features/editor/lib/editor_prompts.py"),
    ("editor/editor_autocomplete.py", "features/editor/lib/editor_autocomplete.py"),
    # pages
    ("ui/main_window/window.py", "pages/main/window.py"),
    ("ui/main_window/workers.py", "pages/main/workers.py"),
    ("ui/main_window/__init__.py", "pages/main/__init__.py"),
    ("ui/test_window.py", "pages/test/test_window.py"),
]

MIXIN_DIR = SRC / "ui" / "main_window" / "mixins"
NEW_MIXIN_DIR = SRC / "pages" / "main" / "mixins"

# Замены импортов: длинные пути первыми
IMPORT_REPLACEMENTS: list[tuple[str, str]] = [
    ("from src.shared.i18n.translator import", "from src.shared.i18n.translator import"),
    ("from src.shared.lib.path_utils import", "from src.shared.lib.path_utils import"),
    ("from src.shared.lib.version_utils import", "from src.shared.lib.version_utils import"),
    ("from src.shared.lib.text_encoding import", "from src.shared.lib.text_encoding import"),
    ("from src.shared.lib.github_utils import", "from src.shared.lib.github_utils import"),
    ("from src.shared.lib.app_logging import", "from src.shared.lib.app_logging import"),
    ("from src.entities.config.config_manager import", "from src.entities.config.config_manager import"),
    ("from src.entities.winws.winws_manager import", "from src.entities.winws.winws_manager import"),
    ("from src.entities.winws.winws_version import", "from src.entities.winws.winws_version import"),
    ("from src.entities.strategy.bat_generator import", "from src.entities.strategy.bat_generator import"),
    ("from src.entities.diagnostics.diagnostics_runner import", "from src.entities.diagnostics.diagnostics_runner import"),
    ("from src.entities.diagnostics.diagnostics_config import", "from src.entities.diagnostics.diagnostics_config import"),
    ("from src.entities.network.network_status import", "from src.entities.network.network_status import"),
    ("from src.entities.domain.domain_variants import", "from src.entities.domain.domain_variants import"),
    ("from src.entities.zapret.zapret_updater import", "from src.entities.zapret.zapret_updater import"),
    ("from src.features.updates.app_updater import", "from src.features.updates.app_updater import"),
    ("from src.features.autostart.autostart_manager import", "from src.features.autostart.autostart_manager import"),
    ("from src.features.export.export_bundle import", "from src.features.export.export_bundle import"),
    ("from src.shared.ui.assets.embedded_assets import", "from src.shared.ui.assets.embedded_assets import"),
    ("from src.shared.ui.assets.embedded_style import", "from src.shared.ui.assets.embedded_style import"),
    ("from src.shared.ui.assets.codicons_manager import", "from src.shared.ui.assets.codicons_manager import"),
    ("from src.shared.ui.assets.codicon_utils import", "from src.shared.ui.assets.codicon_utils import"),
    ("from src.shared.ui.window_styles import", "from src.shared.ui.window_styles import"),
    ("from src.shared.ui.native_window_styles import", "from src.shared.ui.native_window_styles import"),
    ("from src.shared.ui.standard_window import", "from src.shared.ui.standard_window import"),
    ("from src.shared.ui.standard_dialog import", "from src.shared.ui.standard_dialog import"),
    ("from src.shared.ui.message_box_utils import", "from src.shared.ui.message_box_utils import"),
    ("from src.shared.ui.system_tray import", "from src.shared.ui.system_tray import"),
    ("from src.shared.ui.update_progress import", "from src.shared.ui.update_progress import"),
    ("from src.pages.main import", "from src.pages.main import"),
    ("from src.pages.main.", "from src.pages.main."),
    ("from src.pages.test.test_window import", "from src.pages.test.test_window import"),
    ("from src.features.settings.ui.settings_dialog import", "from src.features.settings.ui.settings_dialog import"),
    ("from src.features.diagnostics.ui.diagnostics_dialog import", "from src.features.diagnostics.ui.diagnostics_dialog import"),
    ("from src.features.winws_setup.ui.winws_setup_dialog import", "from src.features.winws_setup.ui.winws_setup_dialog import"),
    ("from src.features.updates.ui.vs_update_dialog import", "from src.features.updates.ui.vs_update_dialog import"),
    ("from src.features.updates.ui.addons_dialog import", "from src.features.updates.ui.addons_dialog import"),
    ("from src.features.strategy.ui.strategy_creator_window import", "from src.features.strategy.ui.strategy_creator_window import"),
    ("from src.features.tools.ui.bin_creator_dialog import", "from src.features.tools.ui.bin_creator_dialog import"),
    ("from src.features.export.ui.export_bundle_dialog import", "from src.features.export.ui.export_bundle_dialog import"),
    ("from src.features.editor.ui.country_blocklist_dialog import", "from src.features.editor.ui.country_blocklist_dialog import"),
    ("from src.features.editor.ui.domain_variants_dialog import", "from src.features.editor.ui.domain_variants_dialog import"),
    ("from src.features.editor.ui.find_replace_dialog import", "from src.features.editor.ui.find_replace_dialog import"),
    ("from src.features.editor.ui.find_in_files_dialog import", "from src.features.editor.ui.find_in_files_dialog import"),
    ("from src.app.critical_error_dialog import", "from src.app.critical_error_dialog import"),
    ("from src.features.setup.ui.first_run_window import", "from src.features.setup.ui.first_run_window import"),
    ("from src.features.editor.ui.unified_editor_window import", "from src.features.editor.ui.unified_editor_window import"),
    ("from src.features.editor.ui.lists_editor_window import", "from src.features.editor.ui.lists_editor_window import"),
    ("from src.features.editor.ui.etcdrivers_editor_window import", "from src.features.editor.ui.etcdrivers_editor_window import"),
    ("from src.features.editor.lib.line_number_editor import", "from src.features.editor.lib.line_number_editor import"),
    ("from src.features.editor.lib.editor_highlighters import", "from src.features.editor.lib.editor_highlighters import"),
    ("from src.features.editor.lib.editor_prompts import", "from src.features.editor.lib.editor_prompts import"),
    ("from src.features.editor.lib.editor_autocomplete import", "from src.features.editor.lib.editor_autocomplete import"),
    ("from src.shared.ui import theme", "from src.shared.ui import theme"),
    ("import src.shared.ui.theme", "import src.shared.ui.theme"),
    ("from src.shared.ui import native_window_styles", "from src.shared.ui import native_window_styles"),
]

INTERNAL_REPLACEMENTS: list[tuple[str, str]] = [
    ("from .path_utils import", "from src.shared.lib.path_utils import"),
    ("from .app_logging import", "from src.shared.lib.app_logging import"),
    ("from .version_utils import", "from src.shared.lib.version_utils import"),
    ("from .github_utils import", "from src.shared.lib.github_utils import"),
    ("from .codicons_manager import", "from src.shared.ui.assets.codicons_manager import"),
    ("from .embedded_assets import", "from src.shared.ui.assets.embedded_assets import"),
    ("from .diagnostics_config import", "from src.entities.diagnostics.diagnostics_config import"),
]

PACKAGE_DIRS = [
    "app",
    "shared",
    "shared/i18n",
    "shared/lib",
    "shared/ui",
    "shared/ui/assets",
    "entities",
    "entities/config",
    "entities/winws",
    "entities/strategy",
    "entities/diagnostics",
    "entities/network",
    "entities/domain",
    "entities/zapret",
    "features",
    "features/settings/ui",
    "features/diagnostics/ui",
    "features/winws_setup/ui",
    "features/updates/ui",
    "features/strategy/ui",
    "features/tools/ui",
    "features/export/ui",
    "features/editor/ui",
    "features/editor/lib",
    "features/autostart",
    "features/setup/ui",
    "pages",
    "pages/main",
    "pages/main/mixins",
    "pages/test",
    "widgets",
]


def ensure_packages() -> None:
    for rel in PACKAGE_DIRS:
        pkg = SRC / rel
        pkg.mkdir(parents=True, exist_ok=True)
        init = pkg / "__init__.py"
        if not init.exists():
            init.write_text('"""FSD package."""\n', encoding="utf-8")


def move_files() -> None:
    for old_rel, new_rel in FILE_MOVES:
        old = SRC / old_rel.replace("/", "\\") if "\\" in str(SRC) else SRC / old_rel
        new = SRC / new_rel
        new.parent.mkdir(parents=True, exist_ok=True)
        if old.exists():
            shutil.move(str(old), str(new))
            print(f"  moved {old_rel} -> {new_rel}")
        else:
            print(f"  SKIP (missing): {old_rel}")

    if MIXIN_DIR.exists():
        for f in MIXIN_DIR.glob("*.py"):
            dest = NEW_MIXIN_DIR / f.name
            shutil.move(str(f), str(dest))
            print(f"  moved mixins/{f.name} -> pages/main/mixins/{f.name}")


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in IMPORT_REPLACEMENTS:
        text = text.replace(old, new)
    if path.is_relative_to(SRC):
        for old, new in INTERNAL_REPLACEMENTS:
            text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_all() -> int:
    count = 0
    for path in ROOT.rglob("*.py"):
        if ".git" in path.parts or "build" in path.parts or "dist" in path.parts:
            continue
        if patch_file(path):
            count += 1
            print(f"  patched {path.relative_to(ROOT)}")
    return count


def cleanup_empty_dirs() -> None:
    for name in ("core", "ui", "dialogs", "editor"):
        d = SRC / name
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
            print(f"  removed {d.relative_to(ROOT)}")


def main() -> int:
    print("=== FSD migration ===")
    print("1. Creating packages...")
    ensure_packages()
    print("2. Moving files...")
    move_files()
    print("3. Patching imports...")
    n = patch_all()
    print(f"   {n} files patched")
    print("4. Cleanup old dirs...")
    cleanup_empty_dirs()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

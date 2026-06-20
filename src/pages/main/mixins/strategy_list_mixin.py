"""strategy_list_mixin methods for MainWindow."""
import os

from PyQt6.QtCore import Qt, QFileSystemWatcher, QSize
from PyQt6.QtWidgets import QListWidgetItem
from src.shared.i18n.translator import tr, tr_platform
from src.shared.lib.path_utils import get_base_path, get_winws_path
from src.shared.ui import theme
from src.platform import is_linux, linux_runtime_configured, get_runtime_backend
import psutil

_STRATEGY_ROLE = Qt.ItemDataRole.UserRole
_EXT_STRATEGY_KEY = "__external_winws__"
_HEADER_FAVORITES = "__header_favorites__"
_HEADER_STRATEGIES = "__header_strategies__"


class StrategyListMixin:
    def _is_list_section_header(self, data) -> bool:
        return data in (_HEADER_FAVORITES, _HEADER_STRATEGIES)

    def _add_list_section_header(self, key: str, title: str) -> None:
        from PyQt6.QtGui import QFont, QColor

        item = QListWidgetItem(title)
        item.setData(_STRATEGY_ROLE, key)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setSizeHint(QSize(0, 24))
        font = item.font()
        font.setPointSize(10)
        font.setWeight(QFont.Weight.DemiBold)
        item.setFont(font)
        item.setForeground(QColor(theme.palette().fg_muted))
        self.strategy_list.addItem(item)

    def _retranslate_strategy_list_headers(self) -> None:
        lang = self.settings.get("language", "ru")
        titles = {
            _HEADER_FAVORITES: tr("home_section_favorites", lang),
            _HEADER_STRATEGIES: tr("home_section_strategies", lang),
        }
        for i in range(self.strategy_list.count()):
            item = self.strategy_list.item(i)
            if item is None:
                continue
            data = item.data(_STRATEGY_ROLE)
            if data in titles:
                item.setText(titles[data])

    def _get_favorite_strategies(self) -> list[str]:
        fav = self.settings.get("favorite_strategies", [])
        if not isinstance(fav, list):
            return []
        return [str(x) for x in fav if x]

    def _is_strategy_favorite(self, name: str) -> bool:
        if not name or name == _EXT_STRATEGY_KEY:
            return False
        return name in self._get_favorite_strategies()

    def _set_strategy_favorite(self, name: str, favorite: bool) -> None:
        if not name or name == _EXT_STRATEGY_KEY:
            return
        fav = list(self._get_favorite_strategies())
        if favorite and name not in fav:
            fav.append(name)
        elif not favorite and name in fav:
            fav.remove(name)
        self._persist_setting("favorite_strategies", fav, silent=True)

    def _toggle_selected_strategy_favorite(self) -> None:
        name = self._get_selected_strategy_name()
        if not name or name == _EXT_STRATEGY_KEY:
            return
        self._set_strategy_favorite(name, not self._is_strategy_favorite(name))
        self.load_bat_files()
        if hasattr(self, "_update_strategy_detail_panel"):
            self._update_strategy_detail_panel()

    def _sort_strategy_names(self, names: list[str]) -> list[str]:
        fav = set(self._get_favorite_strategies())
        favorites = sorted(n for n in names if n in fav)
        regular = sorted(n for n in names if n not in fav)
        return favorites + regular

    def _apply_favorite_icon_to_item(self, item: QListWidgetItem, name: str) -> None:
        from PyQt6.QtGui import QIcon
        from src.shared.ui.assets.codicon_utils import codicon_icon

        if self._is_strategy_favorite(name):
            icon = codicon_icon("star-full", 14)
            if not icon.isNull():
                item.setIcon(icon)
                return
        item.setIcon(QIcon())

    def load_bat_files(self):
        """Загружает названия .bat файлов из папки winws в список стратегий."""
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        bat_files = []

        if is_linux() and not linux_runtime_configured():
            self.strategy_list.clear()
            item = QListWidgetItem(tr('linux_runtime_not_configured', lang))
            item.setData(_STRATEGY_ROLE, tr('msg_winws_not_found', lang))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.strategy_list.addItem(item)
            return

        if is_linux():
            bat_files = [s.name for s in get_runtime_backend().list_strategies()]
        elif os.path.exists(winws_folder):
            for filename in os.listdir(winws_folder):
                if (
                    filename.endswith('.bat')
                    and filename != 'service.bat'
                    and os.path.isfile(os.path.join(winws_folder, filename))
                ):
                    bat_files.append(filename[:-4])

        current_strategy = self._get_selected_strategy_name()

        self.strategy_list.clear()
        if bat_files:
            favorites = sorted(n for n in bat_files if self._is_strategy_favorite(n))
            regular = sorted(n for n in bat_files if not self._is_strategy_favorite(n))

            if favorites:
                self._add_list_section_header(
                    _HEADER_FAVORITES, tr("home_section_favorites", lang)
                )
                for name in favorites:
                    item = QListWidgetItem(name)
                    item.setData(_STRATEGY_ROLE, name)
                    self._apply_favorite_icon_to_item(item, name)
                    self.strategy_list.addItem(item)

            if regular:
                if favorites:
                    self._add_list_section_header(
                        _HEADER_STRATEGIES, tr("home_section_strategies", lang)
                    )
                for name in regular:
                    item = QListWidgetItem(name)
                    item.setData(_STRATEGY_ROLE, name)
                    self.strategy_list.addItem(item)

            index = self._find_strategy_index_by_data(current_strategy)
            if index >= 0:
                self.strategy_list.setCurrentRow(index)
        elif os.path.exists(winws_folder) or (is_linux() and linux_runtime_configured()):
            item = QListWidgetItem(tr('msg_no_bat_files', lang))
            item.setData(_STRATEGY_ROLE, None)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.strategy_list.addItem(item)
        else:
            item = QListWidgetItem(tr('msg_winws_not_found', lang))
            item.setData(_STRATEGY_ROLE, None)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.strategy_list.addItem(item)

        if hasattr(self, 'strategy_search') and self.strategy_search.text().strip():
            self._apply_strategy_filter(self.strategy_search.text())

        self._refresh_strategy_display()
        if hasattr(self, "_apply_strategy_list_visual_state"):
            self._apply_strategy_list_visual_state()

    def _init_winws_watcher(self):
        """Инициализирует наблюдение за папкой winws."""
        try:
            if self.winws_watcher.files():
                self.winws_watcher.removePaths(self.winws_watcher.files())
            if self.winws_watcher.directories():
                self.winws_watcher.removePaths(self.winws_watcher.directories())
        except Exception:
            pass

        base_dir = get_base_path()
        winws_folder = get_winws_path()

        dirs_to_watch = set()
        if os.path.isdir(base_dir):
            dirs_to_watch.add(os.path.abspath(base_dir))
        parent_winws = os.path.dirname(winws_folder)
        if parent_winws and os.path.isdir(parent_winws):
            dirs_to_watch.add(os.path.abspath(parent_winws))
        if os.path.isdir(winws_folder):
            dirs_to_watch.add(os.path.abspath(winws_folder))
        if is_linux():
            for sub in ("zapret-latest", "custom-strategies"):
                nested = os.path.join(winws_folder, sub)
                if os.path.isdir(nested):
                    dirs_to_watch.add(os.path.abspath(nested))

        try:
            if dirs_to_watch:
                self.winws_watcher.addPaths(list(dirs_to_watch))
        except Exception:
            pass

    def _on_winws_dir_changed(self, path: str):
        """Обработчик изменений в файловой системе для автодетекта winws."""
        if getattr(self, "_winws_watcher_paused", False):
            return
        try:
            self._init_winws_watcher()
        except Exception:
            pass

        try:
            self.load_bat_files()
        except Exception:
            pass

    def _get_selected_strategy_name(self):
        """Возвращает идентификатор стратегии (без украшений), если выбран реальный .bat."""
        try:
            item = self.strategy_list.currentItem()
            if item is not None:
                data = item.data(_STRATEGY_ROLE)
                if isinstance(data, str) and data:
                    if self._is_list_section_header(data):
                        return ""
                    return data
                if data is None:
                    return item.text()
        except Exception:
            pass
        return ""

    def _find_strategy_index_by_data(self, data):
        """Ищет строку списка по userData."""
        try:
            for i in range(self.strategy_list.count()):
                item = self.strategy_list.item(i)
                if item is not None and item.data(_STRATEGY_ROLE) == data:
                    return i
        except Exception:
            return -1
        return -1

    def _find_combo_index_by_data(self, data):
        """Совместимость со старым API ComboBox."""
        return self._find_strategy_index_by_data(data)

    def _select_strategy_by_data(self, data: str) -> bool:
        index = self._find_strategy_index_by_data(data)
        if index >= 0:
            self.strategy_list.setCurrentRow(index)
            return True
        return False

    def _set_strategy_item_text(self, index: int, text: str) -> None:
        try:
            item = self.strategy_list.item(index)
            if item is not None:
                item.setText(text)
        except Exception:
            return

    def _set_combo_item_text(self, index: int, text: str) -> None:
        self._set_strategy_item_text(index, text)

    def _get_running_winws_process(self):
        """Возвращает процесс runtime: winws.exe или nfqws."""
        stored = None
        if hasattr(self, "_get_stored_winws_pid"):
            stored = self._get_stored_winws_pid()
        mgr = getattr(self, "winws_manager", None)
        if mgr is not None:
            return mgr.get_running_process(stored)
        target = "nfqws" if is_linux() else "winws.exe"
        if stored:
            try:
                proc = psutil.Process(stored)
                if proc.is_running() and (proc.name() or "").lower() == target:
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info.get('name', '').lower() == target:
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            return None
        return None

    def _guess_winws_root_from_process(self, proc):
        """Корень winws только при валидной установке zapret (service.bat + bin/winws.exe)."""
        from src.entities.winws.winws_version import resolve_winws_root_from_process

        return resolve_winws_root_from_process(proc)

    def _get_running_winws_version_and_pid(self):
        """Возвращает (version, pid, winws_root) для запущенного winws.exe, если возможно."""
        proc = self._get_running_winws_process()
        if not proc:
            return (None, None, None)
        pid = None
        try:
            pid = proc.pid
        except Exception:
            pid = None
        winws_root = self._guess_winws_root_from_process(proc)
        version = None
        try:
            from src.entities.winws.winws_version import read_local_version_from_winws_root

            if winws_root:
                version = read_local_version_from_winws_root(winws_root)
        except Exception:
            version = None
        return (version, pid, winws_root)

    def _refresh_strategy_display(self):
        """
        Обновляет тексты в списке стратегий:
        - версия из service.bat
        - отдельный пункт для внешнего winws
        """
        ext_key = _EXT_STRATEGY_KEY
        try:
            from src.entities.winws.winws_version import read_local_version_from_winws_root
            base_version = read_local_version_from_winws_root(get_winws_path()) or "unknown"
        except Exception:
            base_version = "unknown"

        try:
            for i in range(self.strategy_list.count()):
                item = self.strategy_list.item(i)
                if item is None:
                    continue
                data = item.data(_STRATEGY_ROLE)
                if isinstance(data, str) and data:
                    if data == ext_key:
                        continue
                    if self._is_list_section_header(data):
                        continue
                    item.setText(f"{data} {base_version}")
        except Exception:
            return

        runtime_active = getattr(self, "is_running", False)
        if hasattr(self, "_ui_shows_running"):
            runtime_active = self._ui_shows_running()
        elif hasattr(self, "_runtime_process_active"):
            runtime_active = runtime_active or self._runtime_process_active()

        if not runtime_active:
            try:
                idx = self._find_strategy_index_by_data(ext_key)
                if idx >= 0:
                    self.strategy_list.takeItem(idx)
            except Exception:
                pass
            if hasattr(self, "_update_strategy_detail_panel"):
                self._update_strategy_detail_panel()
            if hasattr(self, "_apply_strategy_list_visual_state"):
                self._apply_strategy_list_visual_state()
            return

        external = not self._is_own_winws_session() if hasattr(self, "_is_own_winws_session") else (
            not getattr(self, "_started_winws_this_session", False)
        )
        version = base_version
        lang = self.settings.get("language", "ru")
        if external:
            v_proc, _pid_proc, _root = self._get_running_winws_version_and_pid()
            if v_proc:
                version = v_proc
            else:
                version = tr("home_winws_version_unknown", lang)

        if self.running_strategy:
            idx = self._find_strategy_index_by_data(self.running_strategy)
            if idx >= 0:
                self._set_strategy_item_text(idx, f"{self.running_strategy} {version}")
                if hasattr(self, "_update_strategy_detail_panel"):
                    self._update_strategy_detail_panel()
                if hasattr(self, "_apply_strategy_list_visual_state"):
                    self._apply_strategy_list_visual_state()
                return

        ext_title = tr_platform("home_external_winws_title", lang)
        display = f"{ext_title} {version}"

        ext_idx = self._find_strategy_index_by_data(ext_key)
        if ext_idx < 0:
            item = QListWidgetItem(display)
            item.setData(_STRATEGY_ROLE, ext_key)
            self.strategy_list.insertItem(0, item)
            ext_idx = 0
        else:
            self._set_strategy_item_text(ext_idx, display)

        if self.strategy_list.currentRow() != ext_idx:
            self.strategy_list.setCurrentRow(ext_idx)

        if hasattr(self, "_update_strategy_detail_panel"):
            self._update_strategy_detail_panel()
        if hasattr(self, "_apply_strategy_list_visual_state"):
            self._apply_strategy_list_visual_state()

    def _active_running_strategy_index(self) -> int:
        """Индекс строки запущенной стратегии в списке (-1 если не запущено)."""
        if not getattr(self, "is_running", False):
            return -1
        if self.running_strategy:
            idx = self._find_strategy_index_by_data(self.running_strategy)
            if idx >= 0:
                return idx
        return self._find_strategy_index_by_data(_EXT_STRATEGY_KEY)

    def _lock_strategy_list_to_running(self) -> None:
        """Не даёт выбрать другую стратегию, пока текущая запущена."""
        if not hasattr(self, "strategy_list") or self.strategy_list is None:
            return
        active_idx = self._active_running_strategy_index()
        if active_idx < 0:
            return
        row = self.strategy_list.currentRow()
        if row != active_idx:
            self.strategy_list.blockSignals(True)
            self.strategy_list.setCurrentRow(active_idx)
            self.strategy_list.blockSignals(False)

    def eventFilter(self, obj, event):
        """Блокирует клики/клавиши по другим стратегиям при is_running."""
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if (
            getattr(self, "_runtime_locks_strategy_list", lambda: getattr(self, "is_running", False))()
            and hasattr(self, "strategy_list")
            and self.strategy_list is not None
            and obj is self.strategy_list.viewport()
        ):
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
            ):
                item = self.strategy_list.itemAt(event.pos())
                if item is not None:
                    active_idx = self._active_running_strategy_index()
                    if active_idx >= 0 and self.strategy_list.row(item) != active_idx:
                        return True
            if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                if event.key() in (
                    Qt.Key.Key_Up,
                    Qt.Key.Key_Down,
                    Qt.Key.Key_PageUp,
                    Qt.Key.Key_PageDown,
                    Qt.Key.Key_Home,
                    Qt.Key.Key_End,
                ):
                    return True
        return super().eventFilter(obj, event)

    def _apply_strategy_list_visual_state(self) -> None:
        """Подсветка запущенной стратегии; остальные — приглушённые, без выбора."""
        from PyQt6.QtGui import QBrush, QColor

        p = theme.palette()
        ext_key = _EXT_STRATEGY_KEY
        active_idx = -1

        if getattr(self, "is_running", False):
            if self.running_strategy:
                active_idx = self._find_strategy_index_by_data(self.running_strategy)
            if active_idx < 0:
                active_idx = self._find_strategy_index_by_data(ext_key)

        dim = QColor(p.fg_muted)
        dim.setAlpha(120)

        for i in range(self.strategy_list.count()):
            item = self.strategy_list.item(i)
            if item is None:
                continue
            data = item.data(_STRATEGY_ROLE)

            if self._is_list_section_header(data):
                item.setBackground(QBrush())
                item.setForeground(QBrush(theme.qcolor(p.fg_muted)))
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                continue

            if getattr(self, "is_running", False):
                if i == active_idx and active_idx >= 0:
                    item.setBackground(QBrush(theme.qcolor(p.accent)))
                    item.setForeground(QBrush(QColor("#ffffff")))
                    item.setFlags(
                        Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    )
                else:
                    item.setBackground(QBrush())
                    item.setForeground(QBrush(dim))
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                item.setBackground(QBrush())
                item.setForeground(QBrush())
                flags = Qt.ItemFlag.ItemIsEnabled
                if isinstance(data, str) and data:
                    flags |= Qt.ItemFlag.ItemIsSelectable
                item.setFlags(flags)

        if active_idx >= 0 and getattr(self, "is_running", False):
            self.strategy_list.blockSignals(True)
            self.strategy_list.setCurrentRow(active_idx)
            self.strategy_list.blockSignals(False)

    def _detect_running_strategy(self, proc=None):
        """Определяет запущенную стратегию."""
        if is_linux():
            mgr = getattr(self, "winws_manager", None)
            if mgr is not None and hasattr(mgr, "get_configured_strategy"):
                if proc is None and not mgr.is_running():
                    return None
                name = mgr.get_configured_strategy()
                if name:
                    from src.platform.linux.conf_env import strategy_base_name
                    return strategy_base_name(name)
            return None
        try:
            if proc is None:
                proc = self._get_running_winws_process()
            if not proc:
                return None
            try:
                cmdline = proc.cmdline()
                proc_cmdline = ' '.join(cmdline) if cmdline else ''
                proc_exe = proc.exe() or ''
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                return None
            if not proc_cmdline or 'winws.exe' not in proc_cmdline.lower():
                return None
            if not proc_exe:
                return None

            exe_path = os.path.abspath(proc_exe)
            bin_folder = os.path.dirname(exe_path)
            winws_folder = os.path.abspath(os.path.join(bin_folder, os.pardir))
            if not os.path.isdir(winws_folder):
                return None

            bin_path = os.path.normpath(os.path.join(winws_folder, 'bin'))
            lists_path = os.path.normpath(os.path.join(winws_folder, 'lists'))
            proc_norm = proc_cmdline
            for p, ph in [(bin_path, 'BIN'), (lists_path, 'LISTS')]:
                proc_norm = proc_norm.replace(p, ph).replace(p.replace('\\', '/'), ph)
            if 'winws.exe' in proc_norm.lower():
                idx = proc_norm.lower().find('winws.exe')
                proc_norm = proc_norm[idx + len('winws.exe'):].strip()
            best_match = None
            best_score = 0
            for filename in os.listdir(winws_folder):
                if not filename.endswith('.bat') or filename == 'service.bat':
                    continue
                strategy_name = filename[:-4]
                bat_path = os.path.join(winws_folder, filename)
                if not os.path.isfile(bat_path):
                    continue
                try:
                    with open(bat_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    continue
                bat_args = ''
                for line in content.splitlines():
                    if 'winws.exe' in line.lower():
                        idx = line.lower().find('winws.exe')
                        part = line[idx + len('winws.exe'):].strip()
                        part = part.rstrip('^').strip()
                        bat_args += ' ' + part
                    elif bat_args and line.strip().startswith('--'):
                        bat_args += ' ' + line.strip().rstrip('^').strip()
                bat_args = bat_args.strip()
                if not bat_args:
                    continue
                bat_norm = bat_args.replace('%BIN%', 'BIN').replace('%LISTS%', 'LISTS').replace('%GameFilter%', '')
                bat_norm = bat_norm.replace('"', ' ').replace('\\', '/')
                proc_norm_clean = proc_norm.replace('"', ' ').replace('\\', '/')
                bat_tokens = set(t for t in bat_norm.split() if t.startswith('--') and '=' in t)
                if not bat_tokens:
                    continue
                matches = sum(1 for t in bat_tokens if t in proc_norm_clean)
                score = matches / len(bat_tokens) if bat_tokens else 0
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = strategy_name
            return best_match
        except Exception:
            return None

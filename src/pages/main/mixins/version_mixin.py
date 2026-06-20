"""version_mixin methods for MainWindow."""
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import QLabel

from src.entities.config.config_manager import VERSION
from src.shared.i18n.translator import tr
from src.entities.zapret.zapret_updater import ZapretUpdater
from src.shared.ui import theme
from src.widgets.style_menu import StyleMenu


class VersionMixin:
    def _app_update_repo_slug(self) -> str:
        repo = getattr(self, "app_updater", None)
        if repo is not None:
            slug = (getattr(repo, "github_repo", "") or "").strip()
            if slug:
                return slug
        return self._resolved_app_repo()

    def _resolved_app_repo(self) -> str:
        from src.entities.config.config_manager import ConfigManager, DEFAULT_APP_GITHUB_REPO
        from src.shared.lib.github_utils import resolve_github_repo

        default = DEFAULT_APP_GITHUB_REPO
        try:
            raw = (self.settings.get("app_repo") or ConfigManager().get_setting("app_repo", "") or "").strip()
        except Exception:
            raw = ""
        return resolve_github_repo(raw, default)

    def _zapret_repo_slug(self) -> str:
        from src.entities.config.config_manager import ConfigManager
        from src.shared.lib.github_utils import resolve_github_repo

        default = ZapretUpdater.GITHUB_REPO
        try:
            raw = (self.settings.get("zapret_repo") or ConfigManager().get_setting("zapret_repo", "") or "").strip()
        except Exception:
            raw = ""
        return resolve_github_repo(raw, default)

    def _zapret_repo_owner(self) -> str:
        slug = self._zapret_repo_slug()
        if "/" in slug:
            return slug.split("/", 1)[0]
        return slug or "Flowseal"

    def _zapret_repo_url(self) -> str:
        return f"https://github.com/{self._zapret_repo_slug()}"

    def _app_release_url(self, version: str) -> str:
        repo = self._app_update_repo_slug()
        return f"https://github.com/{repo}/releases/tag/{version}"

    def _app_repo_url(self) -> str:
        return f"https://github.com/{self._app_update_repo_slug()}"

    def load_version_info(self):
        """Совместимость: обновляет нижнюю строку статуса."""
        self.load_footer_info()

    def load_zapret_provider_info(self):
        """Совместимость: обновляет нижнюю строку статуса."""
        self.load_footer_info()

    def load_footer_info(self):
        """Одна строка: обновления программы и источник стратегий."""
        if not hasattr(self, "footer_label"):
            return

        version = VERSION
        p = theme.palette()
        accent = p.accent
        muted = p.fg_muted
        lang = self.settings.get("language", "ru")

        app_repo = self._app_update_repo_slug()
        app_repo_url = self._app_repo_url()
        app_repo_link = (
            f'<a style="color:{accent}; text-decoration:none;" href="{app_repo_url}">{app_repo}</a>'
        )
        release_url = self._app_release_url(version)
        release_link = (
            f'<a style="color:{accent}; text-decoration:none;" href="{release_url}">{version}</a>'
        )
        if self.latest_available_version and self.latest_available_version != version:
            latest = self.latest_available_version
            latest_release_url = self._app_release_url(latest)
            latest_link = (
                f'<a style="color:{accent}; text-decoration:none;" '
                f'href="{latest_release_url}">{latest}</a>'
            )
            app_version_part = f"{release_link} → {latest_link}"
        else:
            app_version_part = release_link

        slug = self._zapret_repo_slug()
        repo_url = self._zapret_repo_url()
        zapret_repo_link = (
            f'<a style="color:{accent}; text-decoration:none;" href="{repo_url}">{slug}</a>'
        )

        self.footer_label.setText(
            f'<span style="color:{muted};">'
            f'{app_repo_link} · {app_version_part} · {zapret_repo_link}'
            f'</span>'
        )
        if hasattr(self, "network_status_label") and hasattr(self, "_apply_network_status_ui"):
            self._apply_network_status_ui()
        self.footer_label.setToolTip(f"{app_repo_url}\n{repo_url}")

        if hasattr(self, "fork_icon_label") and isinstance(self.fork_icon_label, QLabel):
            self.fork_icon_label.setPixmap(self._fork_icon_pixmap(14))
            self.fork_icon_label.setToolTip(tr("home_fork_tooltip", lang).format(app_repo))
            self.fork_icon_label.show()

        if hasattr(self, "_update_launch_args_status"):
            self._update_launch_args_status()

    def _update_launch_args_status(self) -> None:
        """Показывает активные CLI-параметры запуска в нижней строке."""
        if not hasattr(self, "launch_args_label"):
            return
        from src.app.launch_options import (
            format_launch_args,
            format_launch_status_tooltip,
            has_active_launch_flags,
        )

        lang = self.settings.get("language", "ru")
        if not has_active_launch_flags():
            self.launch_args_label.hide()
            return

        args = format_launch_args(prefer_short=True)
        p = theme.palette()
        self.launch_args_label.setText(tr("home_launch_args_status", lang).format(args=args))
        self.launch_args_label.setStyleSheet(
            f"color: {p.fg_muted}; font-size: 11px; padding: 0 4px;"
        )
        self.launch_args_label.setToolTip(format_launch_status_tooltip(lang))
        self.launch_args_label.show()

    def _show_version_context_menu(self, pos):
        """Контекстное меню по версии (открыть релиз / копировать ссылку)."""
        lang = self.settings.get("language", "ru")
        menu = StyleMenu(self)
        open_action = menu.addAction(tr("link_open_release", lang))
        copy_action = menu.addAction(tr("link_copy_release", lang))
        target = getattr(self, "footer_label", None) or getattr(self, "version_label", None)
        if target is None:
            return
        action = menu.exec(target.mapToGlobal(pos))
        if not action:
            return
        release_url = self._app_release_url(VERSION)
        if action == open_action:
            QDesktopServices.openUrl(QUrl(release_url))
        elif action == copy_action:
            QGuiApplication.clipboard().setText(release_url)

"""Индикатор состояния сети в футере главного окна."""
from __future__ import annotations

from PyQt6.QtCore import QThread, QTimer, pyqtSignal

from src.shared.ui.assets.codicon_utils import codicon_colored_pixmap
from src.entities.network.network_status import NetworkState, check_network_status, invalidate_network_cache
from src.shared.i18n.translator import tr
from src.shared.ui import theme

_POLL_STABLE_MS = 30_000
_POLL_OFFLINE_MS = 8_000
_POLL_AFTER_LOSS_MS = 5_000
_NETWORK_ICON_SIZE = 16


class _NetworkCheckWorker(QThread):
    finished = pyqtSignal(object)

    def run(self):
        try:
            status = check_network_status(force=True)
        except Exception:
            from src.entities.network.network_status import NetworkStatus

            status = NetworkStatus(
                state=NetworkState.UNKNOWN,
                ping_ok=False,
                http_ok=False,
            )
        self.finished.emit(status)


def _network_state_rank(state: NetworkState) -> int:
    order = {
        NetworkState.UNKNOWN: 0,
        NetworkState.OFFLINE: 1,
        NetworkState.PING_ONLY: 2,
        NetworkState.ONLINE: 3,
    }
    return order.get(state, 0)


class NetworkMixin:
    def _init_network_status_monitor(self) -> None:
        self._network_worker: _NetworkCheckWorker | None = None
        self._network_status = None
        self._network_pulse_timer: QTimer | None = None
        self._network_pulse_on = False
        timer = QTimer(self)
        timer.timeout.connect(self._refresh_network_status)
        timer.start(_POLL_STABLE_MS)
        self._network_status_timer = timer
        QTimer.singleShot(1500, self._refresh_network_status)

    def _network_status_colors(self, state: NetworkState, *, pulse: bool = False) -> str:
        p = theme.palette()
        if state == NetworkState.ONLINE:
            return "#098658" if theme.is_light() else "#4EC9B0"
        if state == NetworkState.PING_ONLY:
            return "#8b6914" if theme.is_light() else "#DCDCAA"
        if state == NetworkState.OFFLINE:
            if pulse:
                return "#ff1a1a" if theme.is_light() else "#ff8585"
            return "#c42b2b" if theme.is_light() else "#f44747"
        return p.fg_muted

    def _network_icon_name(self, status) -> str:
        if status is None or status.state in (NetworkState.UNKNOWN, NetworkState.OFFLINE):
            return "globe"
        link = getattr(status, "link_type", "unknown") or "unknown"
        if link == "wifi":
            return "broadcast"
        if link == "ethernet":
            return "plug"
        return "globe"

    def _network_status_tooltip(self, lang: str) -> str:
        status = getattr(self, "_network_status", None)
        if status is None:
            return tr("home_network_checking", lang)
        parts = []
        if status.state == NetworkState.ONLINE:
            parts.append(tr("home_network_online", lang))
        elif status.state == NetworkState.PING_ONLY:
            parts.append(tr("home_network_ping_only", lang))
        elif status.state == NetworkState.OFFLINE:
            parts.append(tr("home_network_offline", lang))
        else:
            parts.append(tr("home_network_checking", lang))

        link = getattr(status, "link_type", "unknown") or "unknown"
        if link == "wifi":
            parts.append(tr("home_network_link_wifi", lang))
        elif link == "ethernet":
            parts.append(tr("home_network_link_ethernet", lang))

        parts.append(f"ping 1.1.1.1: {'OK' if status.ping_ok else '—'}")
        parts.append(f"HTTP: {'OK' if status.http_ok else '—'}")
        return " · ".join(parts)

    def _apply_network_status_ui(self) -> None:
        lang = self.settings.get("language", "ru")
        label = getattr(self, "network_status_label", None)
        if label is None:
            return

        status = getattr(self, "_network_status", None)
        pulse = bool(getattr(self, "_network_pulse_on", False))
        if status is None:
            state = NetworkState.UNKNOWN
        else:
            state = status.state

        color = self._network_status_colors(state, pulse=pulse)
        icon_name = self._network_icon_name(status)
        label.setPixmap(codicon_colored_pixmap(icon_name, _NETWORK_ICON_SIZE, color))
        label.setToolTip(self._network_status_tooltip(lang))

    def _schedule_network_poll_interval(self, status) -> None:
        timer = getattr(self, "_network_status_timer", None)
        if timer is None:
            return
        if status.state == NetworkState.OFFLINE:
            timer.setInterval(_POLL_OFFLINE_MS)
        else:
            timer.setInterval(_POLL_STABLE_MS)

    def _stop_network_offline_pulse(self) -> None:
        t = getattr(self, "_network_pulse_timer", None)
        if t is not None:
            t.stop()
        self._network_pulse_on = False

    def _start_network_offline_pulse(self) -> None:
        self._stop_network_offline_pulse()
        self._network_pulse_ticks = 0
        timer = QTimer(self)
        timer.timeout.connect(self._on_network_offline_pulse)
        timer.start(450)
        self._network_pulse_timer = timer

    def _on_network_offline_pulse(self) -> None:
        self._network_pulse_ticks = getattr(self, "_network_pulse_ticks", 0) + 1
        self._network_pulse_on = not getattr(self, "_network_pulse_on", False)
        self._apply_network_status_ui()
        if self._network_pulse_ticks >= 8:
            self._stop_network_offline_pulse()
            self._apply_network_status_ui()

    def _refresh_network_status(self) -> None:
        if self._network_worker is not None and self._network_worker.isRunning():
            return
        self._network_worker = _NetworkCheckWorker(self)
        self._network_worker.finished.connect(self._on_network_status_ready)
        self._network_worker.finished.connect(self._network_worker.deleteLater)
        self._network_worker.start()

    def _on_network_status_ready(self, status) -> None:
        prev = getattr(self, "_network_status", None)
        prev_state = prev.state if prev is not None else None
        self._network_worker = None
        self._network_status = status

        degraded = (
            prev_state is not None
            and _network_state_rank(status.state) < _network_state_rank(prev_state)
        )
        became_offline = (
            status.state == NetworkState.OFFLINE
            and prev_state != NetworkState.OFFLINE
        )

        if became_offline or degraded:
            invalidate_network_cache()
            self._start_network_offline_pulse()
            timer = getattr(self, "_network_status_timer", None)
            if timer is not None:
                timer.setInterval(_POLL_AFTER_LOSS_MS)
                QTimer.singleShot(_POLL_AFTER_LOSS_MS, self._refresh_network_status)
        elif status.state != NetworkState.OFFLINE:
            self._stop_network_offline_pulse()

        self._schedule_network_poll_interval(status)
        self._apply_network_status_ui()

        if hasattr(self, "load_footer_info") and prev_state is None:
            self.load_footer_info()

    def refresh_network_status_now(self) -> None:
        invalidate_network_cache()
        self._refresh_network_status()

    def _on_window_shown_refresh_network(self) -> None:
        if hasattr(self, "refresh_network_status_now"):
            self.refresh_network_status_now()

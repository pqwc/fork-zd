from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import Qt

from src.shared.i18n.translator import tr
from src.shared.ui import theme


def _detect_language(parent: QWidget | None) -> str:
    """Определяет язык из настроек родительского окна (если есть)."""
    lang = "ru"
    if parent is None:
        return lang
    try:
        if hasattr(parent, "settings"):
            lang = getattr(parent, "settings", {}).get("language", "ru")
        elif hasattr(parent, "config"):
            try:
                settings = parent.config.load_settings()  # type: ignore[call-arg, attr-defined]
                lang = settings.get("language", "ru")
            except Exception:
                pass
    except Exception:
        pass
    return lang


def configure_message_box(msg: QMessageBox) -> QMessageBox:
    """
    Настраивает QMessageBox: флаги окна задаются до нативных стилей,
    чтобы не создавать второй HWND на Windows.
    """
    from src.shared.ui.window_styles import message_box_window_flags, schedule_native_style

    msg.setWindowFlags(message_box_window_flags())
    msg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    schedule_native_style(
        msg,
        caption_buttons=True,
        minimize=False,
        maximize=False,
        close=True,
        force=True,
    )

    # Применяем цвета из палитры темы (как StyleMenu / диалоги)
    try:
        p = theme.palette()
        msg.setStyleSheet(
            f"""
            QMessageBox {{
                background-color: {p.bg_panel};
                color: {p.fg_text};
            }}
            QMessageBox QLabel {{
                color: {p.fg_text};
            }}
            QMessageBox QPushButton {{
                background-color: {p.bg_item};
                color: {p.fg_text};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 4px 10px;
            }}
            QMessageBox QPushButton:hover {{
                background-color: {p.accent};
                border-color: {p.accent};
            }}
            QMessageBox QPushButton:pressed {{
                background-color: {p.accent_hover};
                border-color: {p.accent_hover};
                color: #ffffff;
            }}
            """
        )
    except Exception:
        # Если тема по какой-то причине недоступна — просто пропускаем
        pass
    return msg


def _apply_translated_button_texts(box: QMessageBox, lang: str) -> None:
    """Заменяет текст стандартных кнопок на переводы из translator.py."""
    try:
        # Ok / Cancel
        btn = box.button(QMessageBox.StandardButton.Ok)
        if btn is not None:
            btn.setText(tr("settings_ok", lang))
        btn = box.button(QMessageBox.StandardButton.Cancel)
        if btn is not None:
            btn.setText(tr("settings_cancel", lang))
        # Close — используем тот же перевод, что и Cancel (либо можно добавить отдельный ключ)
        btn = box.button(QMessageBox.StandardButton.Close)
        if btn is not None:
            btn.setText(tr("settings_cancel", lang))
    except Exception:
        # Если что-то пошло не так с переводом кнопок — оставляем стандартные подписи
        return


def create_message_box(
    parent: QWidget | None = None,
    icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    title_key: str | None = None,
    text: str | None = None,
    informative_text: str | None = None,
    detailed_text: str | None = None,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton | None = None,
    lang: str | None = None,
) -> QMessageBox:
    """
    Создаёт настроенный QMessageBox для ZapretDesktop:
    - применяет стиль заголовка через window_styles.apply_window_style
    - настраивает флаги окна (только кнопка закрытия)
    - задаёт переводы для стандартных кнопок (Ok/Cancel/Close)
    - может использовать ключ перевода для заголовка (title_key)
    """
    box = QMessageBox(parent)

    # Определяем язык
    lang = lang or _detect_language(parent)
    # Полная настройка окна (заголовок, кнопки окна, цвета)
    configure_message_box(box)
    box.setIcon(icon)

    if title_key:
        try:
            box.setWindowTitle(tr(title_key, lang))
        except Exception:
            box.setWindowTitle(title_key)

    if text is not None:
        box.setText(text)
    if informative_text:
        box.setInformativeText(informative_text)
    if detailed_text:
        box.setDetailedText(detailed_text)

    box.setStandardButtons(buttons)
    if default_button is not None:
        box.setDefaultButton(default_button)

    return box


def exec_message_box(
    parent: QWidget | None = None,
    icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    title_key: str | None = None,
    text: str | None = None,
    informative_text: str | None = None,
    detailed_text: str | None = None,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    default_button: QMessageBox.StandardButton | None = None,
    lang: str | None = None,
) -> QMessageBox.StandardButton:
    """
    Удобный helper: создает и показывает QMessageBox, возвращая нажатую кнопку.

    Пример:
        result = exec_message_box(
            parent=self,
            icon=QMessageBox.Icon.Warning,
            title_key='msg_error',
            text='...',
            buttons=QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            default_button=QMessageBox.StandardButton.Ok,
        )
    """
    box = create_message_box(
        parent=parent,
        icon=icon,
        title_key=title_key,
        text=text,
        informative_text=informative_text,
        detailed_text=detailed_text,
        buttons=buttons,
        default_button=default_button,
        lang=lang,
    )
    # После установки кнопок — применяем переводы
    _apply_translated_button_texts(box, lang or _detect_language(parent))
    clicked = box.exec()
    return QMessageBox.StandardButton(clicked)


"""Общие диалоги редактора."""
from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from src.shared.i18n.translator import tr


def prompt_unsaved_file_action(parent, lang: str, *, filename: str = "") -> str:
    """
    Спрашивает, что делать с несохранёнными изменениями.

    Returns:
        ``save`` | ``discard`` | ``cancel``
    """
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setWindowTitle(tr("editor_unsaved_title", lang))
    if filename:
        msg.setText(tr("editor_unsaved_switch_file", lang).format(filename))
    else:
        msg.setText(tr("editor_unsaved_switch", lang))

    save_btn = msg.addButton(tr("editor_save", lang), QMessageBox.ButtonRole.AcceptRole)
    discard_btn = msg.addButton(tr("editor_discard", lang), QMessageBox.ButtonRole.DestructiveRole)
    cancel_btn = msg.addButton(tr("settings_cancel", lang), QMessageBox.ButtonRole.RejectRole)
    msg.setDefaultButton(cancel_btn)

    msg.exec()
    clicked = msg.clickedButton()
    if clicked is save_btn:
        return "save"
    if clicked is discard_btn:
        return "discard"
    return "cancel"

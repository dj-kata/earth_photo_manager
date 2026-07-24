from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QColorDialog,
)

from src.tag_store import Tag, TagStore


DIALOG_TRANSLATIONS = {
    "en": {
        "title": "Tag Manager",
        "categories": "Categories",
        "tags": "Tags",
        "name": "Name",
        "add": "Add",
        "update": "Update",
        "delete": "Delete",
        "choose_color": "Choose Color",
        "color": "Color",
        "category": "Category",
        "related_tags": "Related Tags",
        "none": "(None)",
        "delete_category_confirm": "Delete this category?",
        "delete_tag_confirm": "Delete this tag?",
        "confirm": "Confirm",
        "choose_tag_color": "Choose tag color",
    },
    "ja": {
        "title": "タグ管理",
        "categories": "カテゴリー",
        "tags": "タグ",
        "name": "名前",
        "add": "追加",
        "update": "更新",
        "delete": "削除",
        "choose_color": "色を選択",
        "color": "色",
        "category": "カテゴリー",
        "related_tags": "関連タグ",
        "none": "(なし)",
        "delete_category_confirm": "このカテゴリーを削除しますか?",
        "delete_tag_confirm": "このタグを削除しますか?",
        "confirm": "確認",
        "choose_tag_color": "タグの色を選択",
    },
}


class TagManagerDialog(QDialog):
    def __init__(
        self,
        tag_store: TagStore,
        language: str = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language if language in DIALOG_TRANSLATIONS else "en"
        self.setWindowTitle(self._tr("title"))
        self.resize(720, 560)
        self.tag_store = tag_store
        self.current_color = "#3b82f6"

        tabs = QTabWidget()
        tabs.addTab(self._build_categories_tab(), self._tr("categories"))
        tabs.addTab(self._build_tags_tab(), self._tr("tags"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self._reload_categories()
        self._reload_tags()

    def _build_categories_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        self.category_list = QListWidget()
        self.category_list.currentItemChanged.connect(self._on_category_selected)

        form_panel = QWidget()
        form = QFormLayout(form_panel)
        self.category_name_edit = QLineEdit()
        form.addRow(self._tr("name"), self.category_name_edit)

        button_row = QHBoxLayout()
        add_button = QPushButton(self._tr("add"))
        add_button.clicked.connect(self._add_category)
        update_button = QPushButton(self._tr("update"))
        update_button.clicked.connect(self._update_category)
        delete_button = QPushButton(self._tr("delete"))
        delete_button.clicked.connect(self._delete_category)
        button_row.addWidget(add_button)
        button_row.addWidget(update_button)
        button_row.addWidget(delete_button)
        form.addRow(button_row)

        layout.addWidget(self.category_list, 2)
        layout.addWidget(form_panel, 3)
        return page

    def _build_tags_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)

        self.tag_list = QListWidget()
        self.tag_list.currentItemChanged.connect(self._on_tag_selected)

        form_host = QWidget()
        form_layout = QVBoxLayout(form_host)
        form = QFormLayout()
        self.tag_name_edit = QLineEdit()
        form.addRow(self._tr("name"), self.tag_name_edit)

        color_row = QHBoxLayout()
        self.color_sample = QLabel()
        self.color_sample.setFixedSize(36, 22)
        color_button = QPushButton(self._tr("choose_color"))
        color_button.clicked.connect(self._choose_color)
        color_row.addWidget(self.color_sample)
        color_row.addWidget(color_button)
        color_row.addStretch(1)
        form.addRow(self._tr("color"), color_row)

        self.tag_category_combo = QComboBox()
        form.addRow(self._tr("category"), self.tag_category_combo)
        form_layout.addLayout(form)

        form_layout.addWidget(QLabel(self._tr("related_tags")))
        self.relation_area = QScrollArea()
        self.relation_area.setWidgetResizable(True)
        self.relation_panel = QWidget()
        self.relation_form = QFormLayout(self.relation_panel)
        self.relation_area.setWidget(self.relation_panel)
        form_layout.addWidget(self.relation_area, 1)

        button_row = QHBoxLayout()
        add_button = QPushButton(self._tr("add"))
        add_button.clicked.connect(self._add_tag)
        update_button = QPushButton(self._tr("update"))
        update_button.clicked.connect(self._update_tag)
        delete_button = QPushButton(self._tr("delete"))
        delete_button.clicked.connect(self._delete_tag)
        button_row.addWidget(add_button)
        button_row.addWidget(update_button)
        button_row.addWidget(delete_button)
        form_layout.addLayout(button_row)

        layout.addWidget(self.tag_list, 2)
        layout.addWidget(form_host, 3)
        self._apply_color_sample()
        return page

    def _reload_categories(self, selected_id: str | None = None) -> None:
        current_tag_id = self._current_tag_id()
        self.category_list.clear()
        self.tag_category_combo.clear()
        self.tag_category_combo.addItem(self._tr("none"), None)
        for category in self.tag_store.categories:
            item = QListWidgetItem(category.name)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            self.category_list.addItem(item)
            self.tag_category_combo.addItem(category.name, category.id)
            if category.id == selected_id:
                self.category_list.setCurrentItem(item)

        self._rebuild_relation_combos()
        self._restore_tag_selection(current_tag_id)

    def _reload_tags(self, selected_id: str | None = None) -> None:
        selected_item: QListWidgetItem | None = None
        self.tag_list.blockSignals(True)
        self.tag_list.clear()
        try:
            for tag in self.tag_store.tags:
                item = QListWidgetItem(self._tag_label(tag))
                item.setData(Qt.ItemDataRole.UserRole, tag.id)
                background = QColor(tag.color)
                if not background.isValid():
                    background = QColor("#3b82f6")
                item.setBackground(background)
                item.setForeground(QBrush(_readable_text_color(background)))
                self.tag_list.addItem(item)
                if tag.id == selected_id:
                    selected_item = item
        finally:
            self.tag_list.blockSignals(False)
        self._rebuild_relation_combos()
        if selected_item is not None:
            self.tag_list.setCurrentItem(selected_item)
        else:
            self._on_tag_selected(None, None)

    def _restore_tag_selection(self, selected_id: str | None) -> None:
        if selected_id is None:
            self._on_tag_selected(self.tag_list.currentItem(), None)
            return
        for index in range(self.tag_list.count()):
            item = self.tag_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == selected_id:
                self.tag_list.setCurrentItem(item)
                self._on_tag_selected(item, None)
                return
        self._on_tag_selected(None, None)

    def _rebuild_relation_combos(self) -> None:
        while self.relation_form.rowCount():
            self.relation_form.removeRow(0)
        self.relation_combos: dict[str, QComboBox] = {}
        for category in self.tag_store.categories:
            combo = QComboBox()
            combo.addItem(self._tr("none"), None)
            for tag in self.tag_store.tags_for_category(category.id):
                combo.addItem(tag.name, tag.id)
            self.relation_combos[category.id] = combo
            self.relation_form.addRow(category.name, combo)

    def _on_category_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.category_name_edit.clear()
            return
        category = self.tag_store.category_by_id(current.data(Qt.ItemDataRole.UserRole))
        self.category_name_edit.setText(category.name if category else "")

    def _on_tag_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.tag_name_edit.clear()
            self.current_color = "#3b82f6"
            self._apply_color_sample()
            self._select_combo_data(self.tag_category_combo, None)
            for combo in self.relation_combos.values():
                self._select_combo_data(combo, None)
            return

        tag = self.tag_store.tag_by_id(current.data(Qt.ItemDataRole.UserRole))
        if tag is None:
            return
        self.tag_name_edit.setText(tag.name)
        self.current_color = tag.color
        self._apply_color_sample()
        self._select_combo_data(self.tag_category_combo, tag.category_id)
        for category_id, combo in self.relation_combos.items():
            self._select_combo_data(combo, tag.related_tag_ids_by_category.get(category_id))

    def _add_category(self) -> None:
        name = self.category_name_edit.text().strip()
        if not name:
            return
        category = self.tag_store.create_category(name)
        self._reload_categories(category.id)

    def _update_category(self) -> None:
        category_id = self._current_category_id()
        name = self.category_name_edit.text().strip()
        if category_id is None or not name:
            return
        self.tag_store.update_category(category_id, name)
        self._reload_categories(category_id)
        self._reload_tags(self._current_tag_id())

    def _delete_category(self) -> None:
        category_id = self._current_category_id()
        if category_id is None:
            return
        if self._confirm_delete(self._tr("delete_category_confirm")):
            self.tag_store.delete_category(category_id)
            self._reload_categories()
            self._reload_tags()

    def _add_tag(self) -> None:
        values = self._tag_form_values()
        if values is None:
            return
        tag = self.tag_store.create_tag(*values)
        self._reload_tags(tag.id)

    def _update_tag(self) -> None:
        tag_id = self._current_tag_id()
        values = self._tag_form_values()
        if tag_id is None or values is None:
            return
        self.tag_store.update_tag(tag_id, *values)
        self._reload_tags(tag_id)

    def _delete_tag(self) -> None:
        tag_id = self._current_tag_id()
        if tag_id is None:
            return
        if self._confirm_delete(self._tr("delete_tag_confirm")):
            self.tag_store.delete_tag(tag_id)
            self._reload_tags()

    def _tag_form_values(
        self,
    ) -> tuple[str, str, str | None, dict[str, str]] | None:
        name = self.tag_name_edit.text().strip()
        if not name:
            return None
        category_id = self.tag_category_combo.currentData()
        related: dict[str, str] = {}
        for relation_category_id, combo in self.relation_combos.items():
            tag_id = combo.currentData()
            if tag_id:
                related[str(relation_category_id)] = str(tag_id)
        return name, self.current_color, category_id, related

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self.current_color),
            self,
            self._tr("choose_tag_color"),
        )
        if color.isValid():
            self.current_color = color.name()
            self._apply_color_sample()

    def _apply_color_sample(self) -> None:
        self.color_sample.setStyleSheet(
            f"background: {self.current_color}; border: 1px solid #667085;"
        )

    def _current_category_id(self) -> str | None:
        item = self.category_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _current_tag_id(self) -> str | None:
        item = self.tag_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _confirm_delete(self, text: str) -> bool:
        return (
            QMessageBox.question(
                self,
                self._tr("confirm"),
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _tr(self, key: str) -> str:
        return DIALOG_TRANSLATIONS[self.language].get(
            key, DIALOG_TRANSLATIONS["en"].get(key, key)
        )

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: str | None) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _tag_label(self, tag: Tag) -> str:
        category = self.tag_store.category_by_id(tag.category_id)
        if category is None:
            return tag.name
        return f"{category.name}: {tag.name}"


def _readable_text_color(color: QColor) -> QColor:
    luminance = (
        0.299 * color.red()
        + 0.587 * color.green()
        + 0.114 * color.blue()
    )
    return QColor("#111827") if luminance >= 150 else QColor("#ffffff")

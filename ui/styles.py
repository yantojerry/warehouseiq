# Owns shared PyQt styling helpers.

"""MIHS design system theme and PyQt styling helpers."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
)

from ui.theme import COLORS, FONT_FALLBACK, FONT_MONO, FONT_UI, MONO_FALLBACK, STATUS_TONES
from backend.auth.roles import canonical_role, display_role


APP_THEME = f"""
QWidget {{
    background-color: {COLORS["background"]};
    color: {COLORS["white"]};
    font-family: "{FONT_UI}", "{FONT_FALLBACK}", Arial, sans-serif;
    font-size: 13px;
}}

QFrame {{
    background: transparent;
}}

QLabel {{
    background: transparent;
    color: {COLORS["white"]};
}}

QCheckBox {{
    background: transparent;
    color: {COLORS["white"]};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border-radius: 3px;
    border: 1px solid {COLORS["border_2"]};
    background-color: {COLORS["white"]};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["teal"]};
    border-color: {COLORS["teal"]};
}}

QRadioButton {{
    color: {COLORS["white"]};
    background: transparent;
    spacing: 6px;
}}

QMainWindow, #content_area, #page_content {{
    background-color: {COLORS["background"]};
}}

QDialog, QDialog QWidget {{
    background-color: {COLORS["white"]};
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
    border: none;
}}

#sidebar {{
    background-color: {COLORS["navy"]};
    border-right: 1px solid {COLORS["navy_2"]};
}}

#sidebar_super_admin {{
    background-color: {COLORS["super_sidebar"]};
    border-right: 1px solid {COLORS["super_sidebar_3"]};
}}

#sidebar_brand {{
    background-color: {COLORS["navy"]};
}}

#sidebar_brand_super_admin {{
    background-color: {COLORS["super_sidebar"]};
}}

#brand_logo, #login_logo {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
    border-radius: 8px;
    font-size: 14px;
    font-weight: 800;
}}

#brand_logo_super_admin {{
    background-color: {COLORS["super_accent"]};
    color: {COLORS["super_sidebar"]};
    border-radius: 8px;
    font-size: 14px;
    font-weight: 900;
}}

#brand_label, #profile_name {{
    color: {COLORS["white"]};
    background: transparent;
    font-weight: 700;
}}

#brand_accent {{
    color: {COLORS["teal_light"]};
    background: transparent;
    font-weight: 800;
}}

#brand_accent_super_admin {{
    color: {COLORS["super_accent"]};
    background: transparent;
    font-weight: 900;
}}

#sidebar_divider, #line_divider {{
    background-color: {COLORS["border"]};
    border: none;
    max-height: 1px;
}}

#sidebar_profile {{
    background-color: {COLORS["navy"]};
    border-top: 1px solid {COLORS["navy_2"]};
}}

#sidebar_profile_super_admin {{
    background-color: {COLORS["super_sidebar_2"]};
}}

#user_avatar {{
    background-color: {COLORS["navy_3"]};
    color: {COLORS["white"]};
    border: 2px solid {COLORS["teal_light"]};
    border-radius: 20px;
    font-weight: 700;
}}

#user_avatar_super_admin {{
    background-color: {COLORS["super_sidebar_3"]};
    color: {COLORS["super_accent_pale"]};
    border: 2px solid {COLORS["super_accent"]};
    border-radius: 20px;
    font-weight: 800;
}}

#nav_section_label {{
    color: {COLORS["muted"]};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    background: transparent;
}}

QToolButton#nav_button, QToolButton#nav_button_active {{
    border: none;
    border-radius: 8px;
    min-height: 38px;
    padding: 0 12px;
    text-align: left;
}}

QToolButton#nav_button {{
    background-color: transparent;
    color: {COLORS["muted"]};
}}

QToolButton#nav_button:hover {{
    background-color: {COLORS["navy_2"]};
    color: {COLORS["white"]};
}}

QToolButton#nav_button_active {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
}}

QToolButton#nav_parent_super, QToolButton#nav_parent_super_expanded,
QToolButton#nav_parent_super_active, QToolButton#nav_button_super,
QToolButton#nav_button_super_active {{
    border: none;
    border-radius: 8px;
    min-height: 38px;
    padding: 0 12px;
    text-align: left;
}}

QToolButton#nav_parent_super, QToolButton#nav_button_super {{
    background-color: transparent;
    color: {COLORS["muted"]};
}}

QToolButton#nav_parent_super:hover, QToolButton#nav_button_super:hover {{
    background-color: {COLORS["super_sidebar_2"]};
    color: {COLORS["white"]};
}}

QToolButton#nav_parent_super_expanded {{
    background-color: {COLORS["super_sidebar_2"]};
    color: {COLORS["super_accent_pale"]};
}}

QToolButton#nav_parent_super_active, QToolButton#nav_button_super_active {{
    background-color: {COLORS["super_accent"]};
    color: {COLORS["super_sidebar"]};
}}

#sidebar_nav_group {{
    background: transparent;
}}

QPushButton#sidebar_logout {{
    background-color: transparent;
    color: {COLORS["muted"]};
    border: none;
    border-radius: 0;
    font-weight: 700;
    text-align: left;
    padding-left: 20px;
}}

QPushButton#sidebar_logout:hover {{
    background-color: {COLORS["red_pale"]};
    color: {COLORS["red"]};
}}

#page_title {{
    color: {COLORS["white"]};
    background: transparent;
    font-size: 18px;
    font-weight: 800;
}}

#page_subtitle, #page_subtitle QLabel {{
    color: {COLORS["muted"]};
    background: transparent;
    font-size: 12px;
}}

#live_dot {{
    color: {COLORS["teal_light"]};
    background: transparent;
    font-weight: 700;
}}

#section_label {{
    color: {COLORS["text_3"]};
    background: transparent;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
}}

#card, #card_header, #card_body, #login_card, #stat_card,
#stat_card_navy, #stat_card_teal, #stat_card_amber,
#stat_card_red, #stat_card_green, #stat_card_blue {{
    background-color: {COLORS["white"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
}}

#card QLabel, #card_header QLabel, #card_body QLabel,
#login_card QLabel, #stat_card QLabel,
#stat_card_navy QLabel, #stat_card_teal QLabel,
#stat_card_amber QLabel, #stat_card_red QLabel,
#stat_card_green QLabel, #stat_card_blue QLabel {{
    color: {COLORS["text"]};
    background: transparent;
}}

#card QCheckBox, #card_body QCheckBox {{
    color: {COLORS["text"]};
    background: transparent;
}}

#login_card {{
    border-radius: 20px;
}}

#card_header {{
    background-color: {COLORS["white"]};
    border-bottom: 1px solid {COLORS["border"]};
}}

#card_title {{
    color: {COLORS["text"]};
    background: transparent;
    font-size: 13px;
    font-weight: 800;
}}

#card_body {{
    background-color: {COLORS["white"]};
    padding: 10px 14px;
}}

#stat_card_navy {{ border-left: 3px solid {COLORS["navy"]}; border-top: 1px solid {COLORS["border"]}; }}
#stat_card_teal {{ border-left: 3px solid {COLORS["teal"]}; border-top: 1px solid {COLORS["border"]}; }}
#stat_card_amber {{ border-left: 3px solid {COLORS["amber"]}; border-top: 1px solid {COLORS["border"]}; }}
#stat_card_red {{ border-left: 3px solid {COLORS["red"]}; border-top: 1px solid {COLORS["border"]}; }}
#stat_card_green {{ border-left: 3px solid {COLORS["green"]}; border-top: 1px solid {COLORS["border"]}; }}
#stat_card_blue {{ border-left: 3px solid {COLORS["blue"]}; border-top: 1px solid {COLORS["border"]}; }}

#stat_value {{
    color: {COLORS["text"]};
    background: transparent;
    font-family: "{FONT_MONO}", "{MONO_FALLBACK}", monospace;
    font-size: 24px;
    font-weight: 800;
}}

#stat_label {{
    color: {COLORS["text_3"]};
    background: transparent;
    font-size: 11.5px;
    font-weight: 700;
}}

#alert_red, #alert_error {{
    background-color: {COLORS["red_pale"]};
    border: 1px solid {COLORS["red"]};
    border-radius: 10px;
}}

#alert_navy, #alert_info {{
    background-color: {COLORS["navy_pale"]};
    border: 1px solid {COLORS["navy"]};
    border-radius: 10px;
}}

#alert_amber, #alert_warning {{
    background-color: {COLORS["amber_pale"]};
    border: 1px solid {COLORS["amber"]};
    border-radius: 10px;
}}

#alert_teal, #alert_success {{
    background-color: {COLORS["teal_pale"]};
    border: 1px solid {COLORS["teal"]};
    border-radius: 10px;
}}

#alert_text_red, #alert_text_error {{ color: {COLORS["red"]}; background: transparent; font-weight: 700; }}
#alert_text_navy, #alert_text_info {{ color: {COLORS["navy"]}; background: transparent; font-weight: 700; }}
#alert_text_amber, #alert_text_warning {{ color: {COLORS["amber"]}; background: transparent; font-weight: 700; }}
#alert_text_teal, #alert_text_success {{ color: {COLORS["teal"]}; background: transparent; font-weight: 700; }}

QPushButton {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
    border: none;
    border-radius: 6px;
    padding: 0 10px;
    min-height: 32px;
    font-size: 12px;
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: {COLORS["teal_light"]};
}}

QPushButton:disabled {{
    background-color: {COLORS["surface_2"]};
    color: {COLORS["muted"]};
    border: 1px solid {COLORS["border"]};
}}

QPushButton#btn_primary, QPushButton#btn_teal, QPushButton#btn_success {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
    border: none;
}}

QPushButton#btn_navy {{
    background-color: {COLORS["navy"]};
    color: {COLORS["white"]};
    border: none;
}}

QPushButton#btn_outline, QPushButton#btn_ghost {{
    background-color: transparent;
    color: {COLORS["text_2"]};
    border: 1px solid {COLORS["border_2"]};
}}

QPushButton#btn_outline:hover, QPushButton#btn_ghost:hover {{
    background-color: {COLORS["surface"]};
}}

QPushButton#btn_danger {{
    background-color: transparent;
    color: {COLORS["red"]};
    border: 1px solid {COLORS["red"]};
}}

QPushButton#btn_danger:hover {{
    background-color: {COLORS["red_pale"]};
}}

QPushButton#btn_danger:disabled {{
    background-color: transparent;
    color: {COLORS["muted"]};
    border: 1px solid {COLORS["border"]};
}}

QPushButton#btn_warning {{
    background-color: transparent;
    color: {COLORS["amber"]};
    border: 1px solid {COLORS["amber"]};
}}

QPushButton#btn_link {{
    background-color: transparent;
    color: {COLORS["teal"]};
    border: none;
    padding: 0;
    min-height: 0;
}}

QPushButton#filter_button, QPushButton#pill_button, QPushButton#payment_option {{
    background-color: {COLORS["white"]};
    color: {COLORS["text_2"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
}}

QPushButton#filter_button_active, QPushButton#pill_button_selected, QPushButton#payment_option_selected {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
    border: 1px solid {COLORS["teal"]};
    border-radius: 8px;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border_2"]};
    border-radius: 6px;
    padding: 8px 11px;
    min-height: 34px;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {COLORS["teal"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
    selection-background-color: {COLORS["teal_pale"]};
    selection-color: {COLORS["teal"]};
    border: 1px solid {COLORS["border_2"]};
}}

QLabel#form_label {{
    color: {COLORS["navy"]};
    background: transparent;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

QTableWidget {{
    background-color: {COLORS["white"]};
    alternate-background-color: {COLORS["white"]};
    color: {COLORS["text_2"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    gridline-color: {COLORS["border"]};
    selection-background-color: {COLORS["teal_pale"]};
    selection-color: {COLORS["text"]};
}}

QTableWidget::item {{
    padding: 10px 13px;
    border-bottom: 1px solid {COLORS["border"]};
}}

QTableWidget::item:hover {{
    background-color: {COLORS["surface"]};
}}

QHeaderView::section {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_3"]};
    font-size: 11px;
    font-weight: 800;
    padding: 9px 13px;
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
}}

QLabel#badge_navy {{ background-color: {COLORS["navy_pale"]}; color: {COLORS["navy"]}; }}
QLabel#badge_teal {{ background-color: {COLORS["teal_pale"]}; color: {COLORS["teal"]}; }}
QLabel#badge_amber {{ background-color: {COLORS["amber_pale"]}; color: {COLORS["amber"]}; }}
QLabel#badge_red {{ background-color: {COLORS["red_pale"]}; color: {COLORS["red"]}; }}
QLabel#badge_green {{ background-color: {COLORS["green_pale"]}; color: {COLORS["green"]}; }}
QLabel#badge_gray {{ background-color: {COLORS["surface_2"]}; color: {COLORS["text_3"]}; }}
QLabel#badge_blue {{ background-color: {COLORS["blue_pale"]}; color: {COLORS["blue"]}; }}
QLabel#badge_super_admin {{ background-color: {COLORS["super_accent_pale"]}; color: {COLORS["super_sidebar"]}; }}

QLabel#badge_navy, QLabel#badge_teal, QLabel#badge_amber, QLabel#badge_red,
QLabel#badge_green, QLabel#badge_gray, QLabel#badge_blue, QLabel#badge_super_admin {{
    border-radius: 10px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 700;
    max-width: 110px;
}}

#login_page {{
    background-color: {COLORS["background"]};
}}

#login_logo {{
    border-radius: 14px;
    font-size: 24px;
}}

#login_title {{
    color: {COLORS["navy"]};
    background: transparent;
    font-size: 22px;
    font-weight: 800;
}}

#dialog_accent {{
    background-color: {COLORS["navy"]};
    border-radius: 0px;
    min-height: 5px;
    max-height: 5px;
}}

#login_subtitle {{
    color: {COLORS["text_3"]};
    background: transparent;
}}

#password_row {{
    background-color: {COLORS["white"]};
    border: 1px solid {COLORS["border_2"]};
    border-radius: 6px;
}}

QLineEdit#password_inside {{
    border: none;
    background: transparent;
}}

QPushButton#password_toggle {{
    background: transparent;
    color: {COLORS["text_3"]};
    border: none;
    padding: 0 10px;
    font-size: 11px;
}}

#pos_panel_left, #pos_panel_mid, #pos_panel_right {{
    background-color: {COLORS["background"]};
}}

#pos_divider {{
    background-color: {COLORS["border"]};
    border: none;
    max-height: 1px;
}}

#pos_empty_label {{
    color: {COLORS["text_3"]};
    background: transparent;
    font-weight: 800;
}}

#pos_total_value, #pos_qty_label {{
    color: {COLORS["white"]};
    background: transparent;
    font-weight: 700;
}}

#pos_live_total, #pos_change_label {{
    color: {COLORS["teal_light"]};
    background: transparent;
    font-weight: 800;
}}

#pos_numpad {{
    background: transparent;
}}

QPushButton#pos_numpad_key, QPushButton#pos_numpad_action, QPushButton#pos_numpad_pay {{
    border-radius: 6px;
    min-height: 38px;
    padding: 0;
    font-size: 13px;
    font-weight: 800;
}}

QPushButton#pos_numpad_key {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border_2"]};
}}

QPushButton#pos_numpad_key:hover {{
    background-color: {COLORS["surface"]};
}}

QPushButton#pos_numpad_action {{
    background-color: transparent;
    color: {COLORS["teal_light"]};
    border: 1px solid {COLORS["teal"]};
}}

QPushButton#pos_numpad_action:hover {{
    background-color: {COLORS["navy_2"]};
}}

QPushButton#pos_numpad_pay {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
    border: 1px solid {COLORS["teal"]};
}}

#pos_cart_row, #product_card {{
    background-color: {COLORS["white"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
}}

#role_tasks_header {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
}}

#role_tasks_column_label {{
    color: {COLORS["text_3"]};
    background: transparent;
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: 0.4px;
}}

#role_task_row {{
    background-color: {COLORS["white"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
}}

#role_task_label {{
    color: {COLORS["text"]};
    background: transparent;
    font-size: 12.5px;
    font-weight: 800;
}}

#role_task_key, #role_task_meta {{
    color: {COLORS["text_3"]};
    background: transparent;
    font-size: 11px;
    font-weight: 700;
}}

#transparent_cell {{
    background: transparent;
}}

#sidebar_brand QWidget, #sidebar_brand_super_admin QWidget,
#sidebar_profile QWidget, #sidebar_profile_super_admin QWidget {{
    background: transparent;
}}

#product_card_selected {{
    background-color: {COLORS["teal_pale"]};
    border: 1px solid {COLORS["teal"]};
    border-radius: 10px;
}}

#floor_card_teal {{ background-color: {COLORS["teal_pale"]}; border: 1px solid {COLORS["teal"]}; border-radius: 10px; }}
#floor_card_amber {{ background-color: {COLORS["amber_pale"]}; border: 1px solid {COLORS["amber"]}; border-radius: 10px; }}
#floor_card_gray {{ background-color: {COLORS["surface_2"]}; border: 1px solid {COLORS["border"]}; border-radius: 10px; }}
#dispatch_header {{ background-color: {COLORS["navy"]}; border-top-left-radius: 14px; border-top-right-radius: 14px; }}
"""

DARK_MODE_OVERRIDES = f"""
QDialog, QDialog QWidget {{
    background-color: {COLORS["background"]};
    color: {COLORS["white"]};
}}

#card, #card_header, #card_body, #login_card, #stat_card,
#stat_card_navy, #stat_card_teal, #stat_card_amber,
#stat_card_red, #stat_card_green, #stat_card_blue,
#pos_cart_row, #product_card, #role_task_row, #role_tasks_header {{
    background-color: {COLORS["navy"]};
    border-color: {COLORS["navy_2"]};
}}

#card_header {{
    border-bottom-color: {COLORS["navy_2"]};
}}

#card QLabel, #card_header QLabel, #card_body QLabel,
#login_card QLabel, #stat_card QLabel,
#stat_card_navy QLabel, #stat_card_teal QLabel,
#stat_card_amber QLabel, #stat_card_red QLabel,
#stat_card_green QLabel, #stat_card_blue QLabel,
#product_card QLabel, #pos_cart_row QLabel,
#role_task_row QLabel, #role_tasks_header QLabel {{
    color: {COLORS["white"]};
    background: transparent;
}}

#card_title, #stat_value, #role_task_label {{
    color: {COLORS["white"]};
}}

#stat_label, #role_task_key, #role_task_meta,
#role_tasks_column_label, #form_label, QLabel#form_label {{
    color: {COLORS["muted"]};
}}

#page_subtitle, #page_subtitle QLabel, #login_subtitle {{
    color: {COLORS["muted"]};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit,
#password_row {{
    background-color: {COLORS["navy"]};
    color: {COLORS["white"]};
    border-color: {COLORS["navy_2"]};
}}

QLineEdit#password_inside {{
    background: transparent;
    color: {COLORS["white"]};
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["navy"]};
    color: {COLORS["white"]};
    selection-background-color: {COLORS["navy_2"]};
    selection-color: {COLORS["teal_light"]};
    border-color: {COLORS["navy_2"]};
}}

QTableWidget {{
    background-color: {COLORS["navy"]};
    alternate-background-color: {COLORS["navy"]};
    color: {COLORS["white"]};
    border-color: {COLORS["navy_2"]};
    gridline-color: {COLORS["navy_2"]};
    selection-background-color: {COLORS["navy_2"]};
    selection-color: {COLORS["white"]};
}}

QTableWidget::item {{
    border-bottom-color: {COLORS["navy_2"]};
}}

QTableWidget::item:hover,
QHeaderView::section {{
    background-color: {COLORS["navy_2"]};
    color: {COLORS["white"]};
    border-bottom-color: {COLORS["navy_3"]};
}}

QPushButton#btn_outline, QPushButton#btn_ghost,
QPushButton#filter_button, QPushButton#pill_button, QPushButton#payment_option,
QPushButton#pos_numpad_key {{
    background-color: {COLORS["navy"]};
    color: {COLORS["white"]};
    border-color: {COLORS["navy_2"]};
}}

QPushButton#btn_outline:hover, QPushButton#btn_ghost:hover,
QPushButton#filter_button:hover, QPushButton#pill_button:hover,
QPushButton#payment_option:hover, QPushButton#pos_numpad_key:hover {{
    background-color: {COLORS["navy_2"]};
}}

#floor_card_gray {{
    background-color: {COLORS["navy"]};
    border-color: {COLORS["navy_2"]};
}}

#floor_card_teal, #product_card_selected {{
    background-color: #063f35;
    border-color: {COLORS["teal_light"]};
}}

#floor_card_amber {{
    background-color: #4a320b;
    border-color: {COLORS["amber"]};
}}

#alert_red, #alert_error {{
    background-color: #3b1218;
    border-color: {COLORS["red"]};
}}

#alert_amber, #alert_warning {{
    background-color: #3d2a0b;
    border-color: {COLORS["amber"]};
}}

#alert_teal, #alert_success {{
    background-color: #063f35;
    border-color: {COLORS["teal_light"]};
}}

#alert_navy, #alert_info {{
    background-color: {COLORS["navy"]};
    border-color: {COLORS["navy_3"]};
}}

#alert_text_red, #alert_text_error {{ color: #fca5a5; }}
#alert_text_amber, #alert_text_warning {{ color: #fcd34d; }}
#alert_text_teal, #alert_text_success {{ color: #5eead4; }}
#alert_text_navy, #alert_text_info {{ color: {COLORS["white"]}; }}

QLabel#badge_gray {{
    background-color: {COLORS["navy_2"]};
    color: {COLORS["muted"]};
}}
"""

LIGHT_MODE_OVERRIDES = f"""
QDialog, QDialog QWidget {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
}}

#sidebar, #sidebar_brand, #sidebar_brand_super_admin,
#sidebar_profile, #sidebar_profile_super_admin {{
    background-color: {COLORS["white"]};
    border-color: {COLORS["border"]};
}}

#brand_label, #profile_name,
#brand_accent_super_admin {{
    color: {COLORS["text"]};
}}

#brand_accent {{
    color: {COLORS["teal"]};
}}

#user_avatar, #user_avatar_super_admin {{
    background-color: {COLORS["teal_pale"]};
    color: {COLORS["teal"]};
    border-color: {COLORS["teal"]};
}}

#brand_logo_super_admin {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
}}

QToolButton#nav_parent_super, QToolButton#nav_button_super,
QToolButton#nav_button {{
    background-color: transparent;
    color: {COLORS["text_2"]};
}}

QToolButton#nav_parent_super:hover, QToolButton#nav_button_super:hover,
QToolButton#nav_button:hover {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text"]};
}}

QToolButton#nav_parent_super_expanded {{
    background-color: {COLORS["teal_pale"]};
    color: {COLORS["teal"]};
}}

QToolButton#nav_parent_super_active, QToolButton#nav_button_super_active,
QToolButton#nav_button_active {{
    background-color: {COLORS["teal"]};
    color: {COLORS["white"]};
}}

QPushButton#sidebar_logout {{
    color: {COLORS["text_3"]};
}}

QPushButton#sidebar_logout:hover {{
    background-color: {COLORS["red_pale"]};
    color: {COLORS["red"]};
}}

QPushButton#btn_navy, QPushButton#btn_outline, QPushButton#btn_ghost,
QPushButton#pos_numpad_key, QPushButton#pos_numpad_action,
QPushButton#payment_option {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border_2"]};
}}

QPushButton#btn_navy:hover, QPushButton#btn_outline:hover,
QPushButton#btn_ghost:hover, QPushButton#pos_numpad_key:hover,
QPushButton#pos_numpad_action:hover, QPushButton#payment_option:hover {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text"]};
}}

QPushButton#btn_danger {{
    background-color: {COLORS["white"]};
    color: {COLORS["red"]};
    border: 1px solid {COLORS["red"]};
}}

QPushButton#btn_danger:hover {{
    background-color: {COLORS["red_pale"]};
    color: {COLORS["red"]};
}}

#card, #card_header, #card_body, #login_card, #stat_card,
#stat_card_navy, #stat_card_teal, #stat_card_amber,
#stat_card_red, #stat_card_green, #stat_card_blue,
#pos_cart_row, #product_card, #role_task_row,
#floor_card_gray, #floor_card_teal, #floor_card_amber {{
    background-color: {COLORS["white"]};
    border-color: {COLORS["border"]};
}}

#dispatch_header {{
    background-color: {COLORS["surface"]};
    border-bottom: 1px solid {COLORS["border"]};
}}

#role_tasks_header {{
    background-color: {COLORS["surface"]};
    border-color: {COLORS["border"]};
}}

#card QLabel, #card_header QLabel, #card_body QLabel,
#login_card QLabel, #stat_card QLabel,
#stat_card_navy QLabel, #stat_card_teal QLabel,
#stat_card_amber QLabel, #stat_card_red QLabel,
#stat_card_green QLabel, #stat_card_blue QLabel,
#product_card QLabel, #pos_cart_row QLabel,
#role_task_row QLabel, #role_tasks_header QLabel,
#floor_card_gray QLabel, #floor_card_teal QLabel,
#floor_card_amber QLabel, #dispatch_header QLabel {{
    color: {COLORS["text"]};
}}

#card_title, #stat_value, #role_task_label {{
    color: {COLORS["text"]};
}}

#stat_label, #role_task_key, #role_task_meta,
#role_tasks_column_label, #form_label, QLabel#form_label {{
    color: {COLORS["text_3"]};
}}

#pos_panel_left, #pos_panel_mid, #pos_panel_right, #page_content {{
    background-color: #f6f7fb;
}}

#pos_empty_label {{
    color: {COLORS["text_3"]};
}}

#pos_total_value, #pos_qty_label, #pos_live_total, #pos_change_label {{
    color: {COLORS["text"]};
}}

#pos_divider {{
    background-color: {COLORS["border"]};
}}

#alert_navy, #alert_info {{
    background-color: {COLORS["navy_pale"]};
    border-color: {COLORS["navy"]};
}}

#alert_teal, #alert_success {{
    background-color: {COLORS["teal_pale"]};
    border-color: {COLORS["teal"]};
}}

#alert_amber, #alert_warning {{
    background-color: {COLORS["amber_pale"]};
    border-color: {COLORS["amber"]};
}}

#alert_red, #alert_error {{
    background-color: {COLORS["red_pale"]};
    border-color: {COLORS["red"]};
}}

#alert_text_navy, #alert_text_info {{
    color: {COLORS["navy"]};
}}

#alert_text_teal, #alert_text_success {{
    color: {COLORS["teal"]};
}}

#alert_text_amber, #alert_text_warning {{
    color: {COLORS["amber"]};
}}

#alert_text_red, #alert_text_error {{
    color: {COLORS["red"]};
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit,
#password_row {{
    background-color: {COLORS["white"]};
    color: {COLORS["text"]};
    border-color: {COLORS["border_2"]};
}}

QTableWidget {{
    background-color: {COLORS["white"]};
    alternate-background-color: {COLORS["white"]};
    color: {COLORS["text_2"]};
    border-color: {COLORS["border"]};
    gridline-color: {COLORS["border"]};
    selection-background-color: {COLORS["teal_pale"]};
    selection-color: {COLORS["text"]};
}}

QHeaderView::section {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_3"]};
    border-bottom-color: {COLORS["border"]};
}}
"""

APP_THEME += DARK_MODE_OVERRIDES


STATUS_COLORS = {
    status: COLORS[tone if tone != "gray" else "text_3"]
    for status, tone in STATUS_TONES.items()
}

BADGE_TONES = dict(STATUS_TONES)
BADGE_TONES.update({
    "Super Admin": "red",
    "Admin": "navy",
    "Cashier": "blue",
    "Warehouseman": "amber",
    "Bookkeeper": "teal",
    "Warehouse": "amber",
})


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_button_kind(button, kind):
    object_name = {
        "primary": "btn_primary",
        "teal": "btn_primary",
        "success": "btn_primary",
        "navy": "btn_navy",
        "outline": "btn_outline",
        "ghost": "btn_ghost",
        "danger": "btn_danger",
        "warning": "btn_warning",
        "link": "btn_link",
    }.get(kind, "btn_primary")
    button.setObjectName(object_name)
    repolish(button)


def add_card_shadow(widget, blur=16, y=4, alpha=28):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(15, 31, 75, alpha))
    widget.setGraphicsEffect(effect)


def make_card(title=None, body_margins=(18, 18, 18, 18)):
    card = QFrame()
    card.setObjectName("card")
    layout = None
    if title is not None:
        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout

        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setObjectName("card_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 13, 18, 13)
        title_label = QLabel(title)
        title_label.setObjectName("card_title")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        outer.addWidget(header)

        body = QFrame()
        body.setObjectName("card_body")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(*body_margins)
        layout.setSpacing(12)
        outer.addWidget(body)
    return card, layout


def make_badge(text, tone="gray"):
    label = QLabel(str(text))
    label.setObjectName(f"badge_{tone}")
    label.setAlignment(Qt.AlignCenter)
    label.setMinimumHeight(22)
    return label


def tone_for_status(status, default="gray"):
    return BADGE_TONES.get(str(status), default)


def display_order_status(status):
    return "Preparing" if status == "Processing" else (status or "Pending")


def backend_order_status(display):
    if display == "Preparing":
        return "Processing"
    if display in {"All Status", "All"}:
        return None
    return display


def configure_table(table):
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setAlternatingRowColors(False)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().setDefaultSectionSize(42)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)


def table_item(text, align=None, mono=False, bold=False, color=None):
    if align is None:
        align = Qt.AlignRight | Qt.AlignVCenter if mono else Qt.AlignLeft | Qt.AlignVCenter
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    font = QFont(FONT_FALLBACK, 10)
    if mono:
        font = QFont(MONO_FALLBACK, 10)
    if bold:
        font.setBold(True)
    item.setFont(font)
    if color:
        item.setForeground(QColor(color))
    return item


def stock_status(quantity, threshold):
    if quantity <= 0:
        return "Critical"
    if quantity <= threshold:
        return "Low"
    return "OK"


def stock_color(status):
    return {
        "OK": COLORS["green"],
        "Low": COLORS["amber"],
        "Critical": COLORS["red"],
    }.get(status, COLORS["text"])

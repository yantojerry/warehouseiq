from PyQt5.QtGui import QIcon

from utils.theme import COLORS


try:
    import qtawesome as qta
except Exception:
    qta = None


def icon(name, color=None):
    if qta is None:
        return QIcon()
    return qta.icon(name, color=color or COLORS["white"])

# Owns role constants and normalization helpers.

ROLE_SUPER_ADMIN = "Super Admin"
ROLE_ADMIN = "Admin"
ROLE_WAREHOUSEMAN = "Warehouseman"
ROLE_BOOKKEEPER = "Bookkeeper"
ROLE_CASHIER = "Cashier"

SYSTEM_ROLES = (
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_WAREHOUSEMAN,
    ROLE_BOOKKEEPER,
    ROLE_CASHIER,
)

LEGACY_ROLE_ALIASES = {
    "sales": ROLE_CASHIER,
    "sales staff": ROLE_CASHIER,
    "staff": ROLE_CASHIER,
    "warehouse": ROLE_WAREHOUSEMAN,
    "warehouse staff": ROLE_WAREHOUSEMAN,
    "book keeper": ROLE_BOOKKEEPER,
    "superadmin": ROLE_SUPER_ADMIN,
    "super admin": ROLE_SUPER_ADMIN,
}


def canonical_role(role):
    text = (role or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered in LEGACY_ROLE_ALIASES:
        return LEGACY_ROLE_ALIASES[lowered]
    for system_role in SYSTEM_ROLES:
        if lowered == system_role.lower():
            return system_role
    return text


def is_super_admin(role):
    return canonical_role(role) == ROLE_SUPER_ADMIN


def display_role(role):
    return canonical_role(role) or "Unknown"

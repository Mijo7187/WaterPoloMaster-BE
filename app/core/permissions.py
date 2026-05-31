# ============================================
# PERMISSIONS - Role-Based Access Control
# ============================================
# Defines all permissions and maps them to roles.
# Use check_permissions(Permission.SOMETHING) as a
# per-endpoint dependency to enforce access control.
#
# USAGE IN ROUTERS:
#   @router.get("/", dependencies=[Depends(check_permissions(Permission.VIEW_USERS))])
#   def get_users(...):
#
# HOW TO SCALE:
#   1. Add new Permission enum values
#   2. Add them to ROLE_PERMISSIONS for the appropriate roles
#   3. Use check_permissions(Permission.NEW_THING) on your endpoint
# ============================================

import enum
from fastapi import Depends

from app.core.api.exceptions import ForbiddenException
from app.features.users.users_models import UserRole


# ============================================
# PERMISSION ENUM
# ============================================
class Permission(str, enum.Enum):
    # Users
    VIEW_USERS = "VIEW_USERS"
    VIEW_USER = "VIEW_USER"
    UPDATE_USER = "UPDATE_USER"
    DELETE_USER = "DELETE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"

    # Contry
    VIEW_COUNTRIES = "VIEW_COUNTRIES"
    VIEW_COUNTRY = "VIEW_COUNTRY"
    CREATE_COUNTRY = "CREATE_COUNTRY"
    UPDATE_COUNTRY = "UPDATE_COUNTRY"

    # City
    VIEW_CITIES = "VIEW_CITIES"
    VIEW_CITY = "VIEW_CITY"
    CREATE_CITY = "CREATE_CITY"
    UPDATE_CITY = "UPDATE_CITY"

    # Companies
    VIEW_COMPANY = "VIEW_COMPANY"
    VIEW_COMPANIES = "VIEW_COMPANIES"
    CREATE_COMPANY = "CREATE_COMPANY"
    UPDATE_COMPANY = "UPDATE_COMPANY"

    # Trainings
    VIEW_TRAININGS = "VIEW_TRAININGS"
    VIEW_TRAINING = "VIEW_TRAINING"
    CREATE_TRAINING = "CREATE_TRAINING"
    UPDATE_TRAINING = "UPDATE_TRAINING"

    # Wallet
    VIEW_WALLET = "VIEW_WALLET"
    VIEW_WALLETS = "VIEW_WALLETS"
    CREATE_WALLET = "CREATE_WALLET"
    UPDATE_WALLET = "UPDATE_WALLET"

    # Payment Type
    VIEW_PAYMENT_TYPE = "VIEW_PAYMENT_TYPE"
    VIEW_PAYMENT_TYPES = "VIEW_PAYMENT_TYPES"
    CREATE_PAYMENT_TYPE = "CREATE_PAYMENT_TYPE"
    UPDATE_PAYMENT_TYPE = "UPDATE_PAYMENT_TYPE"

    # Payment
    VIEW_PAYMENT = "VIEW_PAYMENT"
    VIEW_PAYMENTS = "VIEW_PAYMENTS"
    CREATE_PAYMENT = "CREATE_PAYMENT"
    UPDATE_PAYMENT = "UPDATE_PAYMENT"

    # Expense Category
    VIEW_EXPENSE_CATEGORIES = "VIEW_EXPENSE_CATEGORIES"
    VIEW_EXPENSE_CATEGORY = "VIEW_EXPENSE_CATEGORY"

    # Income Category
    VIEW_INCOME_CATEGORIES = "VIEW_INCOME_CATEGORIES"
    VIEW_INCOME_CATEGORY = "VIEW_INCOME_CATEGORY"


    # Wallet ledger
    VIEW_WALLET_LEDGER = "VIEW_WALLET_LEDGER"


# ============================================
# ROLE → PERMISSIONS MAPPING
# ============================================
ROLE_PERMISSIONS: dict[UserRole, list[Permission]] = {
    #region User
    UserRole.USER: [
        Permission.VIEW_USERS,
        Permission.VIEW_USER,
    ],
    #endregion User
    #region Admin
    UserRole.ADMIN: [
        Permission.VIEW_USERS,
        Permission.VIEW_USER,
        Permission.UPDATE_USER,
        Permission.DELETE_USER,
        Permission.DEACTIVATE_USER,
        Permission.VIEW_COMPANIES,
        Permission.VIEW_TRAININGS,
        Permission.VIEW_TRAINING,
        Permission.CREATE_TRAINING,
        Permission.UPDATE_TRAINING,
        Permission.VIEW_COUNTRIES,
        Permission.CREATE_COUNTRY,
        Permission.UPDATE_COUNTRY,
        Permission.VIEW_COMPANY,
        Permission.VIEW_CITIES,
        Permission.VIEW_CITY,
        Permission.CREATE_CITY,
        Permission.UPDATE_CITY,
        Permission.VIEW_WALLET,
        Permission.VIEW_WALLETS,
        Permission.VIEW_WALLET_LEDGER,
        Permission.VIEW_PAYMENT_TYPE,
        Permission.VIEW_PAYMENT_TYPES,
        Permission.VIEW_PAYMENT,
        Permission.VIEW_PAYMENTS,
        Permission.VIEW_EXPENSE_CATEGORIES,
        Permission.VIEW_EXPENSE_CATEGORY,
        Permission.VIEW_INCOME_CATEGORIES,
        Permission.VIEW_INCOME_CATEGORY,

    ],
    #endregion Admin
    #region Super Admin — has ALL permissions
    UserRole.SUPER_ADMIN: list(Permission),
    #endregion Super Admin
}


# ============================================
# PERMISSION CHECK DEPENDENCY FACTORY
# ============================================
def check_permissions(permission: Permission):
    """
    Returns a FastAPI dependency that checks if the
    current user's role(s) include the required permission.

    Internally resolves get_current_active_user (auth + active check).
    """
    # Lazy import to avoid circular dependency
    from app.features.auth.auth_dependencies import get_current_active_user
    from app.features.users.users_models import User

    async def _check(current_user: User = Depends(get_current_active_user)):
        user_permissions: set[Permission] = set()
        for role in (current_user.roles or []):
            role_enum = UserRole(role) if isinstance(role, str) else role
            user_permissions.update(ROLE_PERMISSIONS.get(role_enum, []))

        if permission not in user_permissions:
            raise ForbiddenException("Not enough permissions to perform this action.")

    return _check

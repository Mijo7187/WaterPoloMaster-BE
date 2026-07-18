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

    # Training Users
    VIEW_TRAINING_USERS = "VIEW_TRAINING_USERS"
    VIEW_TRAINING_USERS_ITEM = "VIEW_TRAINING_USERS_ITEM"
    CREATE_TRAINING_USERS = "CREATE_TRAINING_USERS"
    DELETE_TRAINING_USERS = "DELETE_TRAINING_USERS"

    # Training Segments
    VIEW_TRAINING_SEGMENT = "VIEW_TRAINING_SEGMENT"
    CREATE_TRAINING_SEGMENT = "CREATE_TRAINING_SEGMENT"
    UPDATE_TRAINING_SEGMENT = "UPDATE_TRAINING_SEGMENT"
    DELETE_TRAINING_SEGMENT = "DELETE_TRAINING_SEGMENT"

    # Exercise Option (sifarnik)
    VIEW_EXERCISE_OPTIONS = "VIEW_EXERCISE_OPTIONS"
    VIEW_EXERCISE_OPTION = "VIEW_EXERCISE_OPTION"
    CREATE_EXERCISE_OPTION = "CREATE_EXERCISE_OPTION"
    UPDATE_EXERCISE_OPTION = "UPDATE_EXERCISE_OPTION"

    # Quarter
    VIEW_QUARTERS = "VIEW_QUARTERS"
    VIEW_QUARTER = "VIEW_QUARTER"
    CREATE_QUARTER = "CREATE_QUARTER"
    UPDATE_QUARTER = "UPDATE_QUARTER"
    DELETE_QUARTER = "DELETE_QUARTER"

    # Quarter Users
    VIEW_QUARTER_USERS = "VIEW_QUARTER_USERS"
    VIEW_QUARTER_USER = "VIEW_QUARTER_USER"
    CREATE_QUARTER_USER = "CREATE_QUARTER_USER"
    DELETE_QUARTER_USER = "DELETE_QUARTER_USER"

    # Tournament
    VIEW_TOURNAMENTS = "VIEW_TOURNAMENTS"
    VIEW_TOURNAMENT = "VIEW_TOURNAMENT"
    CREATE_TOURNAMENT = "CREATE_TOURNAMENT"
    UPDATE_TOURNAMENT = "UPDATE_TOURNAMENT"
    DELETE_TOURNAMENT = "DELETE_TOURNAMENT"

    # Tournament Users
    VIEW_TOURNAMENT_USERS = "VIEW_TOURNAMENT_USERS"
    VIEW_TOURNAMENT_USER = "VIEW_TOURNAMENT_USER"
    CREATE_TOURNAMENT_USER = "CREATE_TOURNAMENT_USER"
    DELETE_TOURNAMENT_USER = "DELETE_TOURNAMENT_USER"


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
        Permission.CREATE_COMPANY,
        Permission.UPDATE_COMPANY,
        Permission.VIEW_CITIES,
        Permission.VIEW_CITY,
        Permission.CREATE_CITY,
        Permission.UPDATE_CITY,
        Permission.VIEW_WALLET,
        Permission.VIEW_WALLETS,
        Permission.VIEW_WALLET_LEDGER,
        Permission.VIEW_PAYMENT,
        Permission.VIEW_PAYMENTS,
        Permission.VIEW_EXPENSE_CATEGORIES,
        Permission.VIEW_EXPENSE_CATEGORY,
        Permission.VIEW_INCOME_CATEGORIES,
        Permission.VIEW_INCOME_CATEGORY,
        Permission.VIEW_TRAINING_USERS,
        Permission.VIEW_TRAINING_USERS_ITEM,
        Permission.CREATE_TRAINING_USERS,
        Permission.DELETE_TRAINING_USERS,
        Permission.VIEW_TRAINING_SEGMENT,
        Permission.CREATE_TRAINING_SEGMENT,
        Permission.UPDATE_TRAINING_SEGMENT,
        Permission.DELETE_TRAINING_SEGMENT,
        Permission.VIEW_EXERCISE_OPTIONS,
        Permission.VIEW_EXERCISE_OPTION,
        Permission.CREATE_EXERCISE_OPTION,
        Permission.UPDATE_EXERCISE_OPTION,
        Permission.VIEW_QUARTERS,
        Permission.VIEW_QUARTER,
        Permission.CREATE_QUARTER,
        Permission.UPDATE_QUARTER,
        Permission.DELETE_QUARTER,
        Permission.VIEW_QUARTER_USERS,
        Permission.VIEW_QUARTER_USER,
        Permission.CREATE_QUARTER_USER,
        Permission.DELETE_QUARTER_USER,
        Permission.VIEW_TOURNAMENTS,
        Permission.VIEW_TOURNAMENT,
        Permission.CREATE_TOURNAMENT,
        Permission.UPDATE_TOURNAMENT,
        Permission.DELETE_TOURNAMENT,
        Permission.VIEW_TOURNAMENT_USERS,
        Permission.VIEW_TOURNAMENT_USER,
        Permission.CREATE_TOURNAMENT_USER,
        Permission.DELETE_TOURNAMENT_USER,
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

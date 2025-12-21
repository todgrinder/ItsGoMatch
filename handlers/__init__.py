from aiogram import Router

from .start import router as start_router
from .profile import router as profile_router
from .events import router as events_router
from .elements import router as elements_router
from .search import router as search_router
from .requests import router as requests_router
from .user import router as user_router
from .admin import router as admin_router


def setup_routers() -> Router:
    """Собрать все роутеры в один главный."""
    main_router = Router()
    
    # Админ-роутер должен быть первым, чтобы его фильтры применялись раньше
    main_router.include_router(admin_router)
    main_router.include_router(start_router)
    main_router.include_router(profile_router)
    main_router.include_router(events_router)
    main_router.include_router(elements_router)
    main_router.include_router(search_router)
    main_router.include_router(requests_router)
    main_router.include_router(user_router)
    
    return main_router

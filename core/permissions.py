def is_manager(user) -> bool:
    return user.is_authenticated and (
        user.is_superuser or user.is_staff or user.groups.filter(name="Managers").exists()
    )

def is_sales(user) -> bool:
    return user.is_authenticated and user.groups.filter(name="Sales").exists()
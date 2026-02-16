from django import template

register = template.Library()


@register.filter
def user_role(user):
    """Return the user's profile role, or 'scheduler' if no profile."""
    if not user or not hasattr(user, 'profile'):
        return 'scheduler'
    profile = user.profile
    return profile.role if profile else 'scheduler'

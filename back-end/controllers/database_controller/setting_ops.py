from database.models import site_setting

SITE_THEMES = ("civic-light", "civic", "civic-vt")
DEFAULT_THEME = "civic-light"


def get_setting(key, default, session):
    row = session.query(site_setting).filter(site_setting.key == key).one_or_none()
    return row.value if row else default


def set_setting(key, value, session):
    row = session.query(site_setting).filter(site_setting.key == key).one_or_none()
    if row:
        row.value = value
    else:
        session.add(site_setting(key=key, value=value))
    session.commit()


def get_site_theme(session):
    theme = get_setting("site_theme", DEFAULT_THEME, session)
    return theme if theme in SITE_THEMES else DEFAULT_THEME

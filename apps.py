from django.apps import AppConfig


# Tandoor loads the plugin class as dir(module)[1], so the class name must sort right after "AppConfig".
class LinkPreviewConfig(AppConfig):
    name = 'recipes.plugins.link_preview'
    verbose_name = 'Descriptive recipe links and link previews'
    VERSION = '0.1.0'
    base_url = 'plugin/link-preview/'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # ready() runs before the WSGI handler builds its middleware chain, so appending here is enough
        from django.conf import settings
        path = 'recipes.plugins.link_preview.middleware.LinkPreviewMiddleware'
        if path not in settings.MIDDLEWARE:
            settings.MIDDLEWARE.append(path)
        print('[link_preview] middleware installed')

from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag(takes_context=True)
def static_ver(context, path):
    url = static(path)
    version = context.get("static_version")
    if version is not None:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}v={version}"
    return url

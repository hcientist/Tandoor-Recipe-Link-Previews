"""
Descriptive recipe links and link previews for Tandoor.

- /recipe/<id>/ pages get Open Graph tags (title, image, description) whenever the viewer may see the recipe:
  logged in with access, or holding a valid share link.
- Link-preview fetchers are always logged out. A logged-out request that carries the recipe's title slug
  (/recipe/192/?cucumber-pomegranate-salad) gets a small preview page instead of the login redirect.
  The slug acts as the key: without the exact title nobody can walk the ids to collect previews,
  and private recipes never get one.
- For logged-in users a page script keeps the slug in the address bar, so copied and shared URLs are descriptive.
- Share links created with Tandoor's Share button get the slug appended too.
- On share-link pages the guest app bar's logo links back to this instance instead of tandoor.dev.
"""
import html
import json
import re
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.urls import reverse
from django.utils.text import slugify
from django_scopes import scopes_disabled

RECIPE_PAGE = re.compile(r'^/recipe/(\d+)/?$')
SHARE_LINK_API = re.compile(r'^/api/share-link/(\d+)/?$')
DESCRIPTION_LIMIT = 300

PAGE_SCRIPT = """<script>(() => {
  if (window.__tandoorLinkPreview) return;
  window.__tandoorLinkPreview = true;
  const page = /^\\/recipe\\/(\\d+)\\/?$/, slugs = {};
  async function addSlug() {
    const m = location.pathname.match(page);
    if (!m) return;
    const id = m[1];
    if (!(id in slugs)) {
      try {
        const r = await fetch(`%(base)splugin/link-preview/slug/${id}/`, {credentials: 'same-origin'});
        slugs[id] = r.ok ? (await r.json()).slug : '';
      } catch (e) { return; }
    }
    const slug = slugs[id];
    if (!slug || (location.pathname.match(page) || [])[1] !== id) return;
    const params = new URLSearchParams(location.search);
    if (params.has(slug)) return;
    for (const [k, v] of [...params]) if (v === '' && /^[a-z0-9-]+$/.test(k)) params.delete(k);  // stale slug after a rename
    const rest = params.toString();
    history.replaceState(history.state, '', location.pathname + '?' + (rest ? rest + '&' : '') + slug + location.hash);
  }
  for (const name of ['pushState', 'replaceState']) {
    const original = history[name];
    history[name] = function (...args) { const r = original.apply(this, args); setTimeout(addSlug, 0); return r; };
  }
  addEventListener('popstate', () => setTimeout(addSlug, 0));
  addSlug();
})();</script>"""

# Logged-out share-link visitors get Tandoor's guest app bar, whose logo hard-links to https://tandoor.dev.
# Point it at this instance instead; the observer catches the bar whenever Vue renders it.
HOME_LINK_SCRIPT = """<script>(() => {
  const home = %(home)s;
  const fix = () => document.querySelectorAll('.v-app-bar a[href="https://tandoor.dev"]').forEach(a => { a.href = home; });
  new MutationObserver(fix).observe(document.documentElement, {childList: true, subtree: true});
  fix();
})();</script>"""

STUB_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
%(og)s
<style>
  :root { color-scheme: light dark; --bg: #f6f4ef; --card: #fff; --ink: #1f1d1a; --muted: #6b665e; --accent: #b98b37; }
  @media (prefers-color-scheme: dark) { :root { --bg: #181715; --card: #23211e; --ink: #f1ede6; --muted: #a39d93; } }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--ink);
         font: 16px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  main { width: min(28rem, calc(100vw - 2rem)); background: var(--card); border-radius: 14px; overflow: hidden;
         box-shadow: 0 6px 24px rgb(0 0 0 / .12); }
  img { display: block; width: 100%%; aspect-ratio: 4 / 3; object-fit: cover; }
  div { padding: 1.1rem 1.25rem 1.3rem; }
  h1 { font-size: 1.3rem; margin: 0 0 .35rem; }
  p { margin: 0 0 1rem; color: var(--muted); font-size: .95rem; }
  a { display: inline-block; background: var(--accent); color: #fff; text-decoration: none; padding: .6rem 1rem;
      border-radius: 8px; font-weight: 600; }
</style>
</head><body><main>
%(image)s<div><h1>%(title)s</h1>%(description)s<a href="%(login)s">Sign in to open in Tandoor</a></div>
</main></body></html>"""


def recipe_slug(recipe):
    return slugify(recipe.name)


def _recipe(pk):
    from cookbook.models import Recipe
    with scopes_disabled():
        return Recipe.objects.filter(pk=pk).first()


def visible_to(request, pk):
    """The recipe if the logged-in user may open it: same space, and not private unless theirs or shared with them."""
    from cookbook.models import Recipe
    space = getattr(request, 'space', None)
    if space is None:
        return None
    with scopes_disabled():
        recipe = Recipe.objects.filter(pk=pk, space=space).first()
        if recipe and recipe.private and recipe.created_by_id != request.user.id \
                and not recipe.shared.filter(pk=request.user.pk).exists():
            return None
    return recipe


def _share_valid(recipe, share):
    from cookbook.models import ShareLink
    try:
        with scopes_disabled():
            return ShareLink.objects.filter(recipe=recipe, uuid=share, abuse_blocked=False).exists()
    except ValidationError:
        return False


def _slug_matches(request, recipe):
    wanted = recipe_slug(recipe)
    return bool(wanted) and any(v == '' and slugify(k) == wanted for k, v in request.GET.items())


def _absolute(request, path):
    return request.build_absolute_uri(path)


def og_tags(request, recipe):
    slug = recipe_slug(recipe)
    url = _absolute(request, f"{reverse('index')}recipe/{recipe.pk}/" + (f'?{slug}' if slug else ''))
    tags = [('og:type', 'website'), ('og:site_name', 'Tandoor'), ('og:title', recipe.name), ('og:url', url)]
    if recipe.description:
        tags.append(('og:description', recipe.description[:DESCRIPTION_LIMIT]))
    if recipe.image:
        tags.append(('og:image', _absolute(request, recipe.image.url)))
    lines = [f'<meta property="{k}" content="{html.escape(v, quote=True)}">' for k, v in tags]
    lines.append(f'<meta name="twitter:card" content="{"summary_large_image" if recipe.image else "summary"}">')
    return '\n'.join(lines)


def stub_page(request, recipe):
    login = reverse('account_login') + '?next=' + quote(request.get_full_path(), safe='')
    image = f'<img src="{html.escape(_absolute(request, recipe.image.url))}" alt="">' if recipe.image else ''
    description = f'<p>{html.escape(recipe.description[:DESCRIPTION_LIMIT])}</p>' if recipe.description else ''
    body = STUB_PAGE % {'title': html.escape(recipe.name), 'og': og_tags(request, recipe), 'image': image,
                        'description': description, 'login': html.escape(login)}
    response = HttpResponse(body, content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'private, no-store'
    response['X-Robots-Tag'] = 'noindex'
    return response


def _inject(response, snippet):
    if response.status_code != 200 or 'text/html' not in response.get('Content-Type', '') or response.streaming:
        return response
    content = response.content
    if b'</head>' not in content:
        return response
    response.content = content.replace(b'</head>', snippet.encode() + b'</head>', 1)
    if response.has_header('Content-Length'):
        response['Content-Length'] = str(len(response.content))
    return response


class LinkPreviewMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'GET' and (m := RECIPE_PAGE.match(request.path_info)):
            return self.recipe_page(request, int(m.group(1)))
        response = self.get_response(request)
        if (m := SHARE_LINK_API.match(request.path_info)) and response.status_code == 200:
            response = self.describe_share_link(response, int(m.group(1)))
        return response

    def recipe_page(self, request, pk):
        authenticated = request.user.is_authenticated
        share = request.GET.get('share')
        recipe = _recipe(pk)

        if recipe and not authenticated and not share and not recipe.private and _slug_matches(request, recipe):
            return stub_page(request, recipe)

        response = self.get_response(request)
        if recipe is None:
            return response
        visible = (share and _share_valid(recipe, share)) or (authenticated and visible_to(request, pk) is not None)
        snippet = og_tags(request, recipe) if visible else ''
        if authenticated:
            snippet += PAGE_SCRIPT % {'base': reverse('index')}
        elif share:
            snippet += HOME_LINK_SCRIPT % {'home': json.dumps(_absolute(request, reverse('index')))}
        return _inject(response, snippet) if snippet else response

    def describe_share_link(self, response, pk):
        try:
            data = json.loads(response.content)
            recipe = _recipe(pk)
            if recipe and data.get('link') and (slug := recipe_slug(recipe)):
                data['link'] = f"{data['link']}&{slug}"
                response.content = json.dumps(data)
                if response.has_header('Content-Length'):
                    response['Content-Length'] = str(len(response.content))
        except (ValueError, TypeError):
            pass
        return response

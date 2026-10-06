# Tandoor Recipe Link Previews

A backend plugin for [Tandoor Recipes](https://github.com/TandoorRecipes/recipes) 2.6.x that makes recipe links
descriptive and gives them rich previews in Messages, Slack, Discord and other apps.

- **Descriptive links.** While you are logged in, the address bar shows the recipe's title as a slug, for example
  `/recipe/192/?cucumber-pomegranate-salad`. Links you copy or share from the browser carry it. Share links
  created with Tandoor's Share button get the slug too.
- **Link previews.** Preview fetchers are never logged in, so Tandoor normally sends them to the login page. With this
  plugin, a logged-out request that carries the recipe's exact title slug gets a small page with Open Graph tags
  (title, image, description) and a "Sign in to open in Tandoor" button. Logged-in pages and valid share links get the same tags.
- **Home link for guests.** On share-link pages, Tandoor's guest header logo links to tandoor.dev. The plugin points
  it at your own instance instead.

## Privacy

- The slug works as a key: without the recipe's exact title, a logged-out visitor just gets the usual login redirect.
  So nobody can walk recipe ids to collect previews.
- Recipes marked private never get a logged-out preview.
- The preview shows only the title, the image and the first 300 characters of the description. The recipe itself
  still needs a login or a share link.
- Recipe images are served from Tandoor's `/media/` path, which Tandoor already serves without authentication.

## Install

Tandoor loads any Django app placed in `/opt/recipes/recipes/plugins/`. With docker compose, clone this repo into a
`plugins/link_preview` folder next to your compose file and mount it (or mount the whole `plugins` folder):

```yaml
services:
  web_recipes:
    volumes:
      - ./plugins/link_preview:/opt/recipes/recipes/plugins/link_preview:ro
```

Recreate the container. The log should show `PLUGIN link_preview loaded` and `[link_preview] middleware installed`.
The folder name must be `link_preview`.

## How it works

- `middleware.py` handles `GET /recipe/<id>/`. It serves the preview page, or it adds the Open Graph tags plus a
  small page script to Tandoor's normal HTML. It also appends the slug to the link returned by `/api/share-link/<id>`.
- The page script watches the SPA's navigation and uses `history.replaceState` to add the slug. It gets the slug
  from `/plugin/link-preview/slug/<id>/`, which answers only for recipes the logged-in user can open.
- Slugs come from Django's `slugify(recipe.name)`. After a rename, old links still open the recipe for logged-in users;
  they just stop producing previews.

from django.http import JsonResponse

from .middleware import recipe_slug, visible_to


def slug(request, pk):
    """The slug the page script appends to the address bar; only for recipes the user can open."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'login required'}, status=403)
    recipe = visible_to(request, pk)
    if recipe is None:
        return JsonResponse({'error': 'not found'}, status=404)
    return JsonResponse({'slug': recipe_slug(recipe)})

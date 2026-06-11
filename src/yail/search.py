"""Image search via the DDGS metasearch package."""
import logging

logger = logging.getLogger(__name__)


def search_images(term: str, max_images: int = 1000) -> list[str]:
    """Search for images and return a list of image URLs (empty on failure)."""
    try:
        from ddgs import DDGS
        results = DDGS().images(query=term, max_results=max_images)
        urls = [result["image"] for result in results]
        logger.info(f"Found {len(urls)} images for search term: '{term}'")
        return urls
    except Exception as e:
        logger.error(f"Error searching for images '{term}': {e}")
        return []

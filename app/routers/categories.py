from fastapi import APIRouter

router = APIRouter(prefix="/recommend", tags=["recommend"])

CATEGORIES = ["Blockbuster", "Grand Public", "Auteur"]


@router.get("/categories")
def list_categories() -> dict:
    """Retourne la liste des catégories de style utilisables pour filtrer /recommend/."""
    return {"categories": CATEGORIES}

"""
Enveloppe de réponse commune — cf 00-contrat-commun.md section 2 :
    Succès : { "success": true, "data": { ... } }
    Erreur : { "success": false, "error": "message" }

`SuccessEnvelope` est "générique" : `SuccessEnvelope[ProjectListResponse]` veut
dire "un succès dont le contenu de `data` est un ProjectListResponse". Ça évite
de réécrire `success: bool` dans chaque schéma de réponse, et ça garde une
doc Swagger correcte pour chaque route.

⚠️ Fichier pas explicitement assigné dans les fiches (ni A ni B) — je le mets
ici car j'en ai besoin pour mes routes tout de suite. Le pendant "erreur"
({"success": false, "error": ...}) doit être produit par un exception handler
global dans `app/main.py` (probablement le fichier de A) : à valider en sync
d'équipe, sinon FastAPI renverra ses erreurs au format par défaut `{"detail": ...}`
qui NE MATCHE PAS le contrat.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T


class SimpleSuccessResponse(BaseModel):
    """Pour les routes qui renvoient juste `{"success": true}` sans "data"
    (ex: DELETE /api/projects/{id}), telles que littéralement écrites dans le
    contrat commun."""

    success: bool = True

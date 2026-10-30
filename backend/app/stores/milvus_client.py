"""
Vector Store Client Re-export for Backward Compatibility.
All vector storage and semantic retrieval logic is maintained in `vector_client.py`.
"""

from backend.app.stores.vector_client import (
    FEW_SHOT_TEMPLATES,
    get_rendered_few_shots,
    add_verified_example,
    retrieve_few_shots,
)

__all__ = [
    "FEW_SHOT_TEMPLATES",
    "get_rendered_few_shots",
    "add_verified_example",
    "retrieve_few_shots",
]

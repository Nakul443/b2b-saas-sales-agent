# reads catalog.json

import os
import json
from typing import List, Dict, Any

# path for catalog.json
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CATALOG_PATH = os.path.join(BASE_DIR, "catalog.json")

def search_catalog(query: str) -> str:
    """
    Executes a real keyword search over the product catalog JSON configuration file.
    
    Args:
        query: The search term or feature string requested by the user.
    Returns:
        A serialized JSON string containing matching plans and their contextual details.
    """
    if not os.path.exists(CATALOG_PATH):
        return json.dumps({"error": "No file found!"})

    try:
        with open(CATALOG_PATH, "r") as f:
            catalog_data = json.load(f)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse catalog data: {str(e)}"})

    query_lower = query.lower()
    matched_plans = []
    plans = catalog_data.get("plans", [])

    for plan in plans:
        # Extract fields for explicit string search mapping
        name = plan.get("name", "").lower()
        features = " ".join(plan.get("features", [])).lower()
        audience = plan.get("target_audience", "").lower()

        # If the search query appears in the name, features array, or audience description
        if query_lower in name or query_lower in features or query_lower in audience:
            matched_plans.append(plan)

    # Architectural safety fall-through: If no specific keyword hits are found, 
    # return all tiers so the LLM doesn't starve for context.
    results = matched_plans if matched_plans else plans

    return json.dumps({
        "status": "success",
        "search_query": query,
        "results": results
    }, indent=2)
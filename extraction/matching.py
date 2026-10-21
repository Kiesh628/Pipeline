from sentence_transformers import SentenceTransformer, util
import torch
import csv
from pathlib import Path

class SemanticMatcher:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        # This downloads a tiny ~80MB model once, then runs locally
        print("Loading local embedding model...")
        self.model = SentenceTransformer(model_name)
        
        # Dictionaries to store our loaded lookups and their pre-computed vectors
        self.categories = {
            "materials": {"names": [], "vectors": None},
            "room_loads": {"names": [], "vectors": None}
            # Add others as needed
        }

    def load_and_embed_csv(self, category: str, csv_path: Path, name_column_index: int = 0):
        """Reads the Honeybee CSV and pre-computes the vectors."""
        names = []
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if row:
                    names.append(row[name_column_index])
                    
        self.categories[category]["names"] = names
        # Pre-compute vectors (this is the "Index")
        self.categories[category]["vectors"] = self.model.encode(names, convert_to_tensor=True)
        print(f"Loaded and embedded {len(names)} items for '{category}'.")

    def search(self, category: str, query: str, top_k: int = 3) -> list[tuple[str, float]]:
        """Takes an unknown IFC string and finds the closest matches in the category."""
        category_data = self.categories.get(category)
        if not category_data or category_data["vectors"] is None:
            return []

        # Convert the unknown IFC name to a vector
        query_vector = self.model.encode(query, convert_to_tensor=True)
        
        # Calculate Cosine Similarity against the pre-computed database
        hits = util.semantic_search(query_vector, category_data["vectors"], top_k=top_k)[0]
        
        # Format results: [(Match_Name, Confidence_Score)]
        results = []
        for hit in hits:
            match_name = category_data["names"][hit['corpus_id']]
            score = hit['score']
            results.append((match_name, score))
            
        return results

# --- Example Usage ---
# matcher = SemanticMatcher()
# matcher.load_and_embed_csv("materials", Path("lookup_tables/materials.csv"))
# top_matches = matcher.search("materials", "marble wall board 15mm")
# print(top_matches) 
# Output: [('Gypsum Board', 0.65), ('Concrete', 0.32), ...]
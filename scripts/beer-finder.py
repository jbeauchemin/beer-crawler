import json
from pathlib import Path
from typing import List, Dict, Optional
from difflib import SequenceMatcher

class BeerFinder:
    def __init__(self, json_files: List[str], 
                 producer_threshold: float = 0.6,
                 name_threshold: float = 0.8):
        """
        Initialise le chercheur de bières avec les fichiers JSON
        
        Args:
            json_files: Liste des chemins vers les fichiers JSON
            producer_threshold: Seuil de similarité pour producteur (défaut 0.6)
            name_threshold: Seuil de similarité pour nom (défaut 0.8)
        """
        self.beers = []
        self.producer_threshold = producer_threshold
        self.name_threshold = name_threshold
        self.load_beers(json_files)
    
    def load_beers(self, json_files: List[str]):
        """Charge toutes les bières depuis les fichiers JSON"""
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    source = Path(file_path).stem
                    for beer in data:
                        beer['source'] = source
                    self.beers.extend(data)
                print(f"✓ Chargé {len(data)} bières depuis {file_path}")
            except Exception as e:
                print(f"✗ Erreur lors du chargement de {file_path}: {e}")
    
    def normalize_text(self, text: str) -> str:
        """
        Normalise le texte pour la comparaison:
        - Minuscules
        - Retire mots communs (microbrasserie, brasserie, inc, etc.)
        - Retire ponctuation
        """
        if not text:
            return ""
        
        text = text.lower()
        
        # Mots à ignorer
        stop_words = [
            'microbrasserie', 'brasserie', 'inc', 'inc.', 
            'ltée', 'ltd', 'limited', 'brewing', 'brewery',
            'co', 'company', 'the', 'le', 'la', 'les',
            'coopérative', 'de', 'travail', 'brassicole'
        ]
        
        # Retire ponctuation
        for char in '.,!?;:()[]{}"\'-–':
            text = text.replace(char, ' ')
        
        # Retire mots communs
        words = text.split()
        words = [w for w in words if w not in stop_words]
        
        return ' '.join(words).strip()
    
    def normalize_beer_name(self, text: str) -> str:
        """
        Normalise le nom de bière (plus léger que pour producteur)
        - Minuscules
        - Retire ponctuation
        - Garde les mots importants
        """
        if not text:
            return ""
        
        text = text.lower()
        
        # Retire seulement la ponctuation
        for char in '.,!?;:()[]{}"\'-–':
            text = text.replace(char, ' ')
        
        # Retire espaces multiples
        return ' '.join(text.split()).strip()
    
    def calculate_similarity(self, str1: str, str2: str, for_name: bool = False) -> float:
        """
        Calcule la similarité entre deux chaînes (0.0 à 1.0)
        
        Args:
            str1: Première chaîne
            str2: Deuxième chaîne
            for_name: Si True, utilise normalisation légère pour noms de bière
        """
        if for_name:
            norm1 = self.normalize_beer_name(str1)
            norm2 = self.normalize_beer_name(str2)
        else:
            norm1 = self.normalize_text(str1)
            norm2 = self.normalize_text(str2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Pour les noms: vérifier si la recherche est contenue exactement
        if for_name and norm1 in norm2:
            # Bonus si c'est au début du nom
            if norm2.startswith(norm1):
                return 1.0
            # Pénalité si c'est juste une partie
            return 0.95
        
        # Vérifier si l'un contient l'autre (après normalisation)
        if norm1 in norm2 or norm2 in norm1:
            return 1.0
        
        # Calculer similarité de base
        base_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Pour les noms: pénaliser si les mots clés diffèrent
        if for_name:
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            
            # Si des mots clés sont différents, réduire le score
            if words1 and words2:
                word_overlap = len(words1 & words2) / max(len(words1), len(words2))
                # Combiner similarité de séquence et overlap de mots
                return (base_similarity * 0.5) + (word_overlap * 0.5)
        
        return base_similarity
    
    def search(self, producer: str = None, name: str = None, 
               use_fuzzy: bool = True) -> List[Dict]:
        """
        Recherche des bières par producteur et/ou nom
        
        Args:
            producer: Nom du producteur (optionnel)
            name: Nom de la bière (optionnel)
            use_fuzzy: Utiliser matching flou (défaut: True)
            
        Returns:
            Liste des bières trouvées avec score de similarité
        """
        results = []
        
        for beer in self.beers:
            producer_match = True
            name_match = True
            producer_score = 0.0
            name_score = 0.0
            
            # Vérifie le producteur
            if producer:
                beer_producer = beer.get('producer')
                if not beer_producer:
                    producer_match = False
                elif use_fuzzy:
                    producer_score = self.calculate_similarity(producer, beer_producer, for_name=False)
                    producer_match = producer_score >= self.producer_threshold
                else:
                    producer_match = producer.lower() in beer_producer.lower()
                    producer_score = 1.0 if producer_match else 0.0
            
            # Vérifie le nom
            if name:
                beer_name = beer.get('name')
                if not beer_name:
                    name_match = False
                elif use_fuzzy:
                    name_score = self.calculate_similarity(name, beer_name, for_name=True)
                    name_match = name_score >= self.name_threshold
                else:
                    name_match = name.lower() in beer_name.lower()
                    name_score = 1.0 if name_match else 0.0
            
            if producer_match and name_match:
                # Calcule score total (moyenne des scores non-nuls)
                scores = [s for s in [producer_score, name_score] if s > 0]
                total_score = sum(scores) / len(scores) if scores else 0.0
                
                beer_result = beer.copy()
                beer_result['_match_score'] = total_score
                beer_result['_producer_score'] = producer_score
                beer_result['_name_score'] = name_score
                results.append(beer_result)
        
        # Trie par score décroissant
        results.sort(key=lambda x: x['_match_score'], reverse=True)
        
        return results
    
    def display_results(self, results: List[Dict], show_scores: bool = True):
        """Affiche les résultats de recherche de façon lisible"""
        if not results:
            print("\n❌ Aucune bière trouvée")
            return
        
        print(f"\n✓ {len(results)} bière(s) trouvée(s):\n")
        
        for i, beer in enumerate(results, 1):
            print(f"--- Bière #{i} ---")
            if show_scores:
                print(f"📊 Score: {beer['_match_score']:.2%} (Producteur: {beer['_producer_score']:.2%}, Nom: {beer['_name_score']:.2%})")
            print(f"Nom: {beer.get('name', 'N/A')}")
            print(f"Producteur: {beer.get('producer', 'N/A')}")
            print(f"Prix: {beer.get('price', 'N/A')}")
            print(f"Style: {beer.get('style', 'N/A')}")
            print(f"Volume: {beer.get('volume', 'N/A')}")
            print(f"Alcool: {beer.get('alcohol', 'N/A')}")
            print(f"Source: {beer.get('source', 'N/A')}")
            print(f"URL: {beer.get('url', 'N/A')}")
            if beer.get('description'):
                desc = beer['description'][:150] + "..." if len(beer.get('description', '')) > 150 else beer.get('description', '')
                print(f"Description: {desc}")
            print()


def main():
    json_files = [
        'beers_espacehoublon.json',
        'beers_lbab.json',
        'beers_masoif.json',
        'beers_vtub.json'
    ]
    
    # Seuils différents: producteur plus permissif (60%), nom plus strict (80%)
    finder = BeerFinder(json_files, producer_threshold=0.6, name_threshold=0.8)
    
    print("\n=== CHERCHEUR DE BIÈRES ===")
    print(f"Seuil producteur: {finder.producer_threshold:.0%}")
    print(f"Seuil nom: {finder.name_threshold:.0%}\n")
    
    print("Recherche par producteur")
    producer = input("Entrez le nom du producteur (ou laissez vide): ").strip()
    
    print("\nRecherche par nom")
    name = input("Entrez le nom de la bière (ou laissez vide): ").strip()
    
    if producer or name:
        results = finder.search(
            producer=producer if producer else None,
            name=name if name else None,
            use_fuzzy=True
        )
        finder.display_results(results, show_scores=True)
        
        # Affiche quelques exemples de normalisation
        if producer:
            print(f"\n💡 Producteur normalisé: '{producer}' → '{finder.normalize_text(producer)}'")
        if name:
            print(f"💡 Nom normalisé: '{name}' → '{finder.normalize_beer_name(name)}'")
    else:
        print("\n⚠️ Aucun critère de recherche fourni")


if __name__ == "__main__":
    main()
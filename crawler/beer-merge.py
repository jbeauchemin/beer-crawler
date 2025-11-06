import json
from pathlib import Path
from typing import List, Dict, Set
from difflib import SequenceMatcher

class BeerMerger:
    def __init__(self, producer_threshold: float = 0.6, name_threshold: float = 0.8):
        """
        Initialise le merger de bières
        
        Args:
            producer_threshold: Seuil de similarité pour producteur
            name_threshold: Seuil de similarité pour nom
        """
        self.producer_threshold = producer_threshold
        self.name_threshold = name_threshold
        self.merged_beers = []
    
    def normalize_text(self, text: str) -> str:
        """Normalise le texte pour la comparaison des producteurs"""
        if not text:
            return ""
        
        text = text.lower()
        
        stop_words = [
            'microbrasserie', 'brasserie', 'inc', 'inc.', 
            'ltée', 'ltd', 'limited', 'brewing', 'brewery',
            'co', 'company', 'the', 'le', 'la', 'les',
            'coopérative', 'de', 'travail', 'brassicole', 'brouërie'
        ]
        
        for char in '.,!?;:()[]{}"\'-–':
            text = text.replace(char, ' ')
        
        words = text.split()
        words = [w for w in words if w not in stop_words]
        
        return ' '.join(words).strip()
    
    def normalize_beer_name(self, text: str) -> str:
        """Normalise le nom de bière"""
        if not text:
            return ""
        
        text = text.lower()
        
        for char in '.,!?;:()[]{}"\'-–':
            text = text.replace(char, ' ')
        
        return ' '.join(text.split()).strip()
    
    def has_variant_keywords(self, name: str) -> Set[str]:
        """Détecte les mots-clés de variantes dans le nom"""
        if not name:
            return set()
        name_lower = name.lower()
        variants = set()
        
        variant_keywords = {
            'lime', 'citron', 'lemon', 'framboise', 'raspberry', 'cerise', 'cherry',
            'mangue', 'mango', 'passion', 'pamplemousse', 'grapefruit',
            'sure', 'sour', 'lactose', 'vanille', 'vanilla', 'chocolat', 'chocolate',
            'café', 'coffee', 'barrel aged', 'vieilli', 'aged', 'nitro',
            'imperial', 'double', 'triple', 'blonde', 'brune', 'rousse', 'noire',
            'blanche', 'wheat', 'wit', 'weizen', 'stout', 'porter',
            'pêche', 'peach', 'abricot', 'apricot', 'orange', 'tangerine'
        }
        
        for keyword in variant_keywords:
            if keyword in name_lower:
                variants.add(keyword)
        
        return variants
    
    def get_package_format(self, beer: Dict) -> str:
        """Détecte le format de packaging"""
        name = (beer.get('name') or '').lower()
        url = (beer.get('url') or '').lower()
        volume = (beer.get('volume') or '').lower()
        
        # Cherche dans le nom, l'URL et le volume
        text = f"{name} {url} {volume}"
        
        # Détecte les packs
        pack_patterns = [
            '4-pack', '4pack', '4 pack',
            '6-pack', '6pack', '6 pack',
            '8-pack', '8pack', '8 pack',
            '12-pack', '12pack', '12 pack',
            'pack de', 'x4', 'x6', 'x8', 'x12',
            'caisse', 'case'
        ]
        
        for pattern in pack_patterns:
            if pattern in text:
                return 'pack'
        
        return 'single'
    
    def is_pack_url(self, url: str) -> bool:
        """Vérifie si une URL concerne un pack"""
        url_lower = url.lower()
        pack_indicators = [
            'pack', 'caisse', 'case',
            'x4', 'x6', 'x8', 'x12',
            '4-pack', '6-pack'
        ]
        return any(indicator in url_lower for indicator in pack_indicators)
    
    def calculate_similarity(self, str1: str, str2: str, for_name: bool = False) -> float:
        """Calcule la similarité entre deux chaînes"""
        if for_name:
            norm1 = self.normalize_beer_name(str1)
            norm2 = self.normalize_beer_name(str2)
        else:
            norm1 = self.normalize_text(str1)
            norm2 = self.normalize_text(str2)
        
        if not norm1 or not norm2:
            return 0.0
        
        if for_name and norm1 in norm2:
            if norm2.startswith(norm1):
                return 1.0
            return 0.95
        
        if norm1 in norm2 or norm2 in norm1:
            return 1.0
        
        base_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        if for_name:
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            
            if words1 and words2:
                word_overlap = len(words1 & words2) / max(len(words1), len(words2))
                return (base_similarity * 0.5) + (word_overlap * 0.5)
        
        return base_similarity
    
    def is_same_beer(self, beer1: Dict, beer2: Dict, ignore_format: bool = False) -> bool:
        """Détermine si deux bières sont identiques"""
        # Compare producteur
        producer1 = beer1.get('producer', '')
        producer2 = beer2.get('producer', '')
        
        if not producer1 or not producer2:
            return False
        
        producer_score = self.calculate_similarity(producer1, producer2, for_name=False)
        if producer_score < self.producer_threshold:
            return False
        
        # Compare nom
        name1 = beer1.get('name', '')
        name2 = beer2.get('name', '')
        
        if not name1 or not name2:
            return False
        
        name_score = self.calculate_similarity(name1, name2, for_name=True)
        if name_score < self.name_threshold:
            return False
        
        # NOUVEAU : Vérifie que les variantes matchent
        variants1 = self.has_variant_keywords(name1)
        variants2 = self.has_variant_keywords(name2)
        
        # Si une bière a des variantes et l'autre non, ce ne sont pas les mêmes
        if variants1 != variants2:
            return False
        
        # NOUVEAU : Vérifie que le format est le même (sauf si on ignore)
        if not ignore_format:
            format1 = self.get_package_format(beer1)
            format2 = self.get_package_format(beer2)
            
            if format1 != format2:
                return False
        
        return True
    
    def choose_best_photo(self, photo_urls: Dict[str, str], package_format: str) -> str:
        """Choisit la meilleure photo selon le format"""
        if not photo_urls:
            return None
        
        # Pour les singles, évite les photos de pack
        if package_format == 'single':
            for source, url in photo_urls.items():
                if url and not self.is_pack_url(url):
                    # Évite aussi les placeholders
                    if 'placeholder' not in url.lower():
                        return url
        
        # Sinon, prend la première disponible (non-placeholder)
        for source, url in photo_urls.items():
            if url and 'placeholder' not in url.lower():
                return url
        
        # En dernier recours, prend n'importe quelle photo
        return list(photo_urls.values())[0]
    
    def merge_beer_data(self, existing: Dict, new_beer: Dict) -> Dict:
        """
        Merge les données de deux bières
        Priorité: garde descriptions, photo_url, style, sub_style de toutes les sources
        """
        merged = existing.copy()
        
        # Ajoute la nouvelle source
        if 'sources' not in merged:
            merged['sources'] = [existing.get('source', 'unknown')]
        
        new_source = new_beer.get('source', 'unknown')
        if new_source not in merged['sources']:
            merged['sources'].append(new_source)
        
        # Détermine les formats
        existing_format = self.get_package_format(existing)
        new_format = self.get_package_format(new_beer)
        
        # Garde toutes les URLs
        if 'urls' not in merged:
            merged['urls'] = []
            if existing.get('url'):
                merged['urls'].append(existing['url'])
        
        if new_beer.get('url') and new_beer['url'] not in merged['urls']:
            merged['urls'].append(new_beer['url'])
        
        # NOUVEAU : Section pack séparée
        if 'pack_info' not in merged:
            merged['pack_info'] = {}
        
        # Si c'est un pack, ajoute les infos pack
        if new_format == 'pack':
            if 'urls' not in merged['pack_info']:
                merged['pack_info']['urls'] = []
            if new_beer.get('url') and new_beer['url'] not in merged['pack_info']['urls']:
                merged['pack_info']['urls'].append(new_beer['url'])
            
            if 'prices' not in merged['pack_info']:
                merged['pack_info']['prices'] = {}
            if new_beer.get('price'):
                merged['pack_info']['prices'][new_source] = new_beer['price']
            
            if 'photo_urls' not in merged['pack_info']:
                merged['pack_info']['photo_urls'] = {}
            if new_beer.get('photo_url'):
                merged['pack_info']['photo_urls'][new_source] = new_beer['photo_url']
            
            if new_beer.get('description'):
                if 'descriptions' not in merged['pack_info']:
                    merged['pack_info']['descriptions'] = {}
                merged['pack_info']['descriptions'][new_source] = new_beer['description']
        
        # Pour les champs simples: prend le premier non-vide (priorité aux singles)
        simple_fields = ['name', 'producer', 'volume', 'alcohol']
        for field in simple_fields:
            if not merged.get(field) and new_beer.get(field):
                # Si c'est un pack, nettoie le nom
                if field == 'name' and new_format == 'pack':
                    clean_name = new_beer[field].replace('(pack)', '').replace('pack', '').strip()
                    if not merged.get(field):
                        merged[field] = clean_name
                else:
                    merged[field] = new_beer[field]
        
        # Prix: garde tous les prix (singles seulement)
        if 'prices' not in merged:
            merged['prices'] = {}
        
        if new_format != 'pack':
            for source in merged['sources']:
                if source == existing.get('source') and existing.get('price'):
                    merged['prices'][source] = existing['price']
                elif source == new_source and new_beer.get('price'):
                    merged['prices'][source] = new_beer['price']
        
        # Descriptions: garde toutes les descriptions uniques (singles prioritaires)
        if 'descriptions' not in merged:
            merged['descriptions'] = {}
        
        if existing.get('description') and existing_format != 'pack':
            merged['descriptions'][existing.get('source', 'unknown')] = existing['description']
        if new_beer.get('description') and new_format != 'pack':
            merged['descriptions'][new_source] = new_beer['description']
        
        # Photos: garde toutes les photos uniques (singles seulement)
        if 'photo_urls' not in merged:
            merged['photo_urls'] = {}
        
        if existing.get('photo_url') and existing_format != 'pack':
            merged['photo_urls'][existing.get('source', 'unknown')] = existing['photo_url']
        
        if new_beer.get('photo_url') and new_format != 'pack':
            merged['photo_urls'][new_source] = new_beer['photo_url']
        
        # Choisit la meilleure photo principale (singles uniquement)
        if merged.get('photo_urls'):
            merged['photo_url'] = self.choose_best_photo(merged['photo_urls'], 'single')
        
        # Styles: garde tous les styles (singles prioritaires)
        if 'styles' not in merged:
            merged['styles'] = {}
        
        if existing.get('style') and existing_format != 'pack':
            merged['styles'][existing.get('source', 'unknown')] = existing['style']
        if new_beer.get('style') and new_format != 'pack':
            merged['styles'][new_source] = new_beer['style']
        
        # Sub-styles: garde tous les sub-styles
        if 'sub_styles' not in merged:
            merged['sub_styles'] = {}
        
        if existing.get('sub_style'):
            merged['sub_styles'][existing.get('source', 'unknown')] = existing['sub_style']
        if new_beer.get('sub_style'):
            merged['sub_styles'][new_source] = new_beer['sub_style']
        
        # Autres champs intéressants
        optional_fields = ['ibu', 'region', 'availability', 'upc']
        for field in optional_fields:
            if new_beer.get(field) and not merged.get(field):
                merged[field] = new_beer[field]
        
        return merged
    
    def merge_beers(self, json_files: List[str]) -> List[Dict]:
        """
        Merge toutes les bières des fichiers JSON
        
        Returns:
            Liste des bières mergées
        """
        all_beers = []
        
        # Charge tous les fichiers
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    source = Path(file_path).stem.replace('beers_', '')
                    
                    for beer in data:
                        beer['source'] = source
                        all_beers.append(beer)
                    
                    print(f"✓ Chargé {len(data)} bières depuis {file_path}")
            except Exception as e:
                print(f"✗ Erreur lors du chargement de {file_path}: {e}")
        
        print(f"\nTotal de bières chargées: {len(all_beers)}")
        print("\n🔄 Début du merge...\n")
        
        # Merge les bières (en ignorant le format pour regrouper packs et singles)
        merged_beers = []
        processed = 0
        merged_count = 0
        
        for beer in all_beers:
            processed += 1
            if processed % 100 == 0:
                print(f"Traité: {processed}/{len(all_beers)} bières...")
            
            # Cherche si la bière existe déjà (ignore le format)
            found = False
            for i, existing in enumerate(merged_beers):
                if self.is_same_beer(beer, existing, ignore_format=True):
                    merged_beers[i] = self.merge_beer_data(existing, beer)
                    found = True
                    merged_count += 1
                    break
            
            # Si pas trouvée, l'ajoute
            if not found:
                merged_beers.append(beer)
        
        print(f"\n✓ Merge terminé!")
        print(f"  - Bières originales: {len(all_beers)}")
        print(f"  - Bières mergées: {len(merged_beers)}")
        print(f"  - Doublons trouvés: {merged_count}")
        
        return merged_beers
    
    def save_merged_beers(self, beers: List[Dict], output_file: str):
        """Sauvegarde les bières mergées dans un fichier JSON"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(beers, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Bières sauvegardées dans: {output_file}")
        except Exception as e:
            print(f"\n✗ Erreur lors de la sauvegarde: {e}")


def main():
    json_files = [
        '../datas/beers_beaudegat.json',
        '../datas/beers_espacehoublon.json',
        '../datas/beers_lbab.json',
        '../datas/beers_masoif.json',
        '../datas/beers_vtub.json'
    ]
    
    print("=== MERGER DE BIÈRES (VERSION AMÉLIORÉE) ===\n")
    
    # Initialise le merger
    merger = BeerMerger(producer_threshold=0.6, name_threshold=0.8)
    
    # Merge les bières
    merged_beers = merger.merge_beers(json_files)
    
    # Sauvegarde le résultat
    output_file = '../datas/beers_merged.json'
    merger.save_merged_beers(merged_beers, output_file)
    
    # Affiche quelques statistiques
    print("\n📊 STATISTIQUES:")
    
    # Compte les bières avec plusieurs sources
    multi_source = [b for b in merged_beers if len(b.get('sources', [])) > 1]
    print(f"  - Bières trouvées sur plusieurs sites: {len(multi_source)}")
    
    # Compte les variantes détectées
    variants = [b for b in merged_beers if merger.has_variant_keywords(b.get('name', ''))]
    print(f"  - Bières avec variantes détectées: {len(variants)}")
    
    # Compte les packs vs singles
    beers_with_packs = [b for b in merged_beers if b.get('pack_info') and b.get('pack_info').get('urls')]
    print(f"  - Bières avec info pack: {len(beers_with_packs)}")
    
    if multi_source:
        print(f"\n  Exemples de bières mergées:")
        for beer in multi_source[:3]:
            print(f"    • {beer.get('name')} ({beer.get('producer')})")
            print(f"      Sources: {', '.join(beer.get('sources', []))}")
            has_pack = beer.get('pack_info') and beer.get('pack_info').get('urls')
            if has_pack:
                print(f"      Pack disponible: Oui ({len(beer['pack_info']['urls'])} liens)")
            variants = merger.has_variant_keywords(beer.get('name', ''))
            if variants:
                print(f"      Variantes: {', '.join(variants)}")


if __name__ == "__main__":
    main()
import json
import re
from pathlib import Path
from typing import Dict, List
import unicodedata


class BeerNameCleaner:
    """
    Nettoie les noms de bières en enlevant le nom du producteur quand il est présent au début
    """

    # Mots courants des noms de brasseries à ignorer lors de la comparaison
    PRODUCER_STOPWORDS = [
        'brasserie', 'microbrasserie', 'artisanal', 'artisanale',
        'brasseurs', 'brasseur', 'inc', 'inc.', 'ltd', 'ltée', 'ltee',
        'compagnie', 'company', 'co', 'co.', 'brewing', 'brewery',
        'microbrewery', 'craft', 'beer', 'biere', 'bières', 'beers',
        'du', 'de', 'la', 'le', 'les', 'des'
    ]

    # Séparateurs courants entre producteur et nom de bière
    SEPARATORS = ['–', '-', '—', ':', '|', '/']

    def __init__(self, dry_run: bool = False):
        """
        Args:
            dry_run: Si True, n'applique pas les changements, juste les affiche
        """
        self.dry_run = dry_run
        self.stats = {
            'total': 0,
            'cleaned': 0,
            'unchanged': 0
        }

    def normalize_text(self, text: str) -> str:
        """Normalise le texte pour la comparaison"""
        if not text:
            return ""

        # Minuscules
        text = text.lower()

        # Enlève les accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

        # Enlève la ponctuation (sauf espaces)
        text = re.sub(r'[^\w\s]', ' ', text)

        # Normalise les espaces
        text = ' '.join(text.split())

        return text.strip()

    def get_significant_tokens(self, text: str) -> List[str]:
        """Extrait les tokens significatifs d'un texte (sans stopwords)"""
        normalized = self.normalize_text(text)
        tokens = normalized.split()

        # Enlève les stopwords
        return [t for t in tokens if t not in self.PRODUCER_STOPWORDS and len(t) > 1]

    def extract_producer_prefix(self, beer_name: str) -> tuple:
        """
        Détecte si le nom de la bière commence par un préfixe séparateur

        Returns:
            (prefix, separator, rest) ou (None, None, original_name)
        """
        # Cherche un séparateur dans le nom
        for sep in self.SEPARATORS:
            if sep in beer_name:
                parts = beer_name.split(sep, 1)
                if len(parts) == 2:
                    prefix = parts[0].strip()
                    rest = parts[1].strip()

                    # Ignore les préfixes trop courts ou trop longs
                    if len(prefix) < 2 or len(prefix) > 50:
                        continue

                    # Ignore si le "reste" est trop court
                    if len(rest) < 2:
                        continue

                    return (prefix, sep, rest)

        return (None, None, beer_name)

    def remove_volume_suffix(self, beer_name: str) -> str:
        """
        Enlève les suffixes de volume comme "- 473ml", "- 355ml", etc.

        Args:
            beer_name: Nom de la bière

        Returns:
            Le nom sans suffixe de volume
        """
        if not beer_name:
            return beer_name

        # Pattern pour détecter les volumes à la fin
        # Exemples: "- 473ml", "- 355 ml", "- 0.5L", "- 500 mL"
        volume_pattern = r'\s*[-–—:]\s*\d+(\.\d+)?\s*(ml|ML|mL|Ml|l|L|litre|litres)\s*$'

        cleaned = re.sub(volume_pattern, '', beer_name, flags=re.IGNORECASE)
        return cleaned.strip()

    def should_clean(self, beer_name: str, producer: str) -> bool:
        """
        Détermine si le nom de la bière devrait être nettoyé

        Args:
            beer_name: Nom de la bière
            producer: Nom du producteur

        Returns:
            True si le nom commence par le producteur
        """
        if not beer_name or not producer:
            return False

        # Extrait le préfixe potentiel
        prefix, sep, rest = self.extract_producer_prefix(beer_name)

        if not prefix:
            return False

        # Compare les tokens significatifs du préfixe et du producteur
        prefix_tokens = set(self.get_significant_tokens(prefix))
        producer_tokens = set(self.get_significant_tokens(producer))

        if not prefix_tokens or not producer_tokens:
            return False

        # Si tous les tokens du préfixe sont dans le producteur, c'est un match
        if prefix_tokens.issubset(producer_tokens):
            return True

        # Si au moins 70% des tokens du préfixe matchent le producteur
        overlap = len(prefix_tokens & producer_tokens)
        ratio = overlap / len(prefix_tokens)

        return ratio >= 0.7

    def clean_beer_name(self, beer: Dict) -> str:
        """
        Nettoie le nom d'une bière en enlevant:
        1. Le nom du producteur au début (si présent)
        2. Le volume à la fin (si présent)

        Args:
            beer: Dictionnaire avec 'name' et 'producer'

        Returns:
            Le nom nettoyé
        """
        original_name = beer.get('name', '')
        producer = beer.get('producer', '')
        cleaned_name = original_name

        # Étape 1: Enlève le préfixe du producteur
        if self.should_clean(cleaned_name, producer):
            # Extrait le préfixe et le reste
            prefix, sep, rest = self.extract_producer_prefix(cleaned_name)

            if prefix and rest:
                cleaned_name = rest

        # Étape 2: Enlève le suffixe de volume
        cleaned_name = self.remove_volume_suffix(cleaned_name)

        return cleaned_name

    def clean_beers(self, beers: List[Dict]) -> List[Dict]:
        """
        Nettoie les noms de toutes les bières

        Args:
            beers: Liste des bières à nettoyer

        Returns:
            Liste des bières avec noms nettoyés
        """
        self.stats['total'] = len(beers)

        print(f"\n🧹 Nettoyage des noms de bières...")
        print(f"   Total de bières: {len(beers)}")
        print(f"   Mode: {'DRY RUN (aperçu seulement)' if self.dry_run else 'MODIFICATION'}\n")

        changes = []

        for i, beer in enumerate(beers):
            original_name = beer.get('name', '')
            cleaned_name = self.clean_beer_name(beer)

            if cleaned_name != original_name:
                self.stats['cleaned'] += 1

                change_info = {
                    'index': i,
                    'producer': beer.get('producer', ''),
                    'original': original_name,
                    'cleaned': cleaned_name,
                    'source': beer.get('source', '')
                }
                changes.append(change_info)

                # Affiche le changement
                print(f"{i+1}. 🔧 {beer.get('producer', 'Unknown')}")
                print(f"   Avant:  {original_name}")
                print(f"   Après:  {cleaned_name}")
                print(f"   Source: {beer.get('source', '')}")
                print()

                # Applique le changement si pas en dry run
                if not self.dry_run:
                    beer['name'] = cleaned_name
            else:
                self.stats['unchanged'] += 1

        return beers

    def print_stats(self):
        """Affiche les statistiques finales"""
        print("\n" + "="*60)
        print("📊 STATISTIQUES")
        print("="*60)
        print(f"Total de bières:         {self.stats['total']}")
        print(f"Noms nettoyés:           {self.stats['cleaned']}")
        print(f"Noms inchangés:          {self.stats['unchanged']}")

        if self.stats['total'] > 0:
            percentage = (self.stats['cleaned'] / self.stats['total']) * 100
            print(f"\nPourcentage nettoyé:     {percentage:.1f}%")

        print("="*60)


def main():
    """Point d'entrée principal du script"""

    import sys

    # Chemins des fichiers
    input_file = Path('../data/beers_merged.json')

    # Essaie aussi dans datas/
    if not input_file.exists():
        input_file = Path('../datas/beers_merged.json')

    if not input_file.exists():
        print("❌ Erreur: Fichier beers_merged.json introuvable!")
        print(f"   Cherché dans: ../data/ et ../datas/")
        return

    output_file = input_file  # Écrase le fichier original
    backup_file = input_file.parent / f"{input_file.stem}_name_backup.json"

    # Vérifie si mode dry-run
    dry_run = '--dry-run' in sys.argv or '--preview' in sys.argv

    print("="*60)
    print("🧹 NETTOYAGE DES NOMS DE BIÈRES")
    print("="*60)
    print(f"Fichier d'entrée:  {input_file}")
    if not dry_run:
        print(f"Fichier de sortie: {output_file}")
        print(f"Fichier de backup: {backup_file}")
    print(f"Mode:              {'DRY RUN (aperçu seulement)' if dry_run else 'MODIFICATION'}")
    print("="*60)

    # Charge les données
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            beers = json.load(f)
        print(f"✓ {len(beers)} bières chargées")
    except Exception as e:
        print(f"❌ Erreur lors du chargement du fichier: {e}")
        return

    # Crée un backup (sauf en dry-run)
    if not dry_run:
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(beers, f, ensure_ascii=False, indent=2)
            print(f"✓ Backup créé: {backup_file}")
        except Exception as e:
            print(f"⚠ Impossible de créer le backup: {e}")

    # Nettoie les noms
    cleaner = BeerNameCleaner(dry_run=dry_run)

    try:
        cleaned_beers = cleaner.clean_beers(beers)

        # Sauvegarde les résultats (sauf en dry-run)
        if not dry_run:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_beers, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Données nettoyées sauvegardées dans: {output_file}")
        else:
            print(f"\n⚠ Mode DRY RUN: Aucune modification appliquée")
            print(f"   Pour appliquer les changements, relancez sans --dry-run")

        # Affiche les statistiques
        cleaner.print_stats()

    except Exception as e:
        print(f"\n❌ Erreur durant le nettoyage: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

# Script d'enrichissement UPC

Ce script enrichit automatiquement vos données de bières avec les codes UPC (Universal Product Code) en utilisant l'API publique de Consignaction.

## 🎯 Objectif

Ajouter le champ `upc` à chaque bière dans votre fichier JSON en faisant des recherches dans la base de données de Consignaction et en trouvant des **matches exacts**.

## 🚀 Utilisation

### Prérequis

- Python 3.6+
- Fichier `beers_merged.json` dans le dossier `data/` ou `datas/`

### Lancer le script

```bash
cd scripts
python upc_enrichment.py
```

Le script va:
1. Charger votre fichier `beers_merged.json`
2. Créer un backup automatique (`beers_merged_backup.json`)
3. Pour chaque bière sans UPC, rechercher dans l'API Consignaction
4. Ajouter le code UPC si un match exact est trouvé
5. Sauvegarder le fichier enrichi

### Tester la logique de matching

Pour tester que la logique de matching fonctionne correctement:

```bash
cd scripts
python test_upc_matching.py
```

## 🔍 Logique de matching

Le script utilise une **logique de match exact** pour éviter les faux positifs:

### Critères de matching

Pour qu'un résultat de l'API soit considéré comme un match:

1. **Producteur** : Le `Maker` de l'API doit correspondre au `producer` de la bière
   - Ignore les mots courants: "Brasserie", "Microbrasserie", "inc.", etc.
   - Au moins 70% des mots doivent matcher

2. **Nom du produit** : Le `product` de l'API doit être **EXACTEMENT** identique au `name` de la bière
   - Normalisation: minuscules, sans ponctuation
   - Pas de mots supplémentaires acceptés

3. **Volume** : Le `volume` de l'API doit correspondre au `volume` de la bière
   - Tolère les différences d'espacement (ex: "473ml" vs "473 ml")

### Exemples

✅ **Match accepté**
```
Bière:  Fardeau (Messorem Bracitorium, 473ml)
API:    Fardeau (Brasserie Messorem Bracitorium inc., 473 ml)
→ UPC: 877951002328
```

❌ **Match rejeté**
```
Bière:  Fardeau (Messorem Bracitorium, 473ml)
API:    Fardeau Xtrm Turbo (Brasserie Messorem Bracitorium inc., 473 ml)
→ Pas de match (mots supplémentaires dans le nom)
```

## ⚙️ Configuration

### Délai entre les requêtes

Par défaut, le script attend 0.5 secondes entre chaque requête pour éviter de surcharger l'API:

```python
enricher = UPCEnricher(delay=0.5)  # 0.5 secondes
```

Vous pouvez ajuster ce délai si nécessaire.

### Reprendre après une interruption

Si le script est interrompu (Ctrl+C), il sauvegarde automatiquement les données partielles. Vous pouvez ensuite modifier le script pour reprendre où vous étiez:

```python
enriched_beers = enricher.enrich_beers(beers, start_index=100)
```

## 📊 Statistiques

À la fin de l'exécution, le script affiche des statistiques détaillées:

```
📊 STATISTIQUES FINALES
Total de bières:           150
Déjà avec UPC:             20
UPC trouvés:               85
UPC non trouvés:           45
Erreurs:                   0

Taux de succès:            65.4%
```

## 🔧 Structure du code

### `UPCEnricher` (classe principale)

- `normalize_text()` : Normalise le texte pour la comparaison
- `normalize_volume()` : Normalise les volumes
- `is_exact_match()` : Vérifie si un résultat API correspond exactement à la bière
- `search_upc()` : Recherche le UPC pour une bière via l'API
- `enrich_beers()` : Enrichit une liste de bières
- `print_stats()` : Affiche les statistiques

## 🛡️ Sécurité

- Le script crée automatiquement un backup avant de modifier les données
- En cas d'erreur ou d'interruption, les données partielles sont sauvegardées
- Aucune donnée n'est supprimée, seulement des UPC sont ajoutés

## 📝 Format des données

### Avant enrichissement
```json
{
  "name": "Fardeau",
  "producer": "Messorem Bracitorium",
  "volume": "473ml",
  ...
}
```

### Après enrichissement
```json
{
  "name": "Fardeau",
  "producer": "Messorem Bracitorium",
  "volume": "473ml",
  "upc": "877951002328",
  ...
}
```

## 🐛 Debugging

Si un UPC n'est pas trouvé, le script affiche des informations de debug:

```
⚠ 2 résultat(s) trouvé(s) mais aucun match exact pour: Fardeau
  1. Fardeau (Brasserie Messorem Bracitorium inc.)
  2. Fardeau Xtrm Turbo (Brasserie Messorem Bracitorium inc.)
```

Cela vous permet de voir pourquoi certains résultats n'ont pas matché.

## 📚 API Consignaction

L'API utilisée est l'API publique de recherche Algolia de Consignaction:

```
https://3mpn6qujk3-dsn.algolia.net/1/indexes/liste_dynamic
```

Paramètres:
- `query` : Terme de recherche (producer + name)
- `hitsPerPage` : Nombre de résultats (50)
- `x-algolia-api-key` : Clé API publique
- `x-algolia-application-id` : ID de l'application

## 🤝 Contribution

Pour améliorer la logique de matching:
1. Modifiez la méthode `is_exact_match()` dans `upc_enrichment.py`
2. Ajoutez des tests dans `test_upc_matching.py`
3. Exécutez les tests pour valider vos modifications

## 📄 Licence

Ce script est fourni tel quel pour faciliter l'enrichissement des données de bières avec les codes UPC.

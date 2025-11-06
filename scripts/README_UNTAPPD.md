# Script d'enrichissement Untappd

Ce script enrichit automatiquement vos données de bières avec les informations provenant d'Untappd via leur API publique Algolia.

## 🎯 Objectif

Ajouter des champs Untappd à chaque bière dans votre fichier JSON:
- `untappd_id`: ID Untappd de la bière
- `untappd_url`: URL de la page Untappd
- `untappd_name`: Nom sur Untappd
- `untappd_brewery`: Nom de la brasserie sur Untappd
- `untappd_style`: Style de bière
- `untappd_abv`: Taux d'alcool
- `untappd_ibu`: IBU (amertume)
- `untappd_rating`: Note moyenne
- `untappd_rating_count`: Nombre de ratings
- `untappd_description`: Description
- `untappd_label`: URL de l'étiquette

## 🚀 Utilisation

### Prérequis

- Python 3.6+
- Librairie `requests`: `pip install requests`
- Fichier `beers_merged.json` dans le dossier `data/` ou `datas/`

### Lancer le script

```bash
cd scripts
python untappd_enrichment.py
```

Le script va:
1. Charger `beers_merged.json` (de `data/` ou `datas/`)
2. Créer un backup automatique (`beers_merged_untappd_backup.json`)
3. Pour chaque bière **sans données Untappd**, rechercher via l'API
4. **Skip automatiquement** les bières qui ont déjà `untappd_id`
5. Ajouter les données Untappd si un match exact est trouvé
6. Sauvegarder le fichier enrichi

**Note**: Les bières qui ont déjà un champ `untappd_id` sont automatiquement ignorées:
```
⏭️  Skipped: Nom de la bière (Untappd ID existant: 123456)
```

### Tester la logique de matching

Pour tester que la logique fonctionne correctement:

```bash
cd scripts
python test_untappd_matching.py
```

## 🔍 Logique de matching

Le script utilise une **logique de match exact** pour éviter les faux positifs:

### Critères de matching

Pour qu'un résultat Untappd soit considéré comme un match:

1. **Nom du produit** : Le `beer_name` doit être **EXACTEMENT** identique au `name` de la bière
   - Normalisation: minuscules, sans accents, sans ponctuation
   - Pas de mots supplémentaires acceptés
   - Le nombre de tokens doit être identique (±1 toléré)

2. **Nom de la brasserie** : Le `brewery_name` doit correspondre au `producer`
   - Ignore les mots courants: "Brasserie", "Microbrasserie", "inc.", etc.
   - Au moins 60% des tokens significatifs doivent matcher

3. **Ratings minimum** : La bière doit avoir au moins 5 ratings sur Untappd
   - Évite les fiches quasi vides ou peu fiables

### Exemples

✅ **Match accepté**
```
Bière:   Fardeau (Messorem Bracitorium)
Untappd: Fardeau (Brasserie Messorem Bracitorium)
→ ID: 123456, Rating: 3.85 (250 ratings)
```

❌ **Match rejeté - variante**
```
Bière:   Fardeau (Messorem Bracitorium)
Untappd: Fardeau Xtrm Turbo (Brasserie Messorem Bracitorium)
→ Pas de match (mots supplémentaires dans le nom)
```

❌ **Match rejeté - mauvais producteur**
```
Bière:   Fardeau (Messorem Bracitorium)
Untappd: Fardeau (Different Brewery)
→ Pas de match (producteur ne correspond pas)
```

## ⚙️ Configuration

### Délai entre les requêtes

Par défaut, le script attend 0.5 secondes entre chaque requête:

```python
enricher = UntappdEnricher(delay=0.5)
```

### Minimum de ratings

Par défaut, le script exige au moins 5 ratings:

```python
enricher = UntappdEnricher(min_ratings=5)
```

Vous pouvez ajuster ces valeurs selon vos besoins.

### Reprendre après une interruption

Si le script est interrompu (Ctrl+C), il sauvegarde automatiquement les données partielles. Vous pouvez reprendre où vous étiez:

```python
enriched_beers = enricher.enrich_beers(beers, start_index=100)
```

## 📊 Statistiques

À la fin de l'exécution, le script affiche des statistiques détaillées:

```
📊 STATISTIQUES FINALES
Total de bières:           150
Déjà avec Untappd:         20
Données trouvées:          85
Non trouvées:              45
Erreurs:                   0

Taux de succès:            65.4%
```

## 🔧 Stratégie de recherche

Le script génère plusieurs candidats de requête pour maximiser les chances de trouver la bière:

1. `{producer} {name}`
2. `{name} {producer}`
3. `{name}` seul

Il teste chaque candidat jusqu'à trouver un match exact.

## 📝 Format des données

### Avant enrichissement
```json
{
  "name": "Fardeau",
  "producer": "Messorem Bracitorium",
  "volume": "473ml",
  "alcohol": "6.2%",
  ...
}
```

### Après enrichissement
```json
{
  "name": "Fardeau",
  "producer": "Messorem Bracitorium",
  "volume": "473ml",
  "alcohol": "6.2%",
  "untappd_id": "123456",
  "untappd_url": "https://untappd.com/b/messorem-bracitorium-fardeau/123456",
  "untappd_name": "Fardeau",
  "untappd_brewery": "Brasserie Messorem Bracitorium",
  "untappd_style": "IPA",
  "untappd_abv": 6.2,
  "untappd_ibu": 45,
  "untappd_rating": 3.85,
  "untappd_rating_count": 250,
  "untappd_description": "Description de la bière...",
  "untappd_label": "https://untappd.akamaized.net/...",
  ...
}
```

## 🐛 Debugging

Si une bière n'est pas trouvée, le script affiche des informations de debug:

```
⚠ 3 résultat(s) trouvé(s) mais aucun match exact
  1. Fardeau (Brasserie Messorem Bracitorium)
  2. Fardeau Xtrm Turbo (Brasserie Messorem Bracitorium)
  3. Fardeau Sour (Autre Brasserie)
```

Cela vous permet de voir pourquoi certains résultats n'ont pas matché.

## 📚 API Untappd (Algolia)

L'API utilisée est l'API publique de recherche Algolia d'Untappd:

```
POST https://9wbo4rq3ho-dsn.algolia.net/1/indexes/beer/query
```

Headers:
- `x-algolia-agent`: Algolia for vanilla JavaScript 3.24.8
- `x-algolia-application-id`: 9WBO4RQ3HO
- `x-algolia-api-key`: 1d347324d67ec472bb7132c66aead485
- `Content-Type`: application/json

Body:
```json
{
  "query": "Messorem Bracitorium Fardeau",
  "hitsPerPage": 12
}
```

## 🛡️ Sécurité

- Le script crée automatiquement un backup avant de modifier les données
- En cas d'erreur ou d'interruption, les données partielles sont sauvegardées
- Aucune donnée n'est supprimée, seulement des champs sont ajoutés

## 🤝 Contribution

Pour améliorer la logique de matching:
1. Modifiez la méthode `is_exact_match()` dans `untappd_enrichment.py`
2. Ajoutez des tests dans `test_untappd_matching.py`
3. Exécutez les tests pour valider vos modifications

## ⚡ Performance

- Délai par défaut: 0.5s entre chaque requête (2 requêtes/seconde)
- Pour 100 bières: ~50 secondes
- Pour 1000 bières: ~8-10 minutes

## 📄 Licence

Ce script est fourni tel quel pour faciliter l'enrichissement des données de bières avec Untappd.

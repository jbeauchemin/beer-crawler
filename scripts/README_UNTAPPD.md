# Scripts d'enrichissement Untappd

## 🔍 Problème résolu

Le script `parallel_enrichment.py` ne complète pas les données manquantes car:

1. **Il skip les bières avec `untappd_id`** sans vérifier si description/style sont null
2. **Selenium ne fonctionne pas bien en parallèle** (10 ChromeDriver = crash/conflits)

## 📋 Scripts disponibles

### 1. `untappd_enrichment.py` - Enrichissement complet (séquentiel)

Pour les **nouvelles bières sans `untappd_id`**:

```bash
cd scripts
python untappd_enrichment.py
```

**Que fait-il?**
- Cherche les bières qui n'ont PAS de `untappd_id`
- Les trouve via l'API Untappd
- Scrape leur page pour description et style
- Ajoute les données dans la structure

**Temps:** ~2-3h pour 1800 bières (API + scraping)

---

### 2. `complete_untappd_missing.py` - Complétion des données manquantes (séquentiel)

**⭐ NOUVEAU - Utilise celui-ci pour compléter les données manquantes!**

Pour les **bières qui ont déjà `untappd_id` mais `untappd_description: null` ou `untappd_style: null`**:

```bash
cd scripts
python complete_untappd_missing.py
```

**Que fait-il?**
- Filtre uniquement les bières avec `untappd_id` mais données manquantes
- Scrape leur page Untappd pour compléter description et/ou style
- Fusionne les données dans `descriptions['untappd']` et `styles['untappd']`
- Normalise les URLs (http → https)

**Temps:** ~12-20 min pour 373 bières (~2 sec/bière)

**Exemple de sortie:**
```
🔍 Recherche des bières à compléter...
   ✓ 373 bières à compléter

📋 Exemples de bières à compléter:
   1. Disco Soleil - Desc:✗ Style:✗
   2. Moralité - Desc:✗ Style:✗
   ...

1/373. 🔄 Disco Soleil
   URL: https://untappd.com/b/_/374544
   📄 Description: A session IPA hopped with Citra hops...
   🎨 Style: IPA - Session

...

📊 STATISTIQUES FINALES
Bières complétées:         373
Descriptions ajoutées:     373
Styles ajoutés:            373
Taux de succès:            100.0%
```

---

### 3. `parallel_enrichment.py` - Recherche parallèle (API seulement)

Pour les **nouvelles bières** en mode rapide (sans scraping):

```bash
cd scripts
python parallel_enrichment.py untappd 10
```

**Que fait-il?**
- Lance 10 workers en parallèle
- Utilise UNIQUEMENT l'API Untappd (pas de scraping)
- Très rapide mais données limitées (pas de description/style)

**⚠️ Limitations:**
- Ne complète PAS les données manquantes
- Skip toutes les bières avec `untappd_id` existant
- Pas de scraping (description et style souvent null)

**Temps:** ~5-10 min pour 1800 bières (API seulement)

---

## 🚀 Workflow recommandé

### Pour enrichir un nouveau dataset complet:

```bash
# 1. Recherche rapide des IDs Untappd (parallèle)
python parallel_enrichment.py untappd 10

# 2. Complète les données manquantes (scraping séquentiel)
python complete_untappd_missing.py
```

### Pour compléter des données existantes avec untappd_id:

```bash
# Complète juste les données manquantes
python complete_untappd_missing.py
```

---

## 🔧 Installation préalable

Avant de lancer ces scripts, installe les dépendances:

```bash
cd scripts

# Test si Selenium fonctionne
python test_selenium_setup.py

# Si erreur, installe les dépendances
pip install -r requirements_scraping.txt
```

Tu devrais voir:
```
✅ Tout est prêt pour le scraping!
```

---

## 📊 Comparaison des scripts

| Script | Vitesse | Données complètes | Cas d'usage |
|--------|---------|-------------------|-------------|
| `parallel_enrichment.py` | ⚡⚡⚡ Très rapide | ❌ Non (API only) | Nouvelles bières, recherche rapide |
| `untappd_enrichment.py` | ⚡ Lent | ✅ Oui (API + scraping) | Nouvelles bières, données complètes |
| `complete_untappd_missing.py` | ⚡⚡ Moyen | ✅ Oui (scraping only) | **Compléter données manquantes** |

---

## 🐛 Dépannage

### "Déjà avec Untappd: 2873, Trouvés: 0"

Tu as utilisé `parallel_enrichment.py` qui skip les bières existantes.

**Solution:** Utilise `complete_untappd_missing.py` à la place.

### "Selenium non disponible"

**Solution:**
```bash
pip install -r requirements_scraping.txt
python test_selenium_setup.py
```

### Le scraping est trop lent

C'est normal! Scraper = 2-3 sec/page.

Pour 373 bières: ~12-20 minutes.

Le script affiche la progression et temps restant.

---

## 📝 Structure des données après enrichissement

Avant:
```json
{
  "name": "Disco Soleil",
  "untappd_id": 374544,
  "untappd_url": "https://untappd.com/b/_/374544",
  "untappd_description": null,
  "untappd_style": null
}
```

Après:
```json
{
  "name": "Disco Soleil",
  "untappd_id": 374544,
  "untappd_url": "https://untappd.com/b/_/374544",
  "untappd_description": "A session IPA hopped with Citra hops...",
  "untappd_style": "IPA - Session",
  "descriptions": {
    "beaudegat": "...",
    "untappd": "A session IPA hopped with Citra hops..."
  },
  "styles": {
    "beaudegat": "HOUBLONNÉE",
    "untappd": "IPA - Session"
  }
}
```

---

## 🔍 Logique de matching (pour untappd_enrichment.py)

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

---

## ⚡ Performance

- **parallel_enrichment.py**: 2 requêtes/sec × 10 workers = ~20 bières/sec
  - Pour 1800 bières: ~5-10 minutes

- **untappd_enrichment.py**: 2 requêtes/sec + 2-3 sec scraping = ~0.5 bière/sec
  - Pour 1800 bières: ~60-90 minutes

- **complete_untappd_missing.py**: ~2-3 sec scraping = ~0.5 bière/sec
  - Pour 373 bières: ~12-20 minutes

---

## 🛡️ Sécurité

- Le script crée automatiquement un backup avant de modifier les données
- En cas d'erreur ou d'interruption, les données partielles sont sauvegardées
- Aucune donnée n'est supprimée, seulement des champs sont ajoutés

---

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

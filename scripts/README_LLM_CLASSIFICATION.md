# LLM Beer Classification avec Mixtral

Ce guide explique comment utiliser les scripts de classification automatique des bières avec un modèle LLM local (Mixtral via Ollama).

## 🎉 Améliorations récentes (v2)

- ✨ **Descriptions plus fun et casual**: Le ton est maintenant comme si tu recommandais une bière à un ami au bar!
- 🎨 **Plus de flavors**: Le système encourage maintenant 2-3 flavors par bière (au lieu de souvent juste 1)
- 🌡️ **Température augmentée**: Plus de créativité dans les descriptions (0.5 au lieu de 0.3)
- 📋 **Exemples dans le prompt**: Le LLM reçoit maintenant des exemples concrets du ton voulu

## 📋 Prérequis

1. **Ollama installé et en marche**
   ```bash
   # Vérifier qu'Ollama est installé
   ollama --version

   # Démarrer Ollama (dans un terminal séparé)
   ollama serve
   ```

2. **Mixtral téléchargé**
   ```bash
   # Vérifier les modèles disponibles
   ollama list

   # Tu devrais voir: mixtral:latest (26 GB)
   ```

3. **Python 3.8+** avec les dépendances
   ```bash
   pip install requests tqdm
   ```

## 🎯 Scripts disponibles

### **classify_beers_with_retry.py** ⭐ RECOMMANDÉ

Script robuste avec retry automatique et format Prisma-ready:
- ✅ Retry automatique (3 tentatives par bière)
- ✅ Progress tracking (reprend où c'était rendu si interrompu)
- ✅ Sauvegarde incrémentale (tous les 10 bières)
- ✅ Format Prisma-ready (prêt pour upsert dans DB)
- ✅ Garde rawData complètes

### **classify_beers_llm.py**

Script simple sans retry (bon pour tester):
- Simple et rapide
- Pas de retry automatique
- Output JSON brut

## 🚀 Utilisation

### Étape 1: Nettoyer les données

Le script `clean_beer_data.py` retire les champs inutiles et prépare les données pour la classification.

```bash
cd /Users/jonathanbeauchemin/Documents/prog/beer-crawler

python scripts/clean_beer_data.py \
  datas/beers_json_perfect_v6.json \
  datas/beers_cleaned.json
```

**Ce que ça fait:**
- ✂️ Retire: price, availability, source, pack_info, etc.
- ✅ Garde: descriptions, styles, urls, photo_urls (pour contexte LLM)
- 🧹 Supprime les anciennes classifications (on repart from scratch)

### Étape 2A: Tester sur quelques bières (RECOMMANDÉ)

Avant de tout classifier, teste sur 20 bières avec le script retry:

```bash
python scripts/classify_beers_with_retry.py \
  datas/beers_cleaned.json \
  datas/beers_prisma_test.json \
  --limit 20
```

**Valide manuellement:**
1. Ouvre `datas/beers_prisma_test.json`
2. Vérifie le format Prisma:
   ```json
   {
     "codeBar": "628055056478",
     "productName": "UAPISHKA",
     "abv": "4.7",
     "alcoholStrength": "LIGHT",
     "bitternessLevel": "LOW",
     "descriptionFr": "Prépare-toi à...",
     "descriptionEn": "Get ready for...",
     "style": {
       "code": "WHEAT_WITBIER",
       "name": "Wheat Beer / Witbier"
     },
     "flavors": [
       { "code": "SPICY_HERBAL", "name": "Spicy / Herbal" },
       { "code": "CITRUS_TROPICAL", "name": "Citrus / Tropical" }
     ],
     "producer": { "name": "St-Pancrace" },
     "rawData": { ... }
   }
   ```
3. Vérifie que les descriptions sont fun et casual!

**Si une bière fail:**
- Le script va automatiquement retry 3 fois
- Si toujours fail, elle sera dans `beers_prisma_test_failed.json`
- Tu peux relancer avec `--resume` pour retry seulement les failed

### Étape 2B: Alternative - Test simple (sans retry)

Pour un test rapide sans retry:

```bash
python scripts/classify_beers_llm.py \
  datas/beers_cleaned.json \
  datas/beers_test_simple.json \
  --limit 20
```

### Étape 3: Classification complète avec retry ⭐

Une fois satisfait des résultats, lance sur toutes les bières avec retry automatique:

```bash
python scripts/classify_beers_with_retry.py \
  datas/beers_cleaned.json \
  datas/beers_prisma_final.json
```

**Temps estimé avec Mixtral:**
- ~4000 bières
- ~30-45 secondes par bière (Mixtral est gourmand mais puissant)
- **Total: ~30-50 heures** 😅
- **Mais:** Sauvegarde tous les 10 bières, peut reprendre si interrompu!

**Features du script:**
- ✅ **Retry automatique**: 3 tentatives par bière
- ✅ **Sauvegarde incrémentale**: Tous les 10 bières
- ✅ **Progress tracking**: Fichier `.progress` pour suivre l'avancement
- ✅ **Reprise**: Si interrompu, lance `--resume` pour continuer

**Si le script est interrompu (Ctrl+C, crash, etc.):**
```bash
# Reprend exactement où c'était rendu!
python scripts/classify_beers_with_retry.py \
  datas/beers_cleaned.json \
  datas/beers_prisma_final.json \
  --resume
```

**Optimisations possibles:**
1. Utiliser un modèle plus petit: `--model mistral:latest` (10x plus rapide, qualité légèrement inférieure)
2. Lancer overnight et laisser tourner

### Étape 4: Validation finale

Échantillonne 100 bières au hasard et vérifie:
- Accuracy du `style_code`
- Pertinence des `flavors`
- Qualité des descriptions FR/EN

## 📊 Format de sortie (Prisma-ready)

Le script `classify_beers_with_retry.py` génère un format compatible avec ton schema Prisma:

```json
{
  "codeBar": "725330860628",
  "productName": "Disco Soleil",
  "abv": "6.5",
  "ibu": null,
  "rating": "3.68073",
  "numRatings": 20837,
  "alcoholStrength": "MEDIUM",
  "bitternessLevel": "MEDIUM",
  "descriptionFr": "Prépare-toi à une explosion d'agrumes! Cette IPA aux kumquats va réveiller tes papilles avec ses notes tropicales et son amertume bien balancée. Parfait pour danser sur tes hits disco préférés!",
  "descriptionEn": "Get ready for a citrus bomb! This kumquat IPA will wake up your taste buds with tropical notes and well-balanced bitterness. Perfect for dancing to your favorite disco hits!",
  "imageUrl": "https://labiereaboire.com/image/cache/catalog/bieres/725330860628-700x825.jpg",

  "style": {
    "code": "IPA",
    "name": "IPA"
  },

  "flavors": [
    { "code": "HOPPY_BITTER", "name": "Hoppy / Bitter" },
    { "code": "CITRUS_TROPICAL", "name": "Citrus / Tropical" }
  ],

  "producer": {
    "name": "Dieu Du Ciel"
  },

  "rawData": {
    // TOUTES les données originales du crawl
    "urls": [...],
    "descriptions": {...},
    "photo_urls": {...},
    "styles": {...},
    ...
  }
}
```

**Ce format est prêt pour:**
- Upsert dans Prisma (via `prisma.beer.upsert()`)
- Import en masse (via `prisma.beer.createMany()`)
- Validation avec ton schema Prisma

## 🎯 Contraintes de classification

### Style Codes (1 seul choix)
- `BLONDE_GOLDEN` - Blonde / Golden Ale
- `WHEAT_WITBIER` - Wheat Beer / Witbier
- `IPA` - IPA
- `PALE_ALE` - Pale Ale
- `RED_AMBER` - Red Ale / Amber
- `LAGER_PILSNER` - Lager / Pilsner
- `SAISON_FARMHOUSE` - Saison / Farmhouse Ale
- `SOUR_TART` - Sour / Tart Beer
- `STOUT_PORTER` - Stout / Porter
- `CIDER` - Cider

### Flavors (1-4 choix)
- `HOPPY_BITTER` - Hoppy / Bitter
- `CITRUS_TROPICAL` - Citrus / Tropical
- `MALTY_GRAINY` - Malty / Grainy
- `CARAMEL_TOFFEE_SWEET` - Caramel / Toffee / Sweet
- `CHOCOLATE_COFFEE` - Chocolate / Coffee
- `RED_FRUITS_BERRIES` - Red Fruits / Berries
- `ORCHARD_FRUITS` - Peach, Pear & Orchard Fruits
- `SPICY_HERBAL` - Spicy / Herbal
- `WOODY_SMOKY` - Woody / Smoky
- `SOUR_TART_FUNKY` - Sour / Tart / Funky

### Bitterness Level
- `LOW`: 0-20 IBU
- `MEDIUM`: 20-40 IBU
- `HIGH`: 40+ IBU

### Alcohol Strength
- `ALCOHOL_FREE`: 0-0.5%
- `LIGHT`: 0.5-5%
- `MEDIUM`: 5-7%
- `STRONG`: 7-15%

## 🔧 Options avancées

### Utiliser un modèle différent

```bash
# Télécharger un modèle plus rapide (mais moins bon)
ollama pull mistral:latest

# Utiliser mistral au lieu de mixtral
python scripts/classify_beers_llm.py \
  datas/beers_cleaned.json \
  datas/beers_classified.json \
  --model mistral:latest
```

### Ajuster la température

Édite `classify_beers_llm.py`, ligne ~140:
```python
temperature: 0.3  # Plus bas = plus déterministe, plus haut = plus créatif
```

### Sauvegarde incrémentale

Le script sauvegarde automatiquement tous les 50 bières dans `output.json`, donc si tu interromps le processus, tu ne perds pas tout!

## ❓ Troubleshooting

### "Cannot connect to Ollama"
```bash
# Assure-toi qu'Ollama tourne
ollama serve
```

### "Model not found"
```bash
# Vérifie tes modèles
ollama list

# Télécharge Mixtral si absent
ollama pull mixtral:latest
```

### Classification trop lente
- Utilise un modèle plus petit: `--model mistral:latest`
- Réduis le contexte dans le prompt (édite le script)
- Considère utiliser l'API OpenAI/Claude (payant mais BEAUCOUP plus rapide)

### Mauvaise qualité de classification
- Ajoute des exemples (few-shot learning) dans le prompt
- Augmente la température pour plus de créativité
- Essaie un modèle plus gros: `ollama pull qwen2.5:32b`

## 📞 Support

Si tu as des questions ou des problèmes, check les logs et le fichier `*_failed.json` pour voir les bières qui n'ont pas pu être classifiées.

Bonne classification! 🍺

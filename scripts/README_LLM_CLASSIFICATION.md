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

### Étape 2: Tester sur quelques bières

Avant de tout classifier, teste sur 10-20 bières pour valider la qualité:

```bash
python scripts/classify_beers_llm.py \
  datas/beers_cleaned.json \
  datas/beers_test_classified.json \
  --limit 20
```

**Valide manuellement:**
1. Ouvre `datas/beers_test_classified.json`
2. Vérifie que `style_code`, `flavors`, `bitterness_level`, `alcohol_strength` sont corrects
3. Lis les `description_fr` et `description_en` - sont-elles friendly et casual?

**Si les résultats ne sont pas bons:**
- Ajuste le prompt dans `classify_beers_llm.py` (fonction `build_classification_prompt`)
- Relance le test
- Itère jusqu'à satisfaction

### Étape 3: Classification complète

Une fois satisfait des résultats, lance sur toutes les bières:

```bash
python scripts/classify_beers_llm.py \
  datas/beers_cleaned.json \
  datas/beers_classified_final.json
```

**Temps estimé avec Mixtral:**
- ~4000 bières
- ~30-45 secondes par bière (Mixtral est gourmand mais puissant)
- **Total: ~30-50 heures** 😅

**Optimisations possibles:**
1. Utiliser un modèle plus petit (mais moins bon)
2. Réduire le contexte dans le prompt
3. Baisser la température (génération plus rapide mais moins créative)

### Étape 4: Validation finale

Échantillonne 100 bières au hasard et vérifie:
- Accuracy du `style_code`
- Pertinence des `flavors`
- Qualité des descriptions FR/EN

## 📊 Format de sortie

Chaque bière aura ces champs ajoutés:

```json
{
  "name": "Disco Soleil",
  "producer": "Dieu Du Ciel",
  "alcohol": "6.5%",
  "volume": "473ml",

  // NOUVEAUX CHAMPS GÉNÉRÉS:
  "style_code": "IPA",
  "flavors": ["HOPPY_BITTER", "CITRUS_TROPICAL", "SOUR_TART_FUNKY"],
  "bitterness_level": "MEDIUM",
  "alcohol_strength": "MEDIUM",
  "abv_normalized": 6.5,
  "ibu_normalized": null,

  "description_fr": "Cette IPA aux kumquats est une explosion d'agrumes et de fraîcheur tropicale. L'amertume se déploie progressivement, balancée par une légère acidité qui te fera saliver jusqu'à la prochaine gorgée. Parfait pour danser sur tes hits disco préférés!",

  "description_en": "This kumquat IPA bursts with citrus and tropical freshness. The bitterness unfolds gradually, balanced by a light acidity that'll have you craving the next sip. Perfect for dancing to your favorite disco hits!",

  // Données originales conservées:
  "urls": [...],
  "descriptions": {...},
  "photo_urls": {...},
  "styles": {...},
  ...
}
```

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

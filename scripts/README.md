# Scripts d'enrichissement de données de bières

Ce dossier contient des scripts pour nettoyer et enrichir vos données de bières.

## 🎯 Vue d'ensemble

| Script | Fonction | Quand l'utiliser |
|--------|----------|------------------|
| `clean_beer_names.py` | Nettoie les noms de bières | **EN PREMIER** - avant tout enrichissement |
| `upc_enrichment.py` | Ajoute les codes UPC | Après nettoyage des noms |
| `untappd_enrichment.py` | Ajoute les données Untappd | Après nettoyage des noms |

## ⚠️ IMPORTANT: Ordre d'exécution

**Vous DEVEZ nettoyer les noms AVANT d'enrichir les données!**

### Pourquoi?

Les noms de bières contiennent souvent des informations superflues qui empêchent le matching:
- `"Blonde de l'Anse (500ml)"` → devrait être `"Blonde de l'Anse"`
- `"Abri de la Tempête - Écume - 473ml"` → devrait être `"Écume"`

Si vous essayez d'enrichir avec des noms sales, le matching échouera:

```
❌ Recherche: "Blonde de l'Anse (500ml)"
   Aucun match trouvé

✅ Recherche: "Blonde de l'Anse"
   UPC trouvé: 123456789
```

## 🚀 Workflow recommandé

### 1. Nettoyage des noms (OBLIGATOIRE)

```bash
cd scripts

# Aperçu des changements
python clean_beer_names.py --dry-run

# Vérifiez que les changements sont corrects

# Appliquez les changements
python clean_beer_names.py
```

Ce script va:
- Enlever les préfixes de producteur: `"Messorem – Fardeau"` → `"Fardeau"`
- Enlever les suffixes de volume: `"Fardeau - 473ml"` → `"Fardeau"`
- Gérer les noms avec tirets: `"Le Saint-Fût - Clé En Main"` → `"Clé En Main"`

### 2. Enrichissement UPC (OPTIONNEL)

```bash
python upc_enrichment.py
```

Ajoute les codes UPC depuis l'API Consignaction.

### 3. Enrichissement Untappd (OPTIONNEL)

```bash
python untappd_enrichment.py
```

Ajoute les données Untappd (ratings, style, ABV, IBU, etc.).

## 📊 Exemple complet

```bash
# Étape 1: Nettoyage (OBLIGATOIRE)
python clean_beer_names.py --dry-run   # Aperçu
python clean_beer_names.py              # Application

# Étape 2: Enrichissement UPC
python upc_enrichment.py

# Étape 3: Enrichissement Untappd
python untappd_enrichment.py
```

## 🔍 Exemples de transformation

### Avant nettoyage
```json
{
  "name": "Abri de la Tempête - Écume - 473ml",
  "producer": "Abri de la Tempête",
  "volume": "473ml"
}
```

### Après nettoyage
```json
{
  "name": "Écume",
  "producer": "Abri de la Tempête",
  "volume": "473ml"
}
```

### Après enrichissement UPC
```json
{
  "name": "Écume",
  "producer": "Abri de la Tempête",
  "volume": "473ml",
  "upc": "123456789012"
}
```

### Après enrichissement Untappd
```json
{
  "name": "Écume",
  "producer": "Abri de la Tempête",
  "volume": "473ml",
  "upc": "123456789012",
  "untappd_id": "987654",
  "untappd_rating": 3.85,
  "untappd_rating_count": 250,
  "untappd_style": "IPA",
  "untappd_abv": 6.2,
  "untappd_ibu": 45,
  ...
}
```

## 🛡️ Sécurité

- Tous les scripts créent un **backup automatique** avant modification
- Mode **dry-run** disponible pour prévisualiser les changements
- Les scripts **n'écrasent jamais** les données existantes (skip automatique)

## 📝 Fichiers de backup

Les scripts créent des backups dans le même dossier que votre fichier JSON:

```
data/
├── beers_merged.json                    # Fichier original/courant
├── beers_merged_name_backup.json        # Backup du nettoyage
├── beers_merged_backup.json             # Backup de l'UPC
└── beers_merged_untappd_backup.json     # Backup d'Untappd
```

## 📚 Documentation détaillée

Chaque script a sa propre documentation:

- [README_CLEAN_NAMES.md](./README_CLEAN_NAMES.md) - Nettoyage des noms
- [README_UPC.md](./README_UPC.md) - Enrichissement UPC
- [README_UNTAPPD.md](./README_UNTAPPD.md) - Enrichissement Untappd

## ⚡ Performance

Pour 1000 bières:

| Script | Durée estimée |
|--------|---------------|
| Nettoyage des noms | ~1 seconde |
| UPC enrichment | ~8-10 minutes (rate limited) |
| Untappd enrichment | ~8-10 minutes (rate limited) |

**Total: ~15-20 minutes** pour enrichir complètement 1000 bières.

## 🐛 Problèmes courants

### ❌ Aucun UPC trouvé

**Cause**: Les noms ne sont pas nettoyés

**Solution**: Lancez `clean_beer_names.py` en premier!

```bash
# Avant nettoyage
Recherche: "Blonde de l'Anse (500ml)"
Résultat: ❌ Aucun match

# Après nettoyage
Recherche: "Blonde de l'Anse"
Résultat: ✅ UPC trouvé
```

### ❌ Matching trop strict

**Cause**: Les variantes de noms

**Solution**: Le matching est intentionnellement strict pour éviter les faux positifs. C'est voulu!

```
Recherche: "Fardeau"
❌ Rejette: "Fardeau Xtrm Turbo" (variante différente)
✅ Accepte: "Fardeau" (match exact)
```

## 🤝 Contribution

Pour améliorer les scripts:

1. Modifiez le script concerné
2. Ajoutez des tests dans le fichier `test_*.py` correspondant
3. Exécutez les tests pour valider
4. Mettez à jour la documentation

## 📄 Licence

Scripts fournis tels quels pour faciliter l'enrichissement des données de bières.

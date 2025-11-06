# Script de nettoyage des noms de bières

Ce script nettoie les noms de bières en enlevant le nom du producteur quand il apparaît au début du nom, suivi d'un séparateur.

## 🎯 Problème

Certains sites incluent des informations superflues dans le nom de la bière:

### Préfixe producteur
- `"Messorem – Not so doomed après tout"` → devrait être `"Not so doomed après tout"`
- `"Bas Canada – Dépression saisonnière"` → devrait être `"Dépression saisonnière"`
- `"Sir John – No Escape"` → devrait être `"No Escape"`

### Suffixe volume
- `"Écume - 473ml"` → devrait être `"Écume"`
- `"IPA - 355 ml"` → devrait être `"IPA"`
- `"Growler - 1L"` → devrait être `"Growler"`

### Les deux combinés
- `"Abri de la Tempête - Écume - 473ml"` → devrait être `"Écume"`

Ce script détecte et corrige automatiquement ces cas.

## 🚀 Utilisation

### Mode aperçu (dry-run)

Pour voir les changements **sans les appliquer**:

```bash
cd scripts
python clean_beer_names.py --dry-run
```

ou

```bash
python clean_beer_names.py --preview
```

### Mode modification

Pour appliquer les changements:

```bash
cd scripts
python clean_beer_names.py
```

Le script va:
1. Charger `beers_merged.json`
2. Créer un backup automatique (`beers_merged_name_backup.json`)
3. Détecter les noms avec préfixe de producteur
4. Nettoyer les noms
5. Sauvegarder le fichier modifié

### Tester la logique

Pour valider que la logique fonctionne correctement:

```bash
cd scripts
python test_beer_name_cleaning.py
```

## 🔍 Logique de détection

Le script effectue deux types de nettoyage:

### 1. Suppression du préfixe producteur

Le script détecte qu'un préfixe doit être enlevé quand:

1. **Présence d'un séparateur**: Le nom contient un séparateur (`–`, `-`, `:`, `|`, `/`)
2. **Match avec le producteur**: Les tokens avant le séparateur correspondent au producteur
3. **Tokens significatifs**: Au moins 70% des tokens significatifs matchent

### 2. Suppression du suffixe volume

Le script enlève automatiquement les suffixes de volume à la fin:

- Pattern détecté: `- XXXml`, `- XXX ml`, `- X.XL`, etc.
- Séparateurs supportés: `-`, `–`, `—`, `:`
- Unités supportées: `ml`, `ML`, `mL`, `l`, `L`, `litre`, `litres`
- Gère les volumes décimaux: `0.5L`, `1.5L`
- **Ne touche pas** les volumes au milieu du nom

### Tokens significatifs

Le script ignore les mots courants lors de la comparaison:
- Mots de brasserie: `brasserie`, `microbrasserie`, `brewery`, `brewing`, etc.
- Articles: `le`, `la`, `les`, `du`, `de`, `des`
- Mots courts (< 2 caractères)

### Exemples

✅ **Nettoyé - Préfixe seul**
```
Nom:        "Messorem – Not so doomed après tout"
Producteur: "Messorem Bracitorium"
Résultat:   "Not so doomed après tout"
```

✅ **Nettoyé - Préfixe seul**
```
Nom:        "Bas Canada – Maréchal"
Producteur: "Brasserie du Bas Canada"
Résultat:   "Maréchal"
```

✅ **Nettoyé - Suffixe seul**
```
Nom:        "Fardeau - 473ml"
Producteur: "Messorem Bracitorium"
Résultat:   "Fardeau"
```

✅ **Nettoyé - Les deux**
```
Nom:        "Abri de la Tempête - Écume - 473ml"
Producteur: "Abri de la Tempête"
Résultat:   "Écume"
```

✅ **Nettoyé avec nom partiel**
```
Nom:        "Dieu – Péché Mortel"
Producteur: "Dieu du Ciel"
Résultat:   "Péché Mortel"
```

❌ **Pas touché** (pas de séparateur)
```
Nom:        "Fardeau"
Producteur: "Messorem Bracitorium"
Résultat:   "Fardeau" (inchangé)
```

❌ **Pas touché** (préfixe ne correspond pas au producteur)
```
Nom:        "La Belle IPA"
Producteur: "Brasserie XYZ"
Résultat:   "La Belle IPA" (inchangé)
```

❌ **Pas touché** (volume au milieu)
```
Nom:        "Édition 473ml Spéciale"
Producteur: "Brasserie ABC"
Résultat:   "Édition 473ml Spéciale" (inchangé)
```

## 🛡️ Sécurité

### Mode aperçu (recommandé)

Lancez **toujours** le script en mode `--dry-run` d'abord pour voir les changements:

```bash
python clean_beer_names.py --dry-run
```

Cela affichera tous les changements qui seraient appliqués sans modifier le fichier.

### Backup automatique

Quand vous lancez le script en mode modification, il crée automatiquement un backup:
```
beers_merged_name_backup.json
```

Vous pouvez restaurer les données originales à tout moment.

### Protection

Le script a des garde-fous:
- Ignore les préfixes trop courts (< 2 caractères)
- Ignore les préfixes trop longs (> 50 caractères)
- Ignore si le reste après nettoyage est trop court (< 2 caractères)
- Ne touche pas aux noms sans séparateur

## 📊 Statistiques

À la fin de l'exécution, le script affiche des statistiques:

```
📊 STATISTIQUES
Total de bières:         1500
Noms nettoyés:           342
Noms inchangés:          1158

Pourcentage nettoyé:     22.8%
```

## 📝 Exemple de sortie

### Mode dry-run

```bash
$ python clean_beer_names.py --dry-run

============================================================
🧹 NETTOYAGE DES NOMS DE BIÈRES
============================================================
Fichier d'entrée:  ../data/beers_merged.json
Mode:              DRY RUN (aperçu seulement)
============================================================
✓ 1500 bières chargées

🧹 Nettoyage des noms de bières...
   Total de bières: 1500
   Mode: DRY RUN (aperçu seulement)

1. 🔧 Messorem Bracitorium
   Avant:  Messorem – Not so doomed après tout
   Après:  Not so doomed après tout
   Source: espacehoublon

2. 🔧 Brasserie du Bas Canada
   Avant:  Bas Canada – Dépression saisonnière
   Après:  Dépression saisonnière
   Source: espacehoublon

...

⚠ Mode DRY RUN: Aucune modification appliquée
   Pour appliquer les changements, relancez sans --dry-run

============================================================
📊 STATISTIQUES
============================================================
Total de bières:         1500
Noms nettoyés:           342
Noms inchangés:          1158

Pourcentage nettoyé:     22.8%
============================================================
```

### Mode modification

```bash
$ python clean_beer_names.py

============================================================
🧹 NETTOYAGE DES NOMS DE BIÈRES
============================================================
Fichier d'entrée:  ../data/beers_merged.json
Fichier de sortie: ../data/beers_merged.json
Fichier de backup: ../data/beers_merged_name_backup.json
Mode:              MODIFICATION
============================================================
✓ 1500 bières chargées
✓ Backup créé: ../data/beers_merged_name_backup.json

...

✓ Données nettoyées sauvegardées dans: ../data/beers_merged.json

============================================================
📊 STATISTIQUES
============================================================
Total de bières:         1500
Noms nettoyés:           342
Noms inchangés:          1158

Pourcentage nettoyé:     22.8%
============================================================
```

## 🔧 Séparateurs supportés

Le script détecte les séparateurs suivants:
- `–` (tiret cadratin)
- `-` (tiret simple)
- `—` (tiret long)
- `:` (deux-points)
- `|` (barre verticale)
- `/` (slash)

## 🧪 Tests

Tous les tests passent avec succès:

```
🧪 TEST DE NETTOYAGE DES NOMS
- 11 tests réussis, 0 tests échoués (incluant préfixe + suffixe combinés)

🧪 TEST DE SUPPRESSION DES SUFFIXES DE VOLUME
- 9 tests réussis, 0 tests échoués

🧪 TEST DE CAS LIMITES
- 5 tests réussis, 0 tests échoués

🧪 TEST DE DÉTECTION
- 4 tests réussis, 0 tests échoués

TOTAL: 29 tests réussis, 0 tests échoués
```

## 📄 Workflow recommandé

1. **Aperçu**: Lancez en mode `--dry-run` pour voir les changements
   ```bash
   python clean_beer_names.py --dry-run
   ```

2. **Validation**: Vérifiez que les changements sont corrects

3. **Application**: Lancez sans `--dry-run` pour appliquer
   ```bash
   python clean_beer_names.py
   ```

4. **Vérification**: Vérifiez le fichier modifié

5. **Restauration** (si nécessaire): Utilisez le backup
   ```bash
   cp ../data/beers_merged_name_backup.json ../data/beers_merged.json
   ```

## 🤝 Contribution

Pour améliorer la logique de détection:
1. Modifiez la méthode `should_clean()` dans `clean_beer_names.py`
2. Ajoutez des tests dans `test_beer_name_cleaning.py`
3. Exécutez les tests pour valider vos modifications

## 📄 Licence

Ce script est fourni tel quel pour faciliter le nettoyage des noms de bières.

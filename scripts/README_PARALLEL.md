# Enrichissement en parallèle

Script pour enrichir les données de bières en utilisant plusieurs workers en parallèle.

## 🚀 Avantage

Au lieu de traiter les bières une par une, le script divise le travail entre plusieurs workers qui tournent **simultanément**.

### Performance

| Méthode | Bières/seconde | Temps pour 1000 bières |
|---------|----------------|------------------------|
| 1 worker (normal) | ~2 bières/sec | ~8-10 minutes |
| 4 workers | ~8 bières/sec | ~2 minutes |
| 8 workers | ~16 bières/sec | ~1 minute |

**Gain de temps: 4-8x plus rapide!** ⚡

## 📋 Prérequis

- MacBook Pro M2 avec 32GB RAM ✅
- Bières déjà nettoyées (avoir lancé `clean_beer_names.py`)

## 🎯 Utilisation

### Syntaxe

```bash
python parallel_enrichment.py <type> [workers]
```

- `<type>`: `upc` ou `untappd`
- `[workers]`: Nombre de workers (optionnel, défaut: 4)

### Exemples

```bash
# UPC avec 4 workers (recommandé)
python parallel_enrichment.py upc 4

# UPC avec 8 workers (plus rapide, mais risque de rate limiting)
python parallel_enrichment.py upc 8

# Untappd avec 6 workers
python parallel_enrichment.py untappd 6
```

## ⚙️ Nombre de workers optimal

### Pour votre M2 MacBook Pro

Le M2 a 8 cores (4 performance + 4 efficiency), donc:

| Workers | Utilisation CPU | Vitesse | Recommandation |
|---------|----------------|---------|----------------|
| 2 | ~25% | Moyen | Trop lent |
| 4 | ~50% | Bon | ✅ **Recommandé** |
| 6 | ~75% | Très bon | ✅ Bon compromis |
| 8 | ~100% | Maximum | ⚠️ Risque rate limiting |
| 10+ | 100%+ | Limité par API | ❌ Pas utile |

**Recommandation: 4-6 workers** pour un bon équilibre vitesse/stabilité.

## 🔒 Rate Limiting

### Attention!

Plus de workers = plus de requêtes API par seconde = risque de blocage!

**Chaque worker attend 0.5s entre les requêtes**, donc:
- 4 workers = ~8 requêtes/sec
- 8 workers = ~16 requêtes/sec

Si vous obtenez des erreurs 429 (Too Many Requests), **réduisez le nombre de workers**.

## 📊 Exemple de sortie

```bash
$ python parallel_enrichment.py upc 4

============================================================
🚀 ENRICHISSEMENT UPC EN PARALLÈLE
============================================================
Fichier d'entrée:  ../data/beers_merged.json
Fichier de sortie: ../data/beers_merged.json
Workers:           4
Délai par worker:  0.5s
============================================================
✓ 4716 bières chargées
✓ Backup créé: ../data/beers_merged_upc_backup.json

📊 Répartition:
   Worker 0: 1179 bières
   Worker 1: 1179 bières
   Worker 2: 1179 bières
   Worker 3: 1179 bières

🚀 Démarrage des 4 workers...

[Worker 0] Démarrage - 1179 bières à traiter
[Worker 1] Démarrage - 1179 bières à traiter
[Worker 2] Démarrage - 1179 bières à traiter
[Worker 3] Démarrage - 1179 bières à traiter
[Worker 0] 🔍 Fardeau (Messorem Bracitorium)
[Worker 1] 🔍 Blanche de Fox (Frontibus)
[Worker 2] 🔍 IPA Américaine (Simple Malt)
[Worker 3] 🔍 Saison (Trou du Diable)
...
[Worker 0] Progression: 10/1179
[Worker 1] Progression: 10/1179
...
[Worker 0] ✓ Terminé - 892 trouvés
[Worker 1] ✓ Terminé - 845 trouvés
[Worker 2] ✓ Terminé - 901 trouvés
[Worker 3] ✓ Terminé - 878 trouvés

📦 Assemblage des résultats...
✓ Sauvegardé: ../data/beers_merged.json

============================================================
📊 STATISTIQUES FINALES
============================================================
Total de bières:        4716
Déjà avec UPC:          200
Trouvés:                3516
Non trouvés:            1000

Temps total:            282.4s (4.7 minutes)
Vitesse:                16.7 bières/sec
Taux de succès:         77.8%
============================================================
```

## 🔧 Comment ça marche

1. **Chargement**: Lit le fichier `beers_merged.json`
2. **Division**: Divise les bières en N chunks (N = nombre de workers)
3. **Distribution**: Chaque worker reçoit un chunk à traiter
4. **Parallélisation**: Tous les workers tournent simultanément
5. **Assemblage**: Les résultats sont fusionnés dans l'ordre
6. **Sauvegarde**: Le fichier final est sauvegardé

## 🛡️ Sécurité

- ✅ Crée un backup automatique avant de commencer
- ✅ Sauvegarde atomique (tout ou rien)
- ✅ Pas de conflits entre workers (chunks séparés)
- ✅ Skip automatique des bières déjà enrichies

## ⚡ Comparaison des méthodes

### Méthode classique (1 worker)

```bash
python upc_enrichment.py
# ⏱️ ~8-10 minutes pour 1000 bières
```

### Méthode parallèle (4 workers)

```bash
python parallel_enrichment.py upc 4
# ⏱️ ~2 minutes pour 1000 bières
# 🚀 4x plus rapide!
```

### Méthode parallèle (8 workers)

```bash
python parallel_enrichment.py upc 8
# ⏱️ ~1 minute pour 1000 bières
# 🚀 8x plus rapide!
# ⚠️ Risque de rate limiting
```

## 💡 Conseils

### Pour maximiser la vitesse

1. **Nettoyez d'abord les noms** avec `clean_beer_names.py`
2. **Utilisez 4-6 workers** pour un bon équilibre
3. **Évitez 8+ workers** (pas de gain réel, risque de blocage)
4. **Fermez les autres apps** pour libérer de la RAM/CPU

### Pour minimiser les erreurs

1. **Commencez avec 4 workers** pour tester
2. **Si ça marche bien**, augmentez à 6
3. **Si erreurs 429**, réduisez à 2-3 workers
4. **Vérifiez votre connexion internet** (stable = mieux)

## 🐛 Troubleshooting

### Erreurs 429 (Too Many Requests)

**Cause**: Trop de workers, l'API bloque

**Solution**: Réduisez le nombre de workers
```bash
python parallel_enrichment.py upc 2
```

### Workers qui plantent

**Cause**: Pas assez de RAM ou CPU surchargé

**Solution**: Fermez d'autres apps, réduisez les workers

### Résultats incomplets

**Cause**: Interruption (Ctrl+C)

**Solution**: Le backup est sauvegardé, vous pouvez réessayer

## 📈 Performance attendue

Pour 4716 bières avec votre M2:

| Workers | Temps estimé | CPU Usage |
|---------|--------------|-----------|
| 1 | ~40 minutes | 12% |
| 2 | ~20 minutes | 25% |
| 4 | ~10 minutes | 50% ✅ |
| 6 | ~7 minutes | 75% ✅ |
| 8 | ~5 minutes | 100% ⚠️ |

**Recommandation: 4-6 workers = sweet spot** 🎯

## 📝 Notes

- Le script utilise `multiprocessing` (vrais processus séparés)
- Chaque worker a son propre délai de 0.5s entre requêtes
- Les stats sont agrégées à la fin
- Le backup est créé AVANT le début du traitement
- La sauvegarde finale est atomique (pas de corruption)

## 🔗 Workflow complet

```bash
# 1. Nettoyage des noms (OBLIGATOIRE)
python clean_beer_names.py

# 2. Enrichissement UPC en parallèle
python parallel_enrichment.py upc 4

# 3. Enrichissement Untappd en parallèle
python parallel_enrichment.py untappd 4
```

**Temps total pour 4716 bières: ~20 minutes** (vs ~80 minutes en série)

## 🎉 Résultat

Avec 4 workers, vous enrichissez vos données **4x plus vite** tout en gardant une bonne stabilité et en évitant le rate limiting! 🚀

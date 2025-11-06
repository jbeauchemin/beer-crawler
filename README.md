# 🍺 Beer Crawler - Récupération de données de bières

Collection de crawlers pour extraire les informations de bières depuis différents sites de microbrasseries québécoises.

## 📋 Table des matières

- [Crawlers spécifiques](#crawlers-spécifiques)
- [Crawler Universel](#-crawler-universel-nouveau)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Scripts utilitaires](#scripts-utilitaires)

---

## Crawlers spécifiques

### Sites supportés

| Site | Fichier | Description |
|------|---------|-------------|
| [Beau de Gat](https://beaudegat.ca) | `beaudegat.py` | Crawl des bières avec style, alcool, volume |
| [Espace Houblon](https://espacehoublon.ca) | `espace-houblon.py` | WooCommerce, filtre produits bière |
| [La Bière à Boire](https://labiereaboire.com) | `labiereaboire.py` | Pagination robuste, UPC |
| [Veux-tu une bière](https://veuxtuunebiere.com) | `vtub.py` | Bières alcoolisées + sans alcool |
| [Ma Soif](https://masoif.com) | `masoif.py` | Données complètes (IBU, région) |

### Caractéristiques communes

✅ Sauvegarde progressive (pas de perte de données)
✅ Gestion de la pagination
✅ Extraction de photos haute résolution
✅ Export en JSON
✅ Gestion des erreurs robuste

---

## 🚀 Crawler Universel (NOUVEAU!)

Le **Universal Beer Crawler** peut crawler **n'importe quel site de microbrasserie** automatiquement, sans configuration !

### ✨ Fonctionnalités

- 🔍 **Détection automatique** de la structure du site
- 🧠 **Adaptation intelligente** à différentes plateformes (Shopify, WooCommerce, WordPress, Custom)
- 📄 **Découverte automatique** des pages de produits et pagination
- 🎯 **Extraction intelligente** des données (nom, prix, alcool, volume, IBU, style, etc.)
- 💾 **Sauvegarde progressive** après chaque produit
- 🔧 **Configuration auto-apprise** sauvegardée pour réutilisation

### 🎬 Utilisation

```bash
# Crawler n'importe quel site de brasserie
python crawler/universal-crawler.py https://dieuduciel.com

# Spécifier le fichier de sortie
python crawler/universal-crawler.py https://autre-brasserie.com beers_custom.json
```

### 📊 Ce qui est extrait automatiquement

| Donnée | Méthodes de détection |
|--------|----------------------|
| **Nom** | `<h1>`, `og:title`, `<title>` |
| **Prix** | Classes "price", `itemprop="price"`, `data-price` |
| **Description** | Classes "description", `itemprop="description"` |
| **Photo** | `og:image`, images de galerie produit |
| **Alcool (%)** | Regex `\d+%` avec validation (0-20%) |
| **Volume (ml)** | Regex `\d+ ml` avec validation (100-5000ml) |
| **IBU** | Regex `\d+ IBU` avec validation (0-150) |
| **Producteur** | Liens catégories, meta brand |
| **Style** | Liens catégories de style/type |

### 🎯 Exemple de sortie

```json
{
  "url": "https://example.com/products/ipa-americaine",
  "name": "IPA Américaine Houblonnée",
  "price": "4,25$",
  "producer": "Dieu du Ciel",
  "style": "IPA",
  "sub_style": "American IPA",
  "volume": "473ml",
  "alcohol": "6.5%",
  "ibu": "65",
  "description": "Une IPA bien houblonnée avec des notes d'agrumes...",
  "photo_url": "https://example.com/images/ipa.jpg"
}
```

### ⚙️ Comment ça fonctionne

1. **Découverte** : Analyse la homepage et trouve les pages de produits
2. **Exploration** : Parcourt les pages de listing et gère la pagination automatiquement
3. **Extraction** : Pour chaque produit, extrait intelligemment toutes les données
4. **Validation** : Valide les données extraites (prix, alcool, volume dans des plages raisonnables)
5. **Sauvegarde** : Enregistre progressivement en JSON

### 📝 Fichiers générés

- `beers_universal.json` : Données des bières extraites
- `product_links_discovered.txt` : Liste de tous les liens de produits trouvés
- `crawler_config.json` : Configuration découverte (plateforme, patterns, sélecteurs)

---

## Installation

### Prérequis

- Python 3.8+
- Google Chrome ou Chromium
- ChromeDriver

### Dépendances Python

```bash
# Créer un environnement virtuel (recommandé)
python3 -m venv env
source env/bin/activate

# Installer les dépendances
pip install selenium beautifulsoup4 requests
```

### Configuration Chrome

Les crawlers utilisent Chrome en mode headless. Assurez-vous que Chrome et ChromeDriver sont installés :

```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# macOS (avec Homebrew)
brew install --cask google-chrome
brew install chromedriver
```

---

## Utilisation

### Crawlers spécifiques

```bash
# Activer l'environnement virtuel
source env/bin/activate

# Exemple : Crawler Beau de Gat
python crawler/beaudegat.py

# Exemple : Crawler Espace Houblon
python crawler/espace-houblon.py
```

### Crawler Universel

```bash
# Crawler n'importe quel site
python crawler/universal-crawler.py https://dieuduciel.com

# Avec fichier de sortie personnalisé
python crawler/universal-crawler.py https://brasserie.com output.json
```

### Analyser un nouveau site

Avant de crawler, vous pouvez analyser la structure du site :

```bash
# Analyse la structure et génère un rapport
python crawler/site-analyzer-lite.py https://nouveau-site.com
```

Cela génère `site_analysis.json` avec :
- Plateforme détectée
- Pages de listing trouvées
- Exemples de produits analysés
- Sélecteurs CSS identifiés

---

## Scripts utilitaires

### 🔀 Fusion de données (`beer-merge.py`)

Fusionne les données de plusieurs sources en détectant les doublons :

```python
from beer_merger import BeerMerger

merger = BeerMerger(producer_threshold=0.6, name_threshold=0.8)
merged_beers = merger.merge_beers([
    'beers_beaudegat.json',
    'beers_espacehoublon.json',
    'beers_lbab.json',
    'beers_masoif.json',
    'beers_vtub.json'
])
merger.save_merged_beers(merged_beers, 'beers_merged.json')
```

**Fonctionnalités** :
- Détection intelligente des doublons (matching flou)
- Gestion des variantes (lime, citron, etc.)
- Séparation packs vs singles
- Conservation de toutes les sources

### 🔍 Recherche de bières (`beer-finder.py`)

Recherche dans les données crawlées :

```python
from beer_finder import BeerFinder

finder = BeerFinder(['beers_merged.json'])
results = finder.search(producer="Dieu du Ciel", name="IPA")
finder.display_results(results)
```

### 🖼️ Traitement d'images (`process_images.py`)

Supprime l'arrière-plan et exporte en WebP :

```bash
python scripts/process_images.py \
  --in images \
  --out out \
  --canvas 900 \
  --pad 40 \
  --shadow \
  --outline 2 \
  --bg transparent
```

---

## Structure du projet

```
beer-crawler/
├── crawler/
│   ├── beaudegat.py              # Crawler Beau de Gat
│   ├── espace-houblon.py         # Crawler Espace Houblon
│   ├── labiereaboire.py          # Crawler La Bière à Boire
│   ├── vtub.py                   # Crawler Veux-tu une bière
│   ├── masoif.py                 # Crawler Ma Soif
│   ├── universal-crawler.py      # 🚀 Crawler Universel
│   ├── site-analyzer-lite.py     # Analyseur de site (sans Selenium)
│   └── beer-merge.py             # Fusion de données
├── scripts/
│   ├── beer-finder.py            # Recherche de bières
│   └── process_images.py         # Traitement d'images
├── README.md                     # Ce fichier
└── .gitignore
```

---

## Format de données

Toutes les bières sont sauvegardées en JSON avec la structure suivante :

```json
{
  "url": "URL du produit",
  "name": "Nom de la bière",
  "price": "Prix (ex: 4,25$)",
  "producer": "Nom du producteur/brasserie",
  "style": "Style principal (ex: IPA)",
  "sub_style": "Sous-style (ex: American IPA)",
  "volume": "Volume (ex: 473ml)",
  "alcohol": "Taux d'alcool (ex: 6.5%)",
  "ibu": "IBU (optionnel)",
  "region": "Région (optionnel)",
  "description": "Description de la bière",
  "photo_url": "URL de la photo",
  "availability": "Disponibilité (optionnel)"
}
```

---

## 🎯 Cas d'usage

### 1. Crawler un nouveau site rapidement

```bash
python crawler/universal-crawler.py https://nouvelle-brasserie.com
```

### 2. Analyser avant de crawler

```bash
# 1. Analyse d'abord
python crawler/site-analyzer-lite.py https://site.com

# 2. Vérifie site_analysis.json

# 3. Crawl avec le crawler universel
python crawler/universal-crawler.py https://site.com
```

### 3. Fusionner plusieurs sources

```bash
# Crawler plusieurs sites
python crawler/universal-crawler.py https://site1.com beers_site1.json
python crawler/universal-crawler.py https://site2.com beers_site2.json

# Fusionner
python crawler/beer-merge.py  # (ajuster les chemins dans le script)
```

---

## Conseils et bonnes pratiques

### 🕐 Respect des sites

- **Delay** : Les crawlers incluent des pauses (1-2s) entre les requêtes
- **Headers** : User-Agent réaliste pour éviter les blocages
- **Rate limiting** : Ne pas surcharger les serveurs

### 🐛 Debugging

Si le crawler ne trouve pas de données :

1. Vérifier que le site est accessible
2. Analyser avec `site-analyzer-lite.py`
3. Vérifier les logs pour identifier les problèmes
4. Ajuster les sélecteurs si nécessaire (mode non-headless pour voir le navigateur)

### 💾 Sauvegarde progressive

Tous les crawlers sauvegardent après chaque produit :
- Pas de perte de données en cas d'interruption
- Possibilité de reprendre où on s'est arrêté

---

## 🤝 Contribution

Pour ajouter un nouveau site spécifique :

1. Créer un nouveau fichier `crawler/nouveau-site.py`
2. S'inspirer de la structure des crawlers existants
3. Tester avec le crawler universel d'abord !

---

## 📜 Licence

Usage personnel et éducatif. Respectez les conditions d'utilisation des sites crawlés.

---

## 🆘 Support

Pour des questions ou problèmes :
1. Vérifier que toutes les dépendances sont installées
2. Tester avec le crawler universel
3. Consulter les logs d'erreur
4. Vérifier que Chrome/ChromeDriver fonctionne

---

**Fait avec 🍺 pour les amateurs de bières artisanales québécoises !**

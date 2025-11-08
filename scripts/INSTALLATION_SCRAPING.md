# Installation du Scraping Untappd

## 🔍 Problème identifié

Le script ne scrapait rien car **Selenium n'était pas correctement initialisé**.

Quand vous avez lancé le script, vous n'avez pas vu le message:
```
✓ Selenium activé pour récupération complète des données
```

Cela signifie que ChromeDriver n'était pas disponible, donc `self.use_selenium` était à `False`, et le code de scraping n'a jamais été exécuté.

## ✅ Solution

### Option 1: Installation automatique (RECOMMANDÉ)

Cette méthode utilise `webdriver-manager` qui télécharge automatiquement ChromeDriver pour vous.

```bash
cd scripts
pip install -r requirements_scraping.txt
```

### Option 2: Installation manuelle

Si l'option 1 ne fonctionne pas:

#### Sur Linux/Ubuntu:
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver
pip install selenium beautifulsoup4
```

#### Sur macOS:
```bash
brew install chromedriver
pip install selenium beautifulsoup4 webdriver-manager
```

#### Sur Windows:
1. Téléchargez ChromeDriver: https://chromedriver.chromium.org/
2. Ajoutez-le au PATH système
3. Installez les dépendances Python:
```cmd
pip install selenium beautifulsoup4 webdriver-manager
```

## 🧪 Tester l'installation

Avant de relancer le script complet, testez que Selenium fonctionne:

```bash
cd scripts
python test_selenium_setup.py
```

Vous devriez voir:
```
✅ Tout est prêt pour le scraping!
```

## 🚀 Lancer le script

Une fois l'installation terminée:

```bash
cd scripts
python untappd_enrichment.py
```

### Messages attendus au démarrage:

Si tout est correct, vous devriez voir:
```
✓ Selenium activé avec webdriver-manager pour récupération complète des données
```

Ou:
```
✓ Selenium activé pour récupération complète des données
```

### Messages pendant l'exécution:

Pour les bières qui ont déjà un `untappd_id` mais manquent de description/style:
```
🔄 Complétion des données Untappd pour: Disco Soleil
    🔍 Scraping de la page pour données manquantes...
    📄 Description ajoutée: A session IPA hopped with Citra hops...
    🎨 Style ajouté: IPA - Session
```

### Statistiques finales attendues:

```
📊 STATISTIQUES FINALES
Total de bières:           4716
Déjà avec Untappd:         2500  (qui ont déjà description ET style)
Données trouvées:          100   (nouvelles bières enrichies)
Données complétées:        373   (bières avec données manquantes complétées)
Non trouvées:              1843
Pages scrapées:            473   (API + completion)
Taux de succès:            XX.X%
```

## 🐛 Dépannage

### Erreur: "chromedriver not found"
- Installez `webdriver-manager`: `pip install webdriver-manager`
- Ou installez ChromeDriver manuellement pour votre OS

### Erreur: "Message: session not created"
- Vérifiez que Chrome/Chromium est installé
- Mettez à jour Chrome à la dernière version
- Réinstallez webdriver-manager: `pip uninstall webdriver-manager && pip install webdriver-manager`

### Le script dit "Selenium activé" mais ne scrape rien
- Vérifiez que les bières ont bien un `untappd_url` dans le JSON
- Vérifiez que les bières manquent soit `untappd_description` soit `untappd_style`

### Le script est trop lent
- C'est normal! Le scraping prend ~2-3 secondes par page
- Pour 373 bières à compléter: ~12-18 minutes
- Le script affiche la progression tous les 10 items

## 📊 Résultats attendus

Après exécution, chaque bière devrait avoir:

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
    "beaudegat": "IPA",
    "untappd": "IPA - Session"
  }
}
```

## 📝 Notes importantes

1. **Backup automatique**: Le script crée un backup avant de modifier les données
2. **Données existantes préservées**: Seules les données manquantes sont ajoutées
3. **Normalisation des URLs**: Toutes les URLs `http://` sont converties en `https://`
4. **Structure unifiée**: Les données Untappd sont fusionnées dans `descriptions['untappd']` et `styles['untappd']`

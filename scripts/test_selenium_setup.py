#!/usr/bin/env python3
"""
Test si Selenium et ChromeDriver sont correctement installés
"""

import sys

print("="*60)
print("🔍 DIAGNOSTIC SELENIUM")
print("="*60)

# Test 1: Import Selenium
print("\n1. Test import Selenium...")
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    print("   ✓ Selenium importé avec succès")
    selenium_ok = True
except ImportError as e:
    print(f"   ✗ Selenium non installé: {e}")
    print("   → Installez avec: pip install selenium")
    selenium_ok = False

# Test 2: Import BeautifulSoup
print("\n2. Test import BeautifulSoup...")
try:
    from bs4 import BeautifulSoup
    print("   ✓ BeautifulSoup4 importé avec succès")
    bs4_ok = True
except ImportError as e:
    print(f"   ✗ BeautifulSoup4 non installé: {e}")
    print("   → Installez avec: pip install beautifulsoup4")
    bs4_ok = False

# Test 3: Initialisation ChromeDriver
if selenium_ok:
    print("\n3. Test initialisation ChromeDriver...")
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        driver = webdriver.Chrome(options=chrome_options)
        driver.quit()
        print("   ✓ ChromeDriver initialisé avec succès")
        chrome_ok = True
    except Exception as e:
        print(f"   ✗ Erreur ChromeDriver: {e}")
        print("\n   SOLUTIONS POSSIBLES:")
        print("   1. Installez Chrome/Chromium:")
        print("      - Linux: sudo apt-get install chromium-browser chromium-chromedriver")
        print("      - Mac: brew install chromedriver")
        print("      - Windows: Téléchargez ChromeDriver depuis https://chromedriver.chromium.org/")
        print("\n   2. Ou utilisez webdriver-manager:")
        print("      pip install webdriver-manager")
        chrome_ok = False
else:
    chrome_ok = False

# Résumé
print("\n" + "="*60)
print("📊 RÉSUMÉ")
print("="*60)
print(f"Selenium:        {'✓ OK' if selenium_ok else '✗ MANQUANT'}")
print(f"BeautifulSoup4:  {'✓ OK' if bs4_ok else '✗ MANQUANT'}")
print(f"ChromeDriver:    {'✓ OK' if chrome_ok else '✗ MANQUANT'}")

if selenium_ok and bs4_ok and chrome_ok:
    print("\n✅ Tout est prêt pour le scraping!")
else:
    print("\n⚠️  Des dépendances sont manquantes.")
    print("\nCOMMANDES D'INSTALLATION:")
    if not selenium_ok or not bs4_ok:
        print("  pip install selenium beautifulsoup4")
    if not chrome_ok:
        print("  # Voir les solutions ChromeDriver ci-dessus")

print("="*60)

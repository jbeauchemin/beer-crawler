#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pour vérifier que l'environnement est correctement configuré
"""

import sys
import subprocess

def check_python():
    """Vérifie la version de Python"""
    version = sys.version_info
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("   ⚠️  Python 3.8+ recommandé")
        return False
    return True

def check_module(module_name, install_cmd=None):
    """Vérifie qu'un module est installé"""
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
        return True
    except ImportError:
        print(f"❌ {module_name} - NON INSTALLÉ")
        if install_cmd:
            print(f"   Installation: {install_cmd}")
        return False

def check_chrome():
    """Vérifie que Chrome est installé"""
    chrome_paths = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',  # macOS
        'google-chrome',  # Linux
        'chrome',  # Windows
    ]

    for path in chrome_paths:
        try:
            result = subprocess.run([path, '--version'],
                                   capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ Chrome installé: {version}")
                return True
        except:
            continue

    print("❌ Chrome - NON TROUVÉ")
    print("   Installation:")
    print("   - macOS: brew install --cask google-chrome")
    print("   - Linux: sudo apt install google-chrome-stable")
    print("   - Windows: https://www.google.com/chrome/")
    return False

def main():
    print("="*60)
    print("🔍 VÉRIFICATION DE L'ENVIRONNEMENT BEER-CRAWLER")
    print("="*60)

    all_ok = True

    print("\n📦 Python:")
    all_ok &= check_python()

    print("\n📚 Modules Python:")
    modules = [
        ('selenium', 'pip install selenium'),
        ('bs4', 'pip install beautifulsoup4'),
        ('webdriver_manager', 'pip install webdriver-manager'),
    ]

    for module, install_cmd in modules:
        all_ok &= check_module(module, install_cmd)

    print("\n🌐 Navigateur:")
    all_ok &= check_chrome()

    print("\n" + "="*60)
    if all_ok:
        print("✅ TOUT EST OK ! Vous pouvez utiliser le crawler.")
        print("\nUsage:")
        print("  python crawler/universal-crawler.py https://dieuduciel.com")
    else:
        print("⚠️  CONFIGURATION INCOMPLÈTE")
        print("\n🔧 INSTALLATION RAPIDE:")
        print("\n# 1. Installer les dépendances Python")
        print("pip install selenium beautifulsoup4 webdriver-manager")
        print("\n# 2. Installer Chrome (si pas déjà fait)")
        print("# macOS:")
        print("brew install --cask google-chrome")
        print("\n# Linux:")
        print("sudo apt install google-chrome-stable")
        print("\n# 3. Tester à nouveau")
        print("python check-setup.py")
    print("="*60)

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())

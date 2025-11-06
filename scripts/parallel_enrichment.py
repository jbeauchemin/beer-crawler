import json
import multiprocessing as mp
from pathlib import Path
from typing import List, Dict
import time


def enrich_chunk(args):
    """
    Enrichit un chunk de bières (appelé par chaque worker)

    Args:
        args: tuple (beers_chunk, chunk_id, script_type, delay)
    """
    beers_chunk, chunk_id, script_type, delay = args

    # Import le bon enricher
    if script_type == 'upc':
        from upc_enrichment import UPCEnricher
        enricher = UPCEnricher(delay=delay)
    elif script_type == 'untappd':
        from untappd_enrichment import UntappdEnricher
        enricher = UntappdEnricher(delay=delay)
    else:
        raise ValueError(f"Unknown script type: {script_type}")

    print(f"[Worker {chunk_id}] Démarrage - {len(beers_chunk)} bières à traiter")

    # Enrichit le chunk
    enriched = []
    for i, beer in enumerate(beers_chunk):
        # Skip si déjà enrichi
        if script_type == 'upc' and beer.get('upc'):
            enricher.stats['already_has_upc'] += 1
            enriched.append(beer)
            continue
        elif script_type == 'untappd' and beer.get('untappd_id'):
            enricher.stats['already_has_untappd'] += 1
            enriched.append(beer)
            continue

        # Affiche la progression tous les 10 items
        if i % 10 == 0 and i > 0:
            print(f"[Worker {chunk_id}] Progression: {i}/{len(beers_chunk)}")

        # Enrichit la bière
        if script_type == 'upc':
            print(f"[Worker {chunk_id}] 🔍 {beer.get('name')} ({beer.get('producer')})")
            upc = enricher.search_upc(beer)
            if upc:
                beer['upc'] = upc
                enricher.stats['found'] += 1
            else:
                enricher.stats['not_found'] += 1
        else:  # untappd
            print(f"[Worker {chunk_id}] 🔍 {beer.get('name')} ({beer.get('producer')})")
            data = enricher.search_untappd(beer)
            if data:
                beer.update(data)
                enricher.stats['found'] += 1
            else:
                enricher.stats['not_found'] += 1

        enriched.append(beer)
        time.sleep(delay)

    print(f"[Worker {chunk_id}] ✓ Terminé - {enricher.stats['found']} trouvés")

    return {
        'chunk_id': chunk_id,
        'beers': enriched,
        'stats': enricher.stats
    }


def parallel_enrich(script_type: str, num_workers: int = 4):
    """
    Lance l'enrichissement en parallèle

    Args:
        script_type: 'upc' ou 'untappd'
        num_workers: Nombre de workers parallèles (défaut: 4)
    """

    # Chemins des fichiers
    input_file = Path('../data/beers_merged.json')
    if not input_file.exists():
        input_file = Path('../datas/beers_merged.json')

    if not input_file.exists():
        print("❌ Erreur: Fichier beers_merged.json introuvable!")
        return

    output_file = input_file
    backup_file = input_file.parent / f"{input_file.stem}_{script_type}_backup.json"

    print("="*60)
    print(f"🚀 ENRICHISSEMENT {script_type.upper()} EN PARALLÈLE")
    print("="*60)
    print(f"Fichier d'entrée:  {input_file}")
    print(f"Fichier de sortie: {output_file}")
    print(f"Workers:           {num_workers}")
    print(f"Délai par worker:  0.5s")
    print("="*60)

    # Charge les données
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            beers = json.load(f)
        print(f"✓ {len(beers)} bières chargées")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return

    # Crée le backup
    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(beers, f, ensure_ascii=False, indent=2)
        print(f"✓ Backup créé: {backup_file}")
    except Exception as e:
        print(f"⚠ Backup impossible: {e}")

    # Divise en chunks
    chunk_size = len(beers) // num_workers
    chunks = []

    for i in range(num_workers):
        start = i * chunk_size
        end = start + chunk_size if i < num_workers - 1 else len(beers)
        chunk = beers[start:end]
        chunks.append((chunk, i, script_type, 0.5))

    print(f"\n📊 Répartition:")
    for i, (chunk, _, _, _) in enumerate(chunks):
        print(f"   Worker {i}: {len(chunk)} bières")

    print(f"\n🚀 Démarrage des {num_workers} workers...\n")

    # Lance les workers en parallèle
    start_time = time.time()

    with mp.Pool(processes=num_workers) as pool:
        results = pool.map(enrich_chunk, chunks)

    elapsed = time.time() - start_time

    # Reconstitue les données
    print(f"\n📦 Assemblage des résultats...")

    enriched_beers = []
    total_stats = {
        'found': 0,
        'not_found': 0,
        'already_has_upc': 0 if script_type == 'upc' else 0,
        'already_has_untappd': 0 if script_type == 'untappd' else 0
    }

    for result in sorted(results, key=lambda x: x['chunk_id']):
        enriched_beers.extend(result['beers'])
        total_stats['found'] += result['stats']['found']
        total_stats['not_found'] += result['stats']['not_found']
        if script_type == 'upc':
            total_stats['already_has_upc'] += result['stats'].get('already_has_upc', 0)
        else:
            total_stats['already_has_untappd'] += result['stats'].get('already_has_untappd', 0)

    # Sauvegarde
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_beers, f, ensure_ascii=False, indent=2)
        print(f"✓ Sauvegardé: {output_file}")
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return

    # Statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES FINALES")
    print("="*60)
    print(f"Total de bières:        {len(beers)}")

    if script_type == 'upc':
        print(f"Déjà avec UPC:          {total_stats['already_has_upc']}")
    else:
        print(f"Déjà avec Untappd:      {total_stats['already_has_untappd']}")

    print(f"Trouvés:                {total_stats['found']}")
    print(f"Non trouvés:            {total_stats['not_found']}")
    print(f"\nTemps total:            {elapsed:.1f}s")
    print(f"Vitesse:                {len(beers)/elapsed:.1f} bières/sec")

    to_process = len(beers) - (total_stats.get('already_has_upc', 0) or total_stats.get('already_has_untappd', 0))
    if to_process > 0:
        success_rate = (total_stats['found'] / to_process) * 100
        print(f"Taux de succès:         {success_rate:.1f}%")

    print("="*60)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python parallel_enrichment.py upc [workers]")
        print("  python parallel_enrichment.py untappd [workers]")
        print()
        print("Exemples:")
        print("  python parallel_enrichment.py upc 4        # 4 workers pour UPC")
        print("  python parallel_enrichment.py untappd 8    # 8 workers pour Untappd")
        print()
        print("Recommandations:")
        print("  M1/M2 MacBook: 4-8 workers")
        print("  Plus de workers = plus rapide, mais attention au rate limiting!")
        sys.exit(1)

    script_type = sys.argv[1].lower()

    if script_type not in ['upc', 'untappd']:
        print(f"❌ Type invalide: {script_type}")
        print("   Types valides: upc, untappd")
        sys.exit(1)

    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    if num_workers < 1 or num_workers > 16:
        print(f"❌ Nombre de workers invalide: {num_workers}")
        print("   Recommandé: 4-8 workers")
        sys.exit(1)

    print(f"\n⚡ Mode parallèle: {num_workers} workers\n")

    parallel_enrich(script_type, num_workers)


if __name__ == "__main__":
    main()

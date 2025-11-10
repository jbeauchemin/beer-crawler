    # Afficher un exemple
    # source env/bin/activate

    jonathanbeauchemin@MB-CAMTL-BEAUJs-MacBook-Pro beer-crawler % python scripts/classify_beers_parallel.py \
    datas/beers_cleaned.json \
    datas/beers_classified.json \
    --workers 2 --resume

    ollama serve
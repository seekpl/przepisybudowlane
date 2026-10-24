# PostgreSQL 16 ze słownikiem Hunspell pl_PL dla wyszukiwarki (arkusz, działanie 5.2).
# Słownik (sjp.pl, licencja GPL/LGPL/MPL) pobieramy przy budowie obrazu z rejestru npm — nie leży w repozytorium.
FROM postgres:16

ARG DICTIONARY_PL=2.0.0
ADD https://registry.npmjs.org/dictionary-pl/-/dictionary-pl-${DICTIONARY_PL}.tgz /tmp/dictionary-pl.tgz
RUN set -eux; \
    mkdir /tmp/dict; \
    tar xzf /tmp/dictionary-pl.tgz -C /tmp/dict; \
    cp /tmp/dict/package/index.aff "$(pg_config --sharedir)/tsearch_data/pl_pl.affix"; \
    cp /tmp/dict/package/index.dic "$(pg_config --sharedir)/tsearch_data/pl_pl.dict"; \
    rm -rf /tmp/dict /tmp/dictionary-pl.tgz

# Konfiguracja „pl_hunspell” w szablonie i w bazie startowej — każda nowa baza ją dziedziczy.
COPY hunspell.sql /docker-entrypoint-initdb.d/10-hunspell.sql

-- Konfiguracja wyszukiwania pełnotekstowego ze słownikiem Hunspell pl_PL (używa jej wariant „hunspell”).
-- Skrypt startuje połączony z bazą POSTGRES_DB; potem to samo w template1, żeby dziedziczyły je nowe bazy.
CREATE TEXT SEARCH DICTIONARY pl_ispell (TEMPLATE = ispell, DictFile = pl_pl, AffFile = pl_pl);
CREATE TEXT SEARCH CONFIGURATION pl_hunspell (COPY = simple);
ALTER TEXT SEARCH CONFIGURATION pl_hunspell
  ALTER MAPPING FOR asciiword, word, hword, hword_part, hword_asciipart, asciihword WITH pl_ispell, simple;

\c template1
CREATE TEXT SEARCH DICTIONARY pl_ispell (TEMPLATE = ispell, DictFile = pl_pl, AffFile = pl_pl);
CREATE TEXT SEARCH CONFIGURATION pl_hunspell (COPY = simple);
ALTER TEXT SEARCH CONFIGURATION pl_hunspell
  ALTER MAPPING FOR asciiword, word, hword, hword_part, hword_asciipart, asciihword WITH pl_ispell, simple;

-- Kinoandmebaasi kontrollpäringud pärast migratsioone ja seederit.
-- Käivitamine (vt README):
--   docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /scripts/kontroll.sql'
\pset footer off

\echo '== 1. Tabelid ja ridade arv'
SELECT 'user' AS tabel, count(*) AS ridu FROM "user"
UNION ALL SELECT 'kino', count(*) FROM kino
UNION ALL SELECT 'kinosaalid', count(*) FROM kinosaalid
UNION ALL SELECT 'istekohad', count(*) FROM istekohad
UNION ALL SELECT 'žanrid', count(*) FROM "žanrid"
UNION ALL SELECT 'filmid', count(*) FROM filmid
UNION ALL SELECT 'filmid_zanrid', count(*) FROM filmid_zanrid
UNION ALL SELECT 'seansid', count(*) FROM seansid
UNION ALL SELECT 'broneeringud', count(*) FROM broneeringud
UNION ALL SELECT 'broneeritud_kohad', count(*) FROM broneeritud_kohad
UNION ALL SELECT 'maksed', count(*) FROM maksed
UNION ALL SELECT 'arvustused', count(*) FROM arvustused;

\echo '== 2. Suured tabelid (nõue: vähemalt 100 rida)'
SELECT tabel, ridu, CASE WHEN ridu >= 100 THEN 'OK' ELSE 'VIGA' END AS tulemus
FROM (
    SELECT 'seansid' AS tabel, count(*) AS ridu FROM seansid
    UNION ALL SELECT 'broneeringud', count(*) FROM broneeringud
    UNION ALL SELECT 'broneeritud_kohad', count(*) FROM broneeritud_kohad
    UNION ALL SELECT 'maksed', count(*) FROM maksed
    UNION ALL SELECT 'arvustused', count(*) FROM arvustused
) t;

\echo '== 3. Võõrvõtmed (FOREIGN KEY) andmebaasis'
SELECT tc.table_name AS tabel, kcu.column_name AS veerg, ccu.table_name AS viitab_tabelile
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON kcu.constraint_name = tc.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('kinosaalid', 'istekohad', 'filmid_zanrid', 'seansid', 'broneeringud',
                        'broneeritud_kohad', 'maksed', 'arvustused')
ORDER BY 1, 2;

\echo '== 4. Terviklikkuse kontrollid (iga "vigu" peab olema 0)'
SELECT kontroll, vigu, CASE WHEN vigu = 0 THEN 'OK' ELSE 'VIGA' END AS tulemus FROM (
    SELECT 'orvuks jäänud piletid (broneering puudub)' AS kontroll, count(*) AS vigu
    FROM broneeritud_kohad bk LEFT JOIN broneeringud b ON b.id = bk.broneeringu_id WHERE b.id IS NULL
    UNION ALL
    SELECT 'orvuks jäänud seansid (film või saal puudub)', count(*)
    FROM seansid s LEFT JOIN filmid f ON f.id = s.filmi_id LEFT JOIN kinosaalid k ON k.id = s.saali_id
    WHERE f.id IS NULL OR k.id IS NULL
    UNION ALL
    SELECT 'pileti seanss erineb broneeringu seansist', count(*)
    FROM broneeritud_kohad bk JOIN broneeringud b ON b.id = bk.broneeringu_id WHERE b.seansi_id <> bk.seansi_id
    UNION ALL
    SELECT 'istekoht pole seansi saalis', count(*)
    FROM broneeritud_kohad bk JOIN seansid s ON s.id = bk.seansi_id JOIN istekohad i ON i.id = bk.istekoha_id
    WHERE i.kinosaal_id <> s.saali_id
    UNION ALL
    SELECT 'sama koht müüdud samal seansil mitu korda', count(*)
    FROM (SELECT seansi_id, istekoha_id FROM broneeritud_kohad GROUP BY 1, 2 HAVING count(*) > 1) d
    UNION ALL
    SELECT 'kattuvad seansid samas saalis', count(*)
    FROM seansid a JOIN seansid b ON a.saali_id = b.saali_id AND a.id < b.id
     AND a.algus_aeg < b.lopu_aeg AND b.algus_aeg < a.lopu_aeg
    UNION ALL
    SELECT 'broneeringu summa ≠ piletite summa', count(*)
    FROM broneeringud b
    WHERE b.kogusumma <> (SELECT coalesce(sum(hind), 0) FROM broneeritud_kohad WHERE broneeringu_id = b.id)
    UNION ALL
    SELECT 'broneering tehtud pärast seansi algust', count(*)
    FROM broneeringud b JOIN seansid s ON s.id = b.seansi_id WHERE b.loodud > s.algus_aeg
    UNION ALL
    SELECT 'kinnitatud broneeringul puudub edukas makse', count(*)
    FROM broneeringud b WHERE b.staatus = 'kinnitatud'
      AND NOT EXISTS (SELECT 1 FROM maksed m WHERE m.broneeringu_id = b.id AND m.staatus = 'edukas')
    UNION ALL
    SELECT 'tühistatud broneeringul on edukas makse', count(*)
    FROM broneeringud b JOIN maksed m ON m.broneeringu_id = b.id
    WHERE b.staatus = 'tühistatud' AND m.staatus = 'edukas'
    UNION ALL
    SELECT 'saali mahutavus ≠ istekohtade arv', count(*)
    FROM kinosaalid k WHERE k.mahutavus <> (SELECT count(*) FROM istekohad WHERE kinosaal_id = k.id)
    UNION ALL
    SELECT 'film ilma žanrita', count(*)
    FROM filmid f WHERE NOT EXISTS (SELECT 1 FROM filmid_zanrid fz WHERE fz.filmi_id = f.id)
    UNION ALL
    SELECT 'arvustus filmile, mida kasutaja pole näinud', count(*)
    FROM arvustused a WHERE NOT EXISTS (
        SELECT 1 FROM broneeringud b JOIN seansid s ON s.id = b.seansi_id
        WHERE b.kasutaja_id = a.kasutaja_id AND s.filmi_id = a.filmi_id AND b.staatus = 'kinnitatud')
) checks;

\echo '== 5. Näidis: tänased seansid Tallinnas'
SELECT to_char(s.algus_aeg AT TIME ZONE 'Europe/Tallinn', 'HH24:MI') AS algus,
       k.name AS saal, f.pealkiri AS film, s.alghind AS hind,
       (SELECT count(*) FROM broneeritud_kohad bk WHERE bk.seansi_id = s.id) AS müüdud
FROM seansid s
JOIN filmid f ON f.id = s.filmi_id
JOIN kinosaalid k ON k.id = s.saali_id
JOIN kino ki ON ki.id = k.kino_id
WHERE ki.linn = 'Tallinn' AND (s.algus_aeg AT TIME ZONE 'Europe/Tallinn')::date = (now() AT TIME ZONE 'Europe/Tallinn')::date
ORDER BY s.algus_aeg, k.name
LIMIT 10;

\echo '== 6. Näidis: filmid ja nende žanrid (mitu-mitmele seos)'
SELECT f.pealkiri AS film, string_agg(z.nimi, ', ' ORDER BY z.nimi) AS žanrid
FROM filmid f
JOIN filmid_zanrid fz ON fz.filmi_id = f.id
JOIN "žanrid" z ON z.id = fz."žanri_id"
GROUP BY f.id, f.pealkiri
ORDER BY f.pealkiri
LIMIT 8;

# TA-andmebaas

Kinoprojekti andmebaasi ülesanded. Repositoorium sisaldab mõlemat tööd:

1. **Andmebaasi planeerimine ja backendi võrdlus**: `project.sql`, `backend-comparison.md`,
   `docs/andmebaasi-kirjeldus.md`.
2. **Docker, ORM-i skeem ja demoandmed**: `docker-compose.yml`, Django mudelid ja migratsioonid,
   Fakeri seeder, kontrollpäringud ja testid.

Tehnoloogiad: **PostgreSQL 16**, **Python 3.12**, **Django 5.2 (Django ORM)**, **Faker**, **Docker Compose**.

## Lähteprojekt

Backend pärineb grupi kinoprojektist
[Tallinna-Polutehnikum/TA-24A-3](https://github.com/Tallinna-Polutehnikum/TA-24A-3)
(commit `63aaf6f`). Esimene commit (`chore: import cinema backend…`) on algsete failide koopia.
Kõik hilisemad commitid on selle töö raames tehtud muudatused.

Kaasa võtsin ainult andmebaasi ülesannetega seotud failid:

| Kopeeritud | Välja jäetud ja põhjus |
| --- | --- |
| `backend/` (Django projekt, `cinema` rakendus, migratsioonid, seeder) | `frontend/`: Vue kasutajaliides ei puuduta andmebaasi ülesandeid |
| `docker-compose.yml`, `project.sql`, `.gitignore` | `backend/config/__pycache__/*.pyc`: genereeritud failid |
| | `README.md`, `documentation.md`: asendatud selle repo dokumentatsiooniga |

Kopeerimisel asendasin koodi sisse kirjutatud Django `SECRET_KEY` ja andmebaasi parooli
kohatäitjaga. Nüüd loetakse saladused failist `.env`.

## Struktuur

```text
TA-andmebaas/
├── README.md                    # see fail: käivitamine ja ülevaade
├── project.sql                  # planeeritud andmebaasi struktuur (PostgreSQL)
├── backend-comparison.md        # backendi/ORM-i variantide võrdlus ja valik
├── docs/andmebaasi-kirjeldus.md # ER-diagramm, tabelid, seosed, muudatused, skeemide võrdlus
├── docker-compose.yml           # PostgreSQL + Django backend, nimega volume
├── .env.example                 # näidisseaded (kopeeri .env failiks)
├── scripts/kontroll.sql         # ridade arvu ja terviklikkuse kontrollpäringud
└── backend/
    ├── Dockerfile, requirements.txt, manage.py
    ├── config/settings.py       # loeb seaded keskkonnamuutujatest
    └── cinema/
        ├── models.py            # ORM-mudelid = tabelid, seosed ja piirangud
        ├── migrations/          # 0001, 0002 (algsed), 0003_schema_integrity (uus)
        ├── management/commands/seed_demo.py   # Fakeri seeder
        └── tests.py             # 17 testi: andmed, seosed, piirangud
```

## Ülesanne 1: planeerimine ja backendi valik

- **`project.sql`**: kogu skeem loetava SQL-ina koos selgitustega: 12 tabelit, primaar- ja
  võõrvõtmed, UNIQUE/CHECK/EXCLUDE piirangud ja indeksid. See vastab täpselt Django
  migratsioonide loodud skeemile (võrdlus on failis `docs/andmebaasi-kirjeldus.md`). Tabeleid selle
  failiga ei looda, seda teeb Django.
- **`backend-comparison.md`**: Django ORM-i, SQLAlchemy + Alembicu, Prisma ja Laravel Eloquenti
  võrdlus koos plusside, miinuste ja valiku põhjendusega.
- **`docs/andmebaasi-kirjeldus.md`**: ER-diagramm, tabelite ja seoste (1:N, M:N) kirjeldus,
  algse projektiga võrreldes parandatud vead ning `project.sql` ja ORM-skeemi võrdluse tulemus.

## Ülesanne 2: käivitamine

**Eeldused:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (koos Docker
Compose'iga) ja Git. Pythonit ei pea arvutisse paigaldama, sest backend töötab konteineris.

Kõik käsud käivita **repositooriumi juurkaustas**. Käsud töötavad nii PowerShellis kui ka bashis,
kui pole märgitud teisiti.

### 0. Kloonimine ja seaded

```powershell
git clone https://github.com/D3brix/TA-andmebaas.git
cd TA-andmebaas
Copy-Item .env.example .env      # bashis: cp .env.example .env
```

Muuda failis `.env` vähemalt `POSTGRES_PASSWORD` ja `DJANGO_SECRET_KEY` väärtust. Fail `.env`
on `.gitignore`'is ega jõua GitHubi.

### 1. Andmebaasi käivitamine Docker Compose'iga

```powershell
docker compose up -d --build
docker compose ps
```

Käivituvad teenused `db` (PostgreSQL 16, arvutis port `5433`) ja `backend` (Django, port `8001`).
`backend` ootab, kuni andmebaasi healthcheck on korras. Teenuse `db` olek peab olema `healthy`.

Andmed on **nimega Docker volume'is** `ta-andmebaas_kino_pgdata`. Volume ei kao, kui konteiner
peatatakse või kustutatakse (`docker compose down`).

### 2. Backendi sõltuvused

Sõltuvused (`backend/requirements.txt`: Django, psycopg2, Faker) paigaldatakse Docker image'i
ehitamisel eelmise sammu käsuga `--build`. Eraldi käsku pole vaja. Kontroll:

```powershell
docker compose exec backend pip list
```

### 3. ORM-i migratsioonid

```powershell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py showmigrations cinema
```

Migratsioonid loovad kõik tabelid Django mudelitest (`backend/cinema/models.py`):
`0001_initial`, `0002_alter_user_phone_number` ja `0003_schema_integrity`. Kõigi ees peab olema `[X]`.

### 4. Seeder (demoandmed)

```powershell
docker compose exec backend python manage.py seed_demo
```

Seeder loob Fakeriga (`et_EE`) omavahel seotud andmed: 80 kasutajat, 3 kino, 9 saali, 966 istekohta,
22 filmi, 10 žanri, 631 seanssi, 1630 broneeringut, 3757 piletit, umbes 1770 makset ja umbes 250 arvustust.

Kui andmebaasis on juba andmeid, keeldub seeder neid üle kirjutamast. Uuesti genereerimiseks
(tühjendab kinotabelid ja alustab ID-sid 1-st):

```powershell
docker compose exec backend python manage.py seed_demo --clear
```

### 5. Tabelite ja andmete kontroll

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /scripts/kontroll.sql'
```

Väljund näitab:
1. iga tabeli ridade arvu;
2. suurte tabelite ≥ 100 rea kontrolli (`OK`);
3. kõiki võõrvõtmeid;
4. 13 terviklikkuse kontrolli, kus iga `vigu` peab olema `0`: orvukirjed, pilet õigel seansil
   ja õiges saalis, topeltmüük, kattuvad seansid, summade ja maksete klappimine jne;
5. ja 6. näidispäringud (tänane kinokava, filmid koos žanritega).

Automaattestid (luuakse eraldi testandmebaas, mis pärast kustutatakse):

```powershell
docker compose exec backend python manage.py test
```

Tabelite nimekiri psql-is:

```powershell
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

### 6. Teenuste peatamine

```powershell
docker compose down
```

Konteinerid kustutatakse, **andmed jäävad volume'isse alles**. Järgmine `docker compose up -d`
käivitab andmebaasi samade andmetega.

### 7. Puhtast olekust uuesti ülesehitamine

```powershell
docker compose down -v
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /scripts/kontroll.sql'
```

> ⚠️ `docker compose down -v` kustutab lisaks konteineritele ka **nimega volume'i
> `ta-andmebaas_kino_pgdata` ja kõik selles olevad andmebaasi andmed**. Kasuta seda ainult selle
> projekti arenduskeskkonnas. Compose'i projekti nimi on `ta-andmebaas`, nii et käsk ei puuduta
> teiste projektide (nt TA-24A-3) konteinereid ega volume'e.

Kui `docker compose up` kohe pärast `down -v` käivitada, võib `backend` mõne sekundi oodata, kuni
PostgreSQL loob uue andmebaasi. Healthcheck hoolitseb selle eest.

## Probleemide lahendamine

| Probleem | Lahendus |
| --- | --- |
| `required variable POSTGRES_DB is missing a value: Puudub .env…` | Tee samm 0 (`.env` loomine). |
| `port is already allocated` | Muuda `.env` failis `POSTGRES_HOST_PORT` või `BACKEND_HOST_PORT`. |
| `Kinoandmebaas pole tühi` | Kasuta `seed_demo --clear` või ehita puhtast olekust (samm 7). |
| Migratsioon `0003` ebaõnnestub vanade andmetega | `0003` eeldab puhast andmebaasi. Tee samm 7. |

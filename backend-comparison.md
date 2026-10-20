# Backendi ja ORM-i valik

Selles dokumendis võrdlen kinoprojekti jaoks nelja backendi/ORM-i varianti ja põhjendan, miks
jäime **Python + Django + Django ORM + PostgreSQL** juurde.

## Lähtekoht: mis projektis juba olemas oli

Kinoprojekt TA-24A-3 kasutas juba enne seda tööd järgmist:

| Osa | Tehnoloogia |
| --- | --- |
| Backend | Python 3.12, Django 5 (`backend/`) |
| ORM ja migratsioonid | Django ORM, migratsioonid `0001_initial`, `0002_alter_user_phone_number` |
| Andmebaas | PostgreSQL 16 (Docker Compose) |
| Testandmed | Faker (`seed_demo` käsk) |
| Frontend | Vue 3 + Vite (ei kuulu andmebaasi ülesannete hulka) |

Seega ei alustanud ma nullist. Küsimus oli: kas Django ORM on selle andmemudeli jaoks
hea valik või tasuks vahetada?

## Mõisted

- **ORM** (*Object-Relational Mapping*) – teek, mis seob andmebaasi tabelid programmeerimiskeele
  klassidega. Tabeli rida on objekt ja veerg on objekti väli. SQL-i ei pea iga päring käsitsi kirjutama.
- **Migratsioon** – versioonitud fail, mis kirjeldab skeemi muudatust (nt "lisa tabel" või "lisa
  UNIQUE-piirang"). Migratsioonid käivitatakse järjest, nii et iga arendaja andmebaas jõuab samasse olekusse.
- **Seeder** – skript, mis täidab andmebaasi testandmetega.

## Võrreldavad variandid

1. **Django ORM** (Python) – praegune lahendus.
2. **SQLAlchemy 2 + Alembic** (Python, nt koos FastAPI-ga).
3. **Prisma** (Node.js / TypeScript, nt koos Expressi või NestJS-iga).
4. **Laravel Eloquent** (PHP).

### 1. Django ORM

Mudelid on Pythoni klassid (`backend/cinema/models.py`). `makemigrations` genereerib nende
põhjal migratsioonid ja `migrate` rakendab need.

**Plussid**
- Juba kasutusel: mudelid, migratsioonid, Docker ja seeder olid olemas, nii et vahetus oleks töö kaotsi läinud.
- Migratsioonid genereeritakse automaatselt mudelitest, ka UNIQUE-, CHECK- ja indeksimuudatused.
- Seosed on lihtsad: `ForeignKey` (1:N), `ManyToManyField(through=...)` (M:N vahetabeliga).
- PostgreSQL-i erivõimalused on toetatud (`django.contrib.postgres`). Selles projektis kasutame
  näiteks `ExclusionConstraint`'i, mis keelab samas saalis kattuvad seansid.
- Kaasas on testiraamistik (eraldi testandmebaas), management-käsud (seeder on `manage.py seed_demo`)
  ja admin-liides andmete vaatamiseks.
- Pythoni Faker toetab eesti keelt (`Faker('et_EE')`): eesti nimed, aadressid ja postiindeksid.

**Miinused**
- Raamistik on suur ja "arvamusega": projekt peab järgima Django struktuuri.
- Liitvõõrvõtmeid (mitmest veerust koosnev FOREIGN KEY) ei saa mudelis kirjeldada. Seetõttu
  kontrollitakse reeglit "pileti seanss = broneeringu seanss" rakenduses, testides ja SQL-kontrollis.
- Asünkroonne tugi on piiratum kui FastAPI-l (kinoprojekti mahu juures pole see probleem).

### 2. SQLAlchemy 2 + Alembic (FastAPI)

SQLAlchemy on Pythoni levinuim eraldiseisev ORM. Alembic on selle migratsioonitööriist.

**Plussid**
- Väga paindlik: toetab nii ORM-stiili kui ka peaaegu puhast SQL-i (Core).
- Toetab PostgreSQL-i võimalusi, sh `ExcludeConstraint` ja `CheckConstraint`.
- FastAPI-ga saab kiire ja tüübitud REST API, mis sobib Vue frontendiga.
- Sama keel (Python) ja sama Faker-teek.

**Miinused**
- Kõik tuleb ise kokku panna: andmebaasisessioonid, seaded, testide andmebaas ja admin.
- Alembicu `--autogenerate` ei tuvasta kõiki muudatusi (nt CHECK-piiranguid), seega tuleb migratsioone käsitsi üle vaadata.
- Olemasolevad Django mudelid ja migratsioonid tuleks ümber kirjutada.

### 3. Prisma (Node.js / TypeScript)

Skeem kirjeldatakse failis `schema.prisma`. `prisma migrate` genereerib SQL-migratsioonid.

**Plussid**
- Väga loetav skeemikeel ja hea TypeScripti tüübikontroll.
- Sama keel kui frontendil (JavaScript/TypeScript), nii et meeskond kasutaks ainult ühte keelt.
- M:N seosed on lihtsad (kaudne või selge vahetabel).
- Testandmete jaoks on olemas `@faker-js/faker`.

**Miinused**
- CHECK- ja EXCLUDE-piiranguid ei saa `schema.prisma`s kirjeldada. Need tuleb lisada käsitsi
  migratsiooni SQL-faili, mis tähendab kahte tõe allikat.
- Kogu backend tuleks Pythonist Node.js-i ümber kirjutada, sh Dockerfile ja seeder.
- Ehitatud admin-liidest ega testandmebaasi haldust pole.

### 4. Laravel Eloquent (PHP)

**Plussid**
- Täislahendus nagu Django: migratsioonid, seederid ja factory'd (FakerPHP) on sisse ehitatud.
- Eloquent'i seosed (`hasMany`, `belongsToMany`) on lihtsad.

**Miinused**
- Teine keel (PHP), mida projektis seni pole. Kogu backend tuleks ümber kirjutada.
- Migratsioonid kirjutatakse käsitsi (neid ei genereerita mudelist). Skeem ja mudel võivad lahku minna.
- PostgreSQL-i EXCLUDE-piirangu jaoks oleks vaja toorest SQL-i.

## Kokkuvõtlik võrdlus

Hinne: ✔ hea, ~ osaliselt, ✘ puudub või nõuab palju lisatööd.

| Kriteerium | Django ORM | SQLAlchemy + Alembic | Prisma | Laravel Eloquent |
| --- | --- | --- | --- | --- |
| Sobib olemasoleva koodiga | ✔ juba kasutusel | ~ sama keel, uus kood | ✘ uus keel | ✘ uus keel |
| Migratsioonid mudelist | ✔ automaatne | ~ autogenerate + ülevaatus | ✔ automaatne | ✘ käsitsi |
| 1:N ja M:N seosed | ✔ | ✔ | ✔ | ✔ |
| CHECK / UNIQUE ORM-is | ✔ | ✔ | ~ ainult UNIQUE | ~ osaliselt |
| PostgreSQL EXCLUDE | ✔ `ExclusionConstraint` | ✔ `ExcludeConstraint` | ✘ toores SQL | ✘ toores SQL |
| Seeder + Faker | ✔ management-käsk, `et_EE` | ✔ Faker, ise ehitada | ✔ faker-js | ✔ factory'd, FakerPHP |
| Testid eraldi andmebaasiga | ✔ sisse ehitatud | ~ ise seadistada | ~ ise seadistada | ✔ |
| Admin andmete vaatamiseks | ✔ | ✘ | ~ Prisma Studio | ✘ (lisapakett) |
| Õppimiskõver meeskonnale | ✔ juba tuttav | ~ | ~ | ✘ |

## Otsus

**Valik: Django 5 + Django ORM + PostgreSQL 16.**

Põhjused:

1. **Olemasolev töö jääb alles.** Mudelid, kaks migratsiooni, Docker Compose ja seeder olid juba
   Djangos. Vahetus oleks tähendanud kogu backendi ümberkirjutamist ilma sisulise võiduta.
2. **Kõik andmebaasi nõuded on ORM-is kirjeldatavad.** Primaar- ja võõrvõtmed, 1:N ja M:N seosed,
   UNIQUE, CHECK, indeksid ja isegi PostgreSQL-i EXCLUDE-piirang on mudelis kirjas. Migratsioonid
   genereeritakse neist automaatselt. Tabeleid ei looda käsitsi SQL-iga.
3. **Testimine on sisse ehitatud.** `manage.py test` loob iga kord eraldi testandmebaasi, käivitab
   migratsioonid ja seederi ning kontrollib andmete terviklikkust.
4. **Faker toetab eesti keelt.** Demoandmetes on eesti nimed, aadressid ja postiindeksid.

PostgreSQL jäi andmebaasiks, sest see oli projektis juba kasutusel. Lisaks toetab see
ajavahemike kattuvuse keeldu (`EXCLUDE USING gist`), mida MariaDB ega MySQL ei paku, ja on Djangos kõige paremini toetatud.

Teadlik piirang: Django ei toeta liitvõõrvõtmeid. Seepärast on kaks mitut tabelit hõlmavat reeglit
(pilet kuulub broneeringu seansile ja istekoht on seansi saalis) kontrollitud mudeli `clean()`
meetodis, automaattestides ja `scripts/kontroll.sql` päringutes. Vajadusel saaks need ka
andmebaasi triggeriga jõustada.

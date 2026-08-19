# Portal de Dades Electorals — Ajuntament de Rubí

Portal web que consulta i presenta dades electorals obertes de l'Ajuntament
de Rubí. És una aplicació **client / backend-for-frontend**: no té base de
dades pròpia en cap moment. Tota lectura (i, en el futur, escriptura) de
dades es fa mitjançant crides HTTP a APIs REST externes; aquesta aplicació
només les consulta, les transforma/agrega per a la vista, i renderitza
HTML. L'única "persistència" que existeix és una **caché en memòria de
curta durada** (TTL configurable) per no saturar les APIs externes — mai
es persisteix res a disc ni a una base de dades local (ni SQLite, ni ORM,
ni fitxers).

## Arquitectura

Flask amb Blueprints (un per apartat), triat en lloc de FastAPI perquè
aquest projecte és, sobretot, un renderitzador de plantilles Jinja
server-side (HTML per a un navegador, no un backend purament d'API), i
Flask + Blueprints encaixa millor amb aquest patró amb menys peces mòbils.
Si en el futur calgués exposar aquest mateix portal com a API JSON pròpia,
migrar a FastAPI seria senzill perquè tota la lògica de negoci ja viu fora
de les vistes (a `services/` i `blueprints/*/services.py`).

```
app/
  __init__.py               # factory create_app(), registra els blueprints
  config.py                 # URLs base de les APIs, timeouts, TTL de caché
  blueprints/
    resultats/               # ← implementat completament
    cens/                    # ← cens agregat per mesa implementat;
                             #   cerca individual per DNI: placeholder futur
    mesa/                    # ← implementat: estat d'escrutini en viu per mesa
    estadistiques/           # ← comparativa Participació/Abstenció implementada;
                             #   resta de comparatives: futures
    admin/                   # ← placeholder ("Pròximament")
  services/
    api_clients/
      base_client.py          # client HTTP genèric: GET/POST/PUT/DELETE,
                               # headers, timeouts, reintents, errors
      resultats_client.py      # client concret per a la font de Resultats
      cens_client.py           # client concret per a la font de Cens (per mesa)
      mesa_client.py           # client concret per a l'estat d'escrutini per mesa
  templates/
  static/
main.py
requirements.txt
```

### Font de dades de "Resultats electorals"

Avui, la "API REST de només lectura" de resultats és el CSV obert publicat
al GitHub de l'Ajuntament de Rubí:

```
https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv/public_eleccions_partits.csv
```

`resultats_client.py` el tracta exactament com un endpoint REST: hi fa un
`GET` a través de `BaseApiClient`, el parseja i l'agrega en memòria, i el
cacheja amb un TTL curt (`RESULTATS_CACHE_TTL_SECONDS`, per defecte 300s).
El dia que aquesta font es converteixi en una API REST real, només caldrà
canviar `RESULTATS_API_BASE_URL` / `RESULTATS_CSV_PATH` a `config.py` (i,
si canvia la forma de la resposta, ajustar `_fetch_dataframe` en aquest
mateix fitxer) — cap altra part del projecte necessita canviar.

### Font de dades de "Cens electoral" (agregat per mesa)

De la mateixa manera, el cens agregat per mesa es llegeix d'un altre CSV
obert, tractat també com un endpoint REST de només lectura:

```
https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv/public_eleccions_cens.csv
```

És un microdau **anonimitzat** (una fila = un elector censat, sense DNI ni
cap altre identificador personal: només la seva ubicació de mesa i
variables demogràfiques agregables com edat, sexe, estudis). `cens_client.py`
el cacheja igual que `resultats_client.py` (TTL curt, `CENS_MESA_CACHE_TTL_SECONDS`),
però es manté deliberadament "prim": només serveix files crues; el
comptatge per mesa (agrupar per districte/secció/mesa/col·legi i comptar
files) es fa a `blueprints/cens/services.py`, no al client.

### Font de dades de "Estat d'escrutini per mesa"

L'apartat "Resultats per mesa electoral" llegeix un tercer CSV obert,
diferent del de Resultats però amb el mateix `CODI_CONVOCATORIA`:

```
https://raw.githubusercontent.com/ajrubi/opendata/refs/heads/main/datasets/csv/public_eleccions_meses.csv
```

Cada fila és l'estat d'una mesa en el moment de la consulta: si ja s'ha
obert (`OBERTA_MESA`), si ja ha comunicat resultats — és a dir, si ja està
escrutinada (`COMUNICADA_MESA` = `"SI"`) — i a quina hora (`HORA_COMUNICADA_MESA`),
a més dels seus recomptes d'avanç (`AVAN1/2/3_MESA`) i el total de vots
rebuts. Aquests valors **haurien de canviar mentre dura l'escrutini**, però
la pantalla que en faria un seguiment en viu encara no existeix: mentre no
hi sigui, `mesa_client.py` cacheja aquest CSV amb el mateix TTL llarg que
la resta de fonts (`MESA_ESTAT_CACHE_TTL_SECONDS`, per defecte 24h, com
`RESULTATS_CACHE_TTL_SECONDS`/`CENS_MESA_CACHE_TTL_SECONDS`). El dia que
s'implementi la pantalla d'escrutini en viu, aquest TTL s'haurà de tornar a
baixar a un valor curt (p. ex. els 60s que tenia abans). La vista ja
ofereix un botó "Actualitza ara" (`?refresh=1`) per forçar una lectura
immediata sense esperar el TTL.

**"% d'escrutini" oficial**: el Ministeri de l'Interior i la Junta
Electoral Central el calculen com `(mesas comunicades / total de mesas) ×
100` — els vots (a partits, nuls o blancs) no hi alteren res. És
exactament el que calcula `blueprints/mesa/services.py::build_summary()`
per a les targetes de resum; aquest client/vista no calcula ni mostra cap
altre "% escrutat" basat en vots, precisament per no confondre'l amb
l'indicador oficial.

## Instal·lació i arrencada

Requereix Python 3.10+.

```bash
# 1. Crear i activar un entorn virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# 2. Instal·lar dependències
pip install -r requirements.txt

# 3. Arrencar el servidor de desenvolupament
python main.py
```

El portal quedarà disponible a `http://127.0.0.1:5000/`, que redirigeix a
`/resultats/`.

### Variables d'entorn opcionals

| Variable                      | Per defecte                                                | Descripció                                   |
|--------------------------------|-------------------------------------------------------------|-----------------------------------------------|
| `RESULTATS_API_BASE_URL`       | (URL del CSV a GitHub)                                       | Base de la font de Resultats                  |
| `RESULTATS_CSV_PATH`           | `public_eleccions_partits.csv`                              | Path/fitxer dins la base anterior             |
| `RESULTATS_CACHE_TTL_SECONDS`  | `86400`                                                      | TTL de la caché en memòria (24h: són resultats ja publicats, no canvien) |
| `HTTP_TIMEOUT_SECONDS`         | `10`                                                         | Timeout de les crides HTTP                    |
| `HTTP_MAX_RETRIES`             | `3`                                                          | Reintents davant errors 5xx/429               |
| `CENS_MESA_API_BASE_URL`       | (URL del CSV a GitHub)                                       | Base de la font de Cens agregat per mesa      |
| `CENS_MESA_CSV_PATH`           | `public_eleccions_cens.csv`                                  | Path/fitxer dins la base anterior             |
| `CENS_MESA_CACHE_TTL_SECONDS`  | `86400`                                                      | TTL de la caché en memòria del cens per mesa (24h, pel mateix motiu) |
| `MESA_ESTAT_API_BASE_URL`      | (URL del CSV a GitHub)                                       | Base de la font d'estat d'escrutini per mesa  |
| `MESA_ESTAT_CSV_PATH`          | `public_eleccions_meses.csv`                                 | Path/fitxer dins la base anterior             |
| `MESA_ESTAT_CACHE_TTL_SECONDS` | `86400`                                                       | TTL de la caché — 24h mentre no hi hagi una pantalla d'escrutini en viu; caldrà tornar-lo a baixar a un valor curt (p. ex. 60s) quan aquesta pantalla existeixi |
| `CENS_API_BASE_URL`            | (buit)                                                       | Reservada per a la futura cerca per DNI       |
| `ADMIN_API_BASE_URL`           | (buit)                                                       | Reservada per a la futura API d'administració |
| `ADMIN_API_TOKEN`              | (buit)                                                       | Reservada per al futur token d'administració  |

## Roadmap / pròxims apartats

### Cens electoral — cerca individual per DNI (pendent)
El cens **agregat per mesa** ja està implementat (vegeu més amunt): dades
anonimitzades, sense cap identificador personal, comptades per
districte/secció/mesa/col·legi. El que queda pendent, com a placeholder
separat de cara al futur, és la **cerca d'un elector individual** per DNI +
data de naixement.
- **API que necessitarà**: una API REST externa de només lectura, diferent
  de la del cens per mesa (`GET` per DNI + data de naixement). S'implementaria
  un nou `services/api_clients/cens_dni_client.py` (o equivalent), seguint
  el mateix patró de `BaseApiClient`, apuntant a `CENS_API_BASE_URL`.
- **Seguretat/RGPD**: a diferència del cens per mesa, aquí sí es tracten
  dades personals identificables. La futura API haurà de tenir autenticació
  robusta (OAuth2/JWT), control d'accés per rols i registre d'auditoria (qui
  ha consultat quin elector i quan), complint el RGPD/LOPDGDD. Aquesta
  aplicació **no** ha de reimplementar aquesta seguretat: només ha de
  consumir l'endpoint amb les credencials adequades.

### Estadístiques comparatives
El sub-apartat "Participació i abstenció per convocatòria" ja està
implementat (gràfic de barres apilades interactiu + taula, filtrable per
tipus d'elecció). Queden pendents altres comparatives (p. ex. evolució de
vots per candidatura entre convocatòries), que es poden afegir com a nous
sub-apartats seguint el mateix patró `routes.py` + `services.py`,
reutilitzant `get_convocatories()` / `get_results(codi)` sense canvis.
- **Seguretat**: dades públiques agregades, sense dades personals.

### Àrea privada / Administració
- **API que necessitarà**: una futura API REST d'administració amb
  operacions d'escriptura (`POST`/`PUT`/`DELETE`) per gestionar
  convocatòries i escrutinar vots per partit/mesa. Es implementaria un
  `services/api_clients/admin_client.py` sobre `BaseApiClient`, enviant el
  token de sessió de l'usuari autenticat a la capçalera `Authorization`
  (`BaseApiClient` ja ho suporta).
- **Seguretat crítica**: aquest és l'apartat que realment escriu dades
  (recomptes de vots, convocatòries). La futura API externa haurà de tenir:
  - autenticació robusta OAuth2/JWT per als usuaris administradors;
  - control d'accés per rols (qui pot escrutar, qui pot crear/modificar
    convocatòries);
  - registre d'auditoria complet (qui ha fet quina operació d'escriptura,
    sobre quina convocatòria/mesa/partit, i quan);
  - compliment RGPD/LOPDGDD.
  Aquesta aplicació web només consumirà aquesta API amb les credencials
  adequades — mai reimplementarà aquesta seguretat pel seu compte, ni
  escriurà res a disc o a una base de dades local.

## Notes de disseny i accessibilitat

- Colors corporatius: vermells i blancs, amb contrast pensat per complir
  WCAG AA (text vermell fosc/blanc sobre fons blanc/vermell).
- Enllaç "Salta al contingut principal", `aria-current="page"` a l'element
  de menú actiu, taules amb `<caption>`/`<th scope>`, gràfic de barres
  implementat amb marcatge accessible (`role="img"` + etiqueta de text, no
  només color) en lloc d'una llibreria de gràfics amb canvas.
- Disseny responsive: les 4 targetes i les dues columnes (taula + gràfic)
  s'apilen en vertical en mòbil.
- Estats explícits per quan no hi ha dades («Pròximament» als placeholders,
  panell buit quan una convocatòria no té candidatures) i per quan l'API
  triga o falla (panell d'error amb botó "Torna-ho a provar" + overlay de
  càrrega amb `aria-live` mentre es refresca la pàgina).

## Font de dades

Ajuntament de Rubí — Dades Obertes (GitHub):
`ajrubi/opendata/datasets/csv/public_eleccions_partits.csv` (resultats) i
`ajrubi/opendata/datasets/csv/public_eleccions_cens.csv` (cens per mesa).

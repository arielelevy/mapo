# infra/ · stack local de MAPO

Lo que hace falta para correr el plano de ingesta y el ledger en la máquina de desarrollo,
sin Docker Desktop. Nada de esto es el producto ni el banco: `lab/` no lo importa.

## Runtime: wslc, no Docker Desktop (2026-09-05)

Los contenedores corren con `wslc`, el runtime nativo de WSL que llega con WSL 2.9.3+ (hoy
pre-release; instalado 2.9.10 con `wsl --update --pre-release`). Misma sintaxis que
Docker (`wslc run`, `wslc ps -a`, `wslc pull`, alias `container.exe`), sin licencias ni
capa extra. Lo que **no** trae: `compose` ni `cp`. El compose lo reemplaza
`wslc/stack.ps1`; los archivos entran a los contenedores por stdin (`wslc exec -i`).
Trampa medida: `wslc exec` parte por espacios los argumentos aunque vengan entrecomillados,
así que `psql -c 'select id from t'` llega como cuatro argumentos. Todo SQL va por stdin.

Decisión del autor, con el riesgo escrito: es preview y ésta es la máquina de trabajo.
Si WSL preview rompe algo, Docker Desktop también deja de andar porque corre sobre WSL2;
la vuelta atrás es reinstalar el MSI estable desde GitHub, no un comando.

## Qué levanta `wslc/stack.ps1 up`

| Contenedor | Imagen | Puerto | Para qué |
|---|---|---|---|
| `mapo-postgres` | `postgres:18` | 5432 | ledger epistémico (base `mapo`) y persistencia de Temporal (`temporal`, `temporal_visibility`) |
| `mapo-temporal` | `temporalio/auto-setup` | 7233 | server de Temporal con esquema en ese Postgres |
| `mapo-temporal-ui` | `temporalio/ui` | 8233 | UI, event history |

Red `mapo`, volumen `mapo_pgdata`. Límites de memoria: 512M, 768M, 256M.

La contraseña de Postgres está en la variable de usuario `MAPO_PG_PASSWORD`
(`HKCU:\Environment`), generada al azar y nunca escrita en el repo. Las shells de las
herramientas arrancan sin el entorno nuevo: el script la lee del registro si no la ve.

```
.\infra\wslc\stack.ps1 up        # crea lo que falte y arranca, en orden
.\infra\wslc\stack.ps1 migrate   # aplica infra/postgres/NNN_*.sql pendientes
.\infra\wslc\stack.ps1 test      # guardas de ARQUITECTURA §10 que son SQL puro
.\infra\wslc\stack.ps1 status    # ps, pg_isready, memoria de la VM
.\infra\wslc\stack.ps1 down      # detiene y borra contenedores; conserva red y volumen
.\infra\wslc\stack.ps1 destroy   # también borra el volumen: se pierde el ledger
```

## Ledger: `postgres/001_ledger.sql`

Es el esquema de `lab/ARQUITECTURA.es.md` §5, completo: `policy_bundle`,
`promotion_certificate`, `episode`, `final_use_ledger`, `belief_log`, `index_version`,
`live_pointer`, `request_log`, más `schema_migration`. Las tablas que son historia
(`belief_log`, `policy_bundle`, `promotion_certificate`, `final_use_ledger`, `request_log`)
tienen trigger que aborta UPDATE y DELETE con `restrict_violation`.

`postgres/test_ledger.sql` corre en una transacción que se revierte y verifica lo que §10
pide del ledger: dos trials de la misma celda violan la PK (anti-pseudorreplicación),
`n_trials >= 3`, segundo uso del mismo `claim_id` falla (final una sola vez), UPDATE y
DELETE sobre `belief_log` bloqueados, certificados y θ inmutables, `live_pointer` de una
sola fila cuyo único cambio permitido es el UPDATE del flip, y FK de episodio a θ.
Once guardas, once `OK` el 2026-09-05.

Lo que falta para cerrar el paso 1 de §9: migrar el ledger JSONL existente a estas tablas
y el adapter Python detrás de `data/ports.py`. Este esquema es el destino, no la migración.

## Medido el 2026-09-05

| Qué | Memoria |
|---|---|
| VM de `wslc` sin contenedores | 763 MB |
| VM con Postgres + Temporal + UI, spike corriendo | 1.248 MB |
| `temporal server start-dev` (binario local, SQLite, con UI) | 124 MB en reposo, 172 MB bajo el spike |
| un worker Python del spike, ocioso | 66 MB |

El spike `spikes/temporal/demo.py` pasa igual contra este server que contra el de
desarrollo: 7,8 s, 10,0 s, rechazo de duplicado, fan-out 7,1 s. Eso cierra la "razón 2" de
§2.1 con un número: el costo de correr Temporal con Postgres on-prem es un contenedor de
server, uno de UI, dos bases en el Postgres que ya existe, y medio giga de RAM de VM.

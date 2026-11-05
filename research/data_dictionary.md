# Esquema mínimo de dados observacionais (proposta)

Armazenar agregações por intervalo e aproximação; **não** coletar identificadores de veículos ou pessoas.

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `site_id` | string | Identificador do ponto, ex.: MIRANTE-01 |
| `approach_id` | string | Aproximação mapeada em plano de campo |
| `start_utc` | ISO 8601 | Início do intervalo em UTC |
| `end_utc` | ISO 8601 | Fim exclusivo do intervalo em UTC |
| `movement` | enum | through, left, right, u_turn, unknown |
| `vehicle_class` | enum | car, motorcycle, bus, truck, other, unknown |
| `vehicle_count` | int >= 0 | Contagem na janela e categoria |
| `measurement_method` | enum | manual, camera_aggregate, radar_aggregate |
| `quality_flag` | enum | validated, provisional, incomplete, rejected |
| `observer_notes` | string? | Comentário operacional sem dados pessoais |

A amostra é sintética, sem representar qualquer observação de Parnaíba:

```csv
site_id,approach_id,start_utc,end_utc,movement,vehicle_class,vehicle_count,measurement_method,quality_flag,observer_notes
SYNTHETIC-01,N,2026-01-01T12:00:00Z,2026-01-01T12:15:00Z,through,car,12,manual,provisional,SYNTHETIC_EXAMPLE
```

**Fuso local:** America/Fortaleza (UTC−03:00 em 2026); manter UTC nos dados e converter apenas para visualização. Fases semafóricas, velocidades e filas devem ter tabelas próprias e definição de evento/erro documentada. Gravações brutas, se necessárias, devem obedecer a um plano de privacidade, autorização, retenção mínima e controle de acesso.

Dados simulados não devem receber `measurement_method` observacional: armazenar sob `simulation_runs` com `scenario_id`, `run_id`, `seed`, versão do modelo e parâmetros.

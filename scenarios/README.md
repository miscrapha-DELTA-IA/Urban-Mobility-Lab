# Cenários SUMO — planejamento

A integração SUMO **ainda não está implementada**. Após auditoria da rede OSM, converter a rede via `netconvert`, verificar semáforos/viradas, gerar demandas de viagens sintéticas e salvar configurações de simulação com parâmetros, sementes, versão do SUMO e artefatos.

Cenários previstos: `low_demand`, `baseline`, `high_demand`.

`baseline` será um cenário **hipotético** até haver contagens observadas. Não confundir baseline sintético com situação atual de Parnaíba.

Métricas planejadas: fluxo, tempo de espera, comprimento de fila, tempos de viagem e eventuais erros de roteamento. Usar detectores virtuais compatíveis com as definições dos sensores físicos.

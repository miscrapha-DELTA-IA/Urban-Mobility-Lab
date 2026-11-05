# Protocolo científico inicial — Parnaíba

**Versão:** 0.1 — planejamento, sem resultados empíricos.

## Pergunta central

Em que medida um modelo computacional da rede viária de Parnaíba consegue reproduzir, após calibração independente, fluxos, filas e tempos de espera de interseções selecionadas?

## Objetivos verificáveis

1. Extrair uma rede viária dirigida e documentar a fonte, data e limites espaciais.
2. Auditar topologia: conexões, sentidos, cruzamentos, restrições e segmentos desconectados.
3. Simular cenários **sintéticos** de demanda baixa, intermediária e alta com sementes registradas.
4. Medir fluxo por aproximação, movimentos de conversão, fases semafóricas e filas em locais de validação.
5. Calibrar em um conjunto de observações e avaliar em períodos distintos **não utilizados** na calibração.

## Unidade de análise e métricas

- **Segmento/interseção × intervalo temporal** (janela inicial proposta: 15 minutos).
- Fluxo: veículos/15 min por aproximação e classe, convertido para veículos/h quando pertinente.
- Espera: segundos por veículo, segundo definição fixa de parada.
- Fila: quantidade de veículos e comprimento estimado em metros, com convenção de medição explícita.
- Velocidade: km/h, somente com trajetória, radar calibrado ou outra fonte adequada.
- Temporização semafórica: estado e duração de fases em segundos.

## Plano de avaliação

- Separar dados de calibração e validação por blocos temporais, evitando vazamento de informação.
- Calcular MAE, viés e WAPE para contagens agregadas; não usar WAPE quando o denominador for zero.
- Reportar intervalos de incerteza de cenários simulados, número de réplicas e sementes.
- Registrar falhas de sensores, lacunas e divergências de classificação.
- Contagem manual independente funciona como referência para auditar sensores, não como verdade infalível.

## Limitações e integridade

Uma rede OSM descreve infraestrutura, **não** circulação observada. Simulação sem demanda calibrada não prova valores reais de congestionamento. Não alegar previsão de acidentes sem observações adequadas. A associação entre mobilidade e saúde mental será objeto de protocolo específico com requisitos éticos e causalidade tratada por desenho de estudo, nunca inferida apenas de correlação.

## Primeira estação candidata

MIRANTE-01: [plano de campo](../stations/MIRANTE-01.md).

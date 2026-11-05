# Roadmap verificável — Parnaíba

## Etapa 1 — protocolo científico
- [x] Protocolo e dicionário de dados preliminares publicados
- [ ] Revisão científica externa e delimitação de desfechos específicos

## Etapa 2 — infraestrutura
- [x] Repositório público e ambiente Python 3.11 criados
- [x] Testes iniciais: 2/2 aprovados no Windows pelo pesquisador (2026-11-05)
- [x] CI inicial do GitHub Actions aprovado
- [ ] Testes da versão AOI confirmados no ambiente do pesquisador

## Etapa 3 — rede viária
- [x] Rede viária OSMnx extraída: 6.585 nós e 18.964 segmentos dirigidos
- [x] Auditoria estrutural executada no Windows: 5 componentes fracamente conectados, maior com 6.579 nós; 0 coordenadas ausentes, 0 comprimentos inválidos
- [x] Grafo municipal de referência com SHA-256: `05fb88f7a23f2f9865c9c2656f1a69937bf087776e94cc593728390db240b5d6`
- [x] Ferramenta de criação e recorte manual de AOI desenvolvida
- [x] Decisão inicial: utilizar toda a rede municipal armazenada, sem recorte (ver `docs/full_city_scope.md`)
- [x] Relatório de escopo municipal integral executado no Windows: hash de referência preservado em 2026-11-05
- [ ] Confirmar limite municipal cartográfico e a cobertura da rede OSM
- [ ] Reservar AOIs menores (como MIRANTE-01) para análises complementares

## Etapa 4 — simulação
- [x] Ferramentas de diagnóstico, planejamento, extração e conversão OSM→SUMO implementadas (CI pendente)
- [ ] Instalar e configurar SUMO no Windows do pesquisador
- [ ] Executar extração OSM XML municipal em 4 partes e documentar data e SHA-256
- [ ] Executar netconvert e auditar a nova rede SUMO; GraphML não é entrada direta
- [ ] Comparar conectividade e cobertura da rede SUMO com a rede OSMnx
- [ ] Definir três cenários de demanda **sintética**, sementes e parâmetros
- [ ] Executar e documentar resultados reproduzíveis

## Etapa 5 — validação observacional
- [ ] Planejar estação MIRANTE-01 e aprovações relevantes
- [ ] Obter contagens independentes, fases semafóricas e filas
- [ ] Calibrar em um período e testar em períodos reservados
- [ ] Publicar métricas, incertezas, vieses e limitações

**Nunca indicar dados de tráfego reais com base apenas na geometria do OpenStreetMap.**

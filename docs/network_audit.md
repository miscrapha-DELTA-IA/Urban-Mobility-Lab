# Auditoria estrutural da rede viária de Parnaíba

**Status:** verificação ainda não executada por este repositório. Os resultados de extração fornecidos pelo pesquisador em 2026-11-05 foram: 6.585 nós, 18.964 segmentos direcionados, 2.417.818,77 m somados; **não são contagens de trânsito**. Dois testes unitários do bootstrap passaram no ambiente Windows do pesquisador.

## Execução (PowerShell 5.1, Python 3.11)

Execute **dentro da raiz do projeto**:

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[dev,viz]"
& $python -m pytest -q
& $python -m urban_mobility_lab.audit --plot
```

A auditoria lê o arquivo `data/networks/parnaiba_drive.graphml` **já salvo** e não faz novas consultas a mapas.

Arquivos gerados:
- `reports/parnaiba_network_audit.json`: diagnóstico topológico, bounding box no CRS da rede, SHA256 do grafo e indicadores de qualidade
- `reports/parnaiba_network.png`: visão geral estática das vias

## Critérios de interpretação

- **Conectividade fraca:** componentes onde se ignora o sentido das ruas. Componentes isolados podem decorrer de ilhas, vias sem conexão, delimitação municipal ou erros cartográficos.
- **Conectividade forte:** acessibilidade bidirecional seguindo sentidos da via. Componentes desconectados não provam, por si só, erro cadastral.
- **Extensão somada:** a soma dos segmentos direcionados pode duplicar trechos físicos de mão dupla; não interpretar como extensão total de ruas.
- **Bounding box:** é extensão das coordenadas presentes no grafo e não substitui o polígono de delimitação do estudo.
- **Qualidade:** a auditoria detecta anomalias estruturais, mas não verifica semáforos, faixas, sentidos reais e restrições de conversão. Inspeção cartográfica e dados de campo continuam necessários.
- **Privacidade:** somente geometria OSM; nenhuma observação de pessoas/veículos é produzida.

## Decisões antes do SUMO

1. Delimitar núcleo urbano versus município inteiro e registrar o polígono usado.
2. Inspecionar visualmente o PNG e os componentes desconectados.
3. Confirmar o ponto MIRANTE-01 com observação, não somente com nome de local.
4. Documentar lacunas do OpenStreetMap e preparar correções **internas**, sem alterar dados públicos automaticamente.
5. Converter uma versão congelada da rede para SUMO, mantendo hash e parâmetros.

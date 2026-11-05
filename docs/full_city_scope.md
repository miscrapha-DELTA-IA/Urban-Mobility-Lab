# Escopo: cidade inteira (Parnaíba)

**Decisão científica:** a primeira versão de simulação usará a **rede dirigível municipal completa já extraída**, em vez do polígono de recorte do núcleo urbano.

## Evidência disponível

Extração realizada em 2026-11-05, no Windows do pesquisador:
- 6.585 nós e 18.964 segmentos direcionados;
- soma dos comprimentos direcionados: 2.417.818,77 m (não é extensão física única);
- cinco componentes fracamente conectados; maior contém 6.579 nós;
- nenhum nó sem x/y e nenhum comprimento de aresta inválido;
- SHA-256 do GraphML: `05fb88f7a23f2f9865c9c2656f1a69937bf087776e94cc593728390db240b5d6`.

**Esses valores indicam estrutura mapeada, não quantidade de veículos nem qualidade de tráfego observada.** O nome municipal passado ao OSMnx solicita um polígono de lugar geocodificado, mas o limite deve ser confirmado com o limite oficial municipal. A cobertura de vias reais também necessita de revisão em campo.

## GeoJSON candidato

O arquivo enviado `parnaiba_urban_core (1).geojson` foi examinado separadamente: polígono válido, área geodésica aproximada de **51,321 km²**, totalmente dentro da caixa envolvente dos nós da rede original. Essa seleção é **menor que a extensão geográfica da rede municipal**. Não deve substituir a rede completa quando o objetivo é o município inteiro. Pode servir como área de visualização ou cenário secundário, após revisão.

## Execução — PowerShell 5.1

```powershell
Set-Location "$env:USERPROFILE\Downloads\Urban-Mobility-Lab"
git pull --ff-only origin feat/parnaiba-scientific-bootstrap
$python = ".\.venv\Scripts\python.exe"
& $python -m pytest -q

# Escopo principal = grafo municipal inteiro, sem recorte
& $python -m urban_mobility_lab.scope

# Opcional: diagnosticar quantos nós estão no polígono secundário,
# se o GeoJSON existir localmente:
$polygon = "$env:USERPROFILE\Downloads\parnaiba_urban_core (1).geojson"
if (Test-Path -LiteralPath $polygon) {
    & $python -m urban_mobility_lab.scope --candidate-geojson $polygon
}
```

O comando salva `reports/parnaiba_full_scope.json`, com auditoria estrutural e hash do grafo. **Não altera** `data/networks/parnaiba_drive.graphml` e não cria uma simulação de tráfego.

## Próxima etapa SUMO: nota de formato

O `GraphML` do OSMnx **não é um arquivo de importação direta do `netconvert`**. Para reconstrução fiel de pistas, restrições e semáforos, a rota prioritária é obter um extrato bruto da região em `*.osm.xml` e executar `netconvert --osm-files arquivo.osm.xml -o rede.net.xml`, conforme documentação oficial do SUMO. Reconciliar a cobertura dos dois arquivos antes de comparar o total de arestas/nós, pois os modelos de segmentação são diferentes.

As três demandas sintéticas (baixa, média e alta) ainda não foram criadas. Sem contagens observacionais e fases semafóricas verificadas, resultados do SUMO não são afirmações empíricas sobre a situação do trânsito.

## Divisão de escala

1. **Município completo:** domínio geográfico e conectividade geral.
2. **Principais eixos urbanos:** métricas agregadas por janela temporal.
3. **MIRANTE-01:** ponto de validação com medição independente e, futuramente, simulação mais detalhada.

Essa abordagem não exige descartar nem substituir a rede municipal original.

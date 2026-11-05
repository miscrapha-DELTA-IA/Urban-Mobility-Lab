# SUMO: integração da rede municipal completa — Parnaíba

## Status científico

A rede OSMnx existente foi extraída e auditada localmente pelo pesquisador:
- 6.585 nós, 18.964 segmentos dirigidos;
- SHA-256 do GraphML: `05fb88f7a23f2f9865c9c2656f1a69937bf087776e94cc593728390db240b5d6`.
- Escopo: toda a **rede OSM mapeada retornada pela consulta municipal**. O limite municipal oficial e as vias reais ainda precisam de validação.
- Este módulo não extrai veículos, trânsito atual, acidentes ou dados pessoais.

O arquivo `.graphml` do OSMnx **não** é equivalente ao OSM XML de entrada do SUMO. O fluxo usa `osmGet.py` da própria instalação SUMO para obter dados OSM brutos e `netconvert` para construir uma rede SUMO separada. A caixa retangular cobre toda a rede de origem mais 0,002° de margem por lado, podendo incluir vias fora do município. Portanto, comparar os dois grafos requer auditoria; número de arestas nunca será necessariamente igual.

## 1. Instalar SUMO no Windows

Documentação oficial: https://eclipse.dev/sumo/docs/Installing/

Instalação recomendada via Windows Package Manager, quando disponível:

```powershell
winget install --name sumo
```

Alternativamente, baixar o ZIP 64-bit da versão estável em https://eclipse.dev/sumo/docs/Downloads.html e extrair para uma pasta do usuário. Não é necessário executar o PowerShell em modo administrador quando utilizar a versão portátil. SUMO 1.28.0 é a versão estável publicada em 2026-10-08; congelar a versão efetivamente utilizada no relatório científico.

### Descoberta local

```powershell
Set-Location "$env:USERPROFILE\Downloads\Urban-Mobility-Lab"
$python = ".\.venv\Scripts\python.exe"
& $python -m urban_mobility_lab.sumo_bridge doctor
```

Se `sumo_detected` for `false`, observe que o MSI 1.28.0 frequentemente instala em `C:\\Program Files\\sumo-1.28.0`, nao na pasta `Eclipse\\Sumo`. O laboratorio agora procura esses diretorios versionados e a variavel `SUMO_HOME` persistida no Windows.

Localize o SUMO com PowerShell sem varrer o disco inteiro:

```powershell
$roots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
Get-ChildItem -Path $roots -Directory -ErrorAction SilentlyContinue |
    Where-Object Name -like 'sumo*' |
    Select-Object FullName
```

Confirme a presenca de `bin\\netconvert.exe` e `tools\\osmGet.py` dentro do diretorio encontrado. Por exemplo, somente se existir:

```powershell
$env:SUMO_HOME = 'C:\\Program Files\\sumo-1.28.0'
& $python -m urban_mobility_lab.sumo_bridge doctor --sumo-home $env:SUMO_HOME
```

O MSI pode atualizar as variaveis de ambiente sem atualizar o PowerShell ja aberto; uma nova janela tambem ajuda. Nao e necessario reinstalar o SUMO.

## 2. Gerar plano (sem fazer download)

```powershell
& $python -m urban_mobility_lab.sumo_bridge plan
```

Salva `reports/parnaiba_sumo_import.json` e mostra bbox, hash e nomes dos quatro arquivos esperados. Anote os valores e cheque que a origem é a mesma. Não confundir bbox com limite legal da cidade.

## 3. Baixar OSM XML em partes (consulta externa explícita)

**Só depois** de confirmar versão do SUMO, estado do serviço Overpass e a bbox:

```powershell
& $python -m urban_mobility_lab.sumo_bridge download --confirm-download
```

O utilitário usa `osmGet.py --bbox oeste,sul,leste,norte --tiles 4` e tenta obter quatro arquivos independentes no diretório `data/raw/osm`. O download pode falhar por limites ou indisponibilidade do Overpass; respeite os limites de uso, não dispare requisições paralelas e não repita em loop. Se o download falhar, os arquivos parciais são preservados para inspeção. Nunca declarar sucesso com tiles vazias ou ausentes.

## 4. Converter com netconvert (sem gerar veículos)

```powershell
& $python -m urban_mobility_lab.sumo_bridge convert
& $python -m urban_mobility_lab.sumo_bridge inspect
```

Saídas:
- `data/sumo/parnaiba_full.net.xml` — topologia SUMO derivada dos arquivos OSM XML;
- `reports/parnaiba_sumo_import.json` — hashes e contagens estruturais;
- arquivos OSM XML brutos permanecem em `data/raw/osm/` e não são enviados ao GitHub.

O comando conserva apenas vias que permitem a classe SUMO `passenger` e interpreta faixas de conversão quando disponíveis no OSM. **Isso não reproduz nem valida automaticamente os tempos reais dos semáforos.** A escolha do filtro é uma primeira hipótese modelística (nesta etapa, não inclui toda a dinâmica de motos, ônibus, bicicletas e pedestres).

Para visualizar sem simular tráfego:

```powershell
& "$env:SUMO_HOME\bin\sumo-gui.exe" -n "data\sumo\parnaiba_full.net.xml"
```

A linha acima depende de SUMO_HOME estar apontando para a instalação correta. Abrir a rede não é equivalente a rodar uma simulação.

## Próximos checkpoints

1. Confirmar que `doctor` detectou corretamente as ferramentas e sua versão.
2. Verificar que o plano reproduz o SHA-256 e área de importação esperados.
3. Confirmar que todos os arquivos OSM XML são válidos e documentar a data de aquisição.
4. Converter, inspecionar os nós/arestas e analisar diferenças geográficas em relação ao GraphML.
5. Preparar demanda sintética com **3 níveis** e sementes fixas, preservando distinção entre simulação e observação de tráfego.
6. Verificar regras de circulação, semáforos e calibração de campo em MIRANTE-01 antes de qualquer alegação sobre fluxos reais.

Referências: https://eclipse.dev/sumo/docs/Networks/Import/OpenStreetMap.html e https://eclipse.dev/sumo/docs/Tools/Import/OSM.html

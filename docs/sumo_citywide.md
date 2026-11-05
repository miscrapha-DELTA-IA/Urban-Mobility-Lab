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

**Checkpoint em Windows 5.1, 2026-11-05:** instalação `C:\Program Files (x86)\SUMO`, `netconvert 1.28.0`, aprovada pelo `doctor`. A primeira consulta ampla ao Overpass retornou **HTTP 504 Gateway Timeout** e não gerou nenhum OSM XML; o erro não ocorreu na instalação nem no GraphML.

A versão revisada usa um procedimento **estritamente sequencial** e retoma downloads parciais:

- a caixa geográfica de estudo é dividida em **8 faixas de oeste a leste** (configurável com `--tiles 1..16`);
- cada consulta do `osmGet.py` recebe somente objetos com etiqueta OSM `highway` e seus nós/relações relevantes; não solicita lojas, prédios ou outros POIs;
- cada arquivo XML é verificado quanto à estrutura e presença de vias antes de ser promovido de diretório temporário para a coleção aprovada;
- o arquivo `data/raw/osm/parnaiba_full_8.download_manifest.json` registra os hashes SHA-256, limites geográficos e momento de download de **cada** faixa;
- em caso de HTTP 504 ou interrupção, as faixas anteriores são **preservadas**. Executar novamente o mesmo comando **posteriormente**, com a mesma configuração, retoma apenas os segmentos faltantes. Nenhuma faixa aprovada é sobrescrita;
- os arquivos são protegidos contra mistura de esquemas, alteração de SHA-256 e conversão com download incompleto.

Comando padrão, **uma única execução por tentativa**:

```powershell
& $python -m urban_mobility_lab.sumo_bridge plan
& $python -m urban_mobility_lab.sumo_bridge download --confirm-download
```

**Importante:** os 8 arquivos XML não são uma fotografia única e atômica do OSM. Cada download pode ter uma data diferente e o relatório deve explicitar essa limitação. Se a exigência futura for uma versão histórica uniforme, escolher um extrato regional datado (PBF) e recortá-lo localmente, em vez de consultar o Overpass para cada parte.

Em caso de outro HTTP 504: não execute em loop nem faça dezenas de requisições. Aguarde a recuperação do Overpass, verifique o manifesto local e só então retome. HTTP 429 indica limitação de requisições e deve ser respeitado. Uma alternativa com arquivo regional encontra-se em https://download.geofabrik.de/south-america/brazil.html ; não baixar o Brasil inteiro desnecessariamente.

O modo antigo de 4 faixas permanece acessível por `--tiles 4`, mas **não deve ser misturado** ao novo padrão de 8 faixas no mesmo experimento. O novo modo usa um manifesto próprio.

## 4. Converter com netconvert (sem gerar veículos)

```powershell
& $python -m urban_mobility_lab.sumo_bridge convert
& $python -m urban_mobility_lab.sumo_bridge inspect
```

Saídas:
- `data/sumo/parnaiba_full.net.xml` — topologia SUMO derivada dos arquivos OSM XML;
- `reports/parnaiba_sumo_import.json` — hashes e contagens estruturais;
- os 8 arquivos OSM XML brutos e o manifesto permanecem em `data/raw/osm/` e não são enviados ao GitHub.

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

### Correção de argumentos negativos (Windows, 2026-11-05)

A primeira tentativa falhou **antes de fazer requisições ao Overpass**. A longitude negativa foi fornecida como argumento separado (`--bbox -41.846...`) e o `argparse` respondeu `argument -b/--bbox: expected one argument`. A versão atual usa a forma `--bbox=-41.8464173,-3.1032097,-41.6627259,-2.8057393`, validada por testes offline. O erro não implica que a base OSM tenha sido baixada nem que a conversão tenha iniciado. Não foi preciso reinstalar o SUMO 1.28.0.

## Testes sem acesso à internet

O teste de descoberta de SUMO foi isolado do registro do Windows, PATH e instalações reais, pois a versão anterior falhava no computador com o programa instalado e passava no Linux CI. Os testes de retoma usam um importador OSM simulado localmente: forçam falha no segundo tile e confirmam que os tiles já válidos não são baixados novamente, que arquivos modificados são rejeitados e que o comando contém o filtro de vias. Esses testes **não certificam** a disponibilidade da API Overpass nem a fidelidade da geometria viária brasileira.

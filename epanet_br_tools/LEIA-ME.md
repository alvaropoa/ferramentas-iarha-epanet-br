# Ferramentas de demonstração — EPANET 2.2 Brasil

Sete ferramentas para o menu **Ferramentas** do EPANET 2.2 Brasil.
São scripts Python que usam só a biblioteca padrão (nada para `pip install`).

| # | Ferramenta | Lê | Altera o projeto? |
|---|---|---|---|
| 1 | Resumo da Rede — quantitativos, extensão por diâmetro e por rugosidade | `$INPFILE` | não |
| 2 | Verificador de Consistência — nó isolado, nó inexistente, comprimento/diâmetro inválido, rugosidade fora da faixa, cota zero, sem coordenada, nós sem caminho até reservatório | `$INPFILE` | não |
| 3 | Rugosidade em Lote — janela para definir/multiplicar rugosidade por faixa de diâmetro | `$INPFILE` | **sim** (gera `.bak`) |
| 4 | Pressões e Velocidades NBR 12218 — mín./máx. no período simulado contra limites | `$INPFILE` (simula) | não |
| 5 | Relatório de Diagnóstico IARHA — capa, síntese automática, mapa de pressões, gráficos, consistência e anexo, em A4 pronto para PDF | `$INPFILE` (simula) | não |
| 6 | Relatório de Análise da Rede (padrão IARHA-ATLAS) — topologia, pressões, hidráulica, demandas, distribuições em km de rede, balanço, reservação (K1), top 10, diagnóstico e 6 mapas temáticos (pressão, perda de carga, velocidade, demanda, elevação, diâmetro) | `$INPFILE` (simula) | não |
| 7 | Configurar o Relatório de Análise — janela para título, subtítulo, responsável, logo, cores, critérios, classes e cores de cada mapa, seções incluídas; prévia com a rede de demonstração | — | não |

As ferramentas 1, 2 e 4 abrem um relatório HTML no navegador.

## Como funciona o mecanismo

O menu de ferramentas segue o modelo de *Add-In Tools* criado pela UPV (Valência)
para o EPANET em espanhol, o mesmo do SWMM 5: cada ferramenta é um **programa externo**
registrado em *Ferramentas › Configurar ferramentas*. Ao chamar a ferramenta, o EPANET
grava o projeto atual em um INP temporário, troca as macros pelos caminhos reais e executa o programa. Com "Atualizar ao fechar" marcado, o EPANET
recarrega o INP depois que o programa termina — é assim que a ferramenta 3 devolve
as alterações.

> **O EPANET 2.2 Brasil só oferece `$PROJDIR`, `$INPFILE` e `$RPTFILE` — não existe
> `$OUTFILE`.** Por isso as ferramentas 4 e 5 recebem `$INPFILE` e simulam sozinhas com o
> `runepanet.exe` da pasta do próprio EPANET Br (mesmo motor `Epanet2.dll` da interface),
> procurado em `C:\Program Files (x86)\Epanet 2.2 Brasil`. Se não for encontrado, copie o
> `runepanet.exe` para a pasta das ferramentas.

## Instalação

1. Instale o Python 3 para Windows (python.org) — a instalação padrão já traz o `tkinter`.
2. Copie esta pasta para um caminho fixo, ex.: `C:\EPANET_Ferramentas\`.
3. No EPANET: *Ferramentas › Configurar ferramentas › Adicionar*, uma entrada por ferramenta:

| Campo | Valor |
|---|---|
| Programa | `C:\...\Python3xx\pythonw.exe` (sem janela preta; use `python.exe` para depurar) |
| Diretório de trabalho | `C:\EPANET_Ferramentas` |
| Parâmetros (1) | `"C:\EPANET_Ferramentas\01_resumo_rede.py" $INPFILE` |
| Parâmetros (2) | `"C:\EPANET_Ferramentas\02_verificar_consistencia.py" $INPFILE` |
| Parâmetros (3) | `"C:\EPANET_Ferramentas\03_rugosidade_lote.py" $INPFILE` + marcar **Atualizar o Epanet após finalizar o programa** |
| Parâmetros (4) | `"C:\EPANET_Ferramentas\04_pressoes_nbr12218.py" $INPFILE 10 40 0.4 3.5` |
| Parâmetros (5) | `"C:\EPANET_Ferramentas\05_relatorio_iarha.py" $INPFILE 10 40 0.4 3.5` |
| Parâmetros (6) | `"C:\EPANET_Ferramentas\06_relatorio_analise_rede.py" $INPFILE` (critérios vêm da configuração) |
| Parâmetros (7) | `"C:\EPANET_Ferramentas\07_configurar_relatorio.py"` (não precisa de $INPFILE) |

O campo **Programa** é sempre o `pythonw.exe`, nunca o `.py` (apontar para o `.py` faz o
Windows abrir o arquivo no editor associado, como o VS Code). O `.py` vai em **Parâmetros**.
Caminhos com espaço em `$INPFILE` funcionam com ou sem aspas.

**Se aparecer "I/O error 32" ao salvar a ferramenta:** o EPANET não conseguiu gravar a lista
de ferramentas (`%APPDATA%\EPANET\Epanet2Tools.ini`) porque outro programa está com o
arquivo aberto. Feche todas as janelas de EPANET (inclusive outras versões instaladas) e
qualquer editor com esse arquivo, abra só o EPANET 2.2 Brasil e cadastre de novo.

**Ferramenta 5:** o relatório abre no navegador; use o botão
"Imprimir / salvar PDF" (A4, com gráficos de fundo). Para usar o logo oficial, coloque
`logo_iarha.png` ou `logo_iarha.svg` nesta pasta — sem ele, o sol IARHA é desenhado em SVG.

**Ferramentas 6 e 7 — personalização:** a ferramenta 7 abre uma janela com abas Geral (título,
subtítulo, responsável técnico, logo, separador decimal), Critérios (pressões, velocidades, perda
de carga alta, K1), Cores (paleta do relatório), Mapas (limites e cores das classes de pressão,
perda de carga e velocidade; rampas de demanda, elevação e diâmetro; ligar/desligar cada mapa) e
Seções (quais partes entram). "Gerar prévia" mostra o resultado na rede de demonstração sem
salvar. As escolhas ficam em `config_relatorio.json`, nesta pasta. Marcando "Abrir esta janela
antes de cada relatório", a ferramenta 6 pergunta antes de gerar. Números escritos depois de
`$INPFILE` no cadastro da ferramenta 6 têm prioridade sobre os critérios salvos.

**Ferramenta 6:** usa as fontes da pasta `fontes/` (Bebas Neue e Fira Sans Condensed, licença OFL),
embutidas no HTML — mantenha essa pasta junto. Tudo é convertido para SI.

Nas ferramentas 4 a 6 os números opcionais são `PMIN PMAX VMIN VMAX` (mca e m/s).
A pressão máxima simulada é usada como
aproximação da estática — para a verificação estrita, simule o cenário de consumo mínimo.

## Roteiro de demonstração (5 min) com `rede_demo.inp`

1. Abrir `rede_demo.inp` → **Resumo da Rede**: 4,13 km, 17 L/s, extensão por DN.
2. **Verificador**: rede limpa. Mudar o comprimento de T4 para 0 e fechar T10 → rodar de novo:
   aparecem erro de comprimento e N10 sem abastecimento.
3. Desfazer → **Pressões NBR 12218**: N7 com 7,7 mca às 8:00; N9 com 58,3 mca à 1:00.
4. **Rugosidade em Lote**: DN 50–75, definir C = 100 → o EPANET recarrega a rede;
   rodar a ferramenta 4 de novo para mostrar o efeito.

## Testes realizados

Validado com o motor EPANET 2.2 (OWA): pressões batem com o solver em mca e kPa;
INP alterado preserva codificação cp1252/acentos, quebras de linha CRLF e comentários,
e volta a simular. A janela da ferramenta 3 (tkinter) não foi testada em Windows —
sem janela, ela aceita: `03_rugosidade_lote.py arquivo.inp definir|multiplicar VALOR [DMIN DMAX]`.

## Estrutura para criar novas ferramentas

`epanet_comum.py` traz `Inp` (lê/edita/grava o INP sem perder formatação),
`SaidaBinaria` (lê o .out por período) e `gravar_relatorio` (HTML com tema claro/escuro).
`simular(inp)` roda o `runepanet.exe` do EPANET Br e devolve o `.out`.
Uma nova ferramenta é um script que recebe `$INPFILE` em `sys.argv[1]`.

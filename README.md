# Ferramentas IARHA para o EPANET 2.2 Brasil

Sete ferramentas para o menu **Ferramentas** do [EPANET 2.2 Brasil](https://www.ct.ufpb.br/lenhs/downlodas/epanet/) (LENHS/UFPB). Com um clique, você obtém o resumo da rede, a verificação do cadastro, a alteração de rugosidade em lote, a checagem de pressões e velocidades pela NBR 12218 e dois relatórios técnicos com mapas, sem sair do programa.

Tudo parte do EPANET. As ferramentas usam o próprio motor de cálculo do EPANET 2.2 Brasil e só organizam os resultados em formatos prontos para análise e entrega.

![Relatório de Análise da Rede](docs/img/06_pagina1.png)

## As ferramentas

| # | Ferramenta | O que faz | Altera o projeto? |
| --- | --- | --- | --- |
| 1 | Resumo da Rede | Quantitativos, extensão por diâmetro e por rugosidade | Não |
| 2 | Verificador de Consistência | Aponta erros de cadastro antes de simular | Não |
| 3 | Rugosidade em Lote | Define ou multiplica a rugosidade por faixa de diâmetro | **Sim** |
| 4 | Pressões e Velocidades NBR 12218 | Nós e trechos fora dos limites no período simulado | Não |
| 5 | Relatório de Diagnóstico | Relatório A4 com capa, síntese, mapa de pressões e anexo | Não |
| 6 | Relatório de Análise da Rede | Indicadores, histogramas, reservação, Top 10, diagnóstico e 6 mapas temáticos | Não |
| 7 | Configurar Relatório | Janela para personalizar título, logo, cores, critérios, mapas e seções do relatório 6 | Não |

## Instalação rápida

Requisitos: Windows 10 ou 11, [EPANET 2.2 Brasil](https://www.ct.ufpb.br/lenhs/downlodas/epanet/) e [Python 3.10+](https://www.python.org/downloads/windows/) do python.org. Não é preciso instalar nenhum pacote Python extra.

1. Baixe este repositório (**Code › Download ZIP**) ou a versão mais recente em **Releases**.
2. Copie o conteúdo da pasta `epanet_br_tools` para `C:\EPANET_Ferramentas` (caminho curto, sem acentos, fora do OneDrive).
3. No PowerShell, descubra o caminho do Python com `where.exe pythonw`. Use o primeiro resultado, não o que estiver em `WindowsApps`.
4. No EPANET, cadastre cada ferramenta em **Ferramentas › Configurar Ferramentas › Adicionar**:

| Campo | Valor |
| --- | --- |
| Programa | o caminho do `pythonw.exe` |
| Pasta de Trabalho | `C:\EPANET_Ferramentas` |
| Parâmetros | o script entre aspas + `$INPFILE`, conforme a tabela abaixo |

| # | Parâmetros | Atualizar o Epanet após finalizar |
| --- | --- | --- |
| 1 | `"C:\EPANET_Ferramentas\01_resumo_rede.py" $INPFILE` | Não |
| 2 | `"C:\EPANET_Ferramentas\02_verificar_consistencia.py" $INPFILE` | Não |
| 3 | `"C:\EPANET_Ferramentas\03_rugosidade_lote.py" $INPFILE` | **Sim** |
| 4 | `"C:\EPANET_Ferramentas\04_pressoes_nbr12218.py" $INPFILE 10 40 0.4 3.5` | Não |
| 5 | `"C:\EPANET_Ferramentas\05_relatorio_iarha.py" $INPFILE 10 40 0.4 3.5` | Não |
| 6 | `"C:\EPANET_Ferramentas\06_relatorio_analise_rede.py" $INPFILE` | Não |
| 7 | `"C:\EPANET_Ferramentas\07_configurar_relatorio.py"` | Não |

A planilha `epanet_br_tools/Cadastro_Ferramentas_EPANET_Br.xlsx` monta essas linhas com os seus caminhos.

**A regra que evita quase todos os erros:** no campo Programa vai sempre o `pythonw.exe`; o arquivo `.py` vai em Parâmetros.

Para testar, abra `rede_demo.inp` no EPANET e rode o Resumo da Rede: deve abrir no navegador um relatório com 4,13 km de rede e 17 L/s de demanda.

## Documentação

O [manual completo](docs/MANUAL.md) explica cada ferramenta com figuras, a personalização do relatório, as premissas de cálculo, a solução de problemas e como criar suas próprias ferramentas.

## Problemas comuns

| O que acontece | Como resolver |
| --- | --- |
| Abre o VS Code ou o Bloco de Notas com o código | Programa = `pythonw.exe`; o `.py` vai em Parâmetros |
| Nada acontece | Confira o caminho do script e as aspas; troque `pythonw.exe` por `python.exe` para ver a mensagem de erro |
| "I/O error 32" ao salvar o cadastro | Feche todas as janelas de EPANET, inclusive de outras versões, e cadastre de novo |
| "Não encontrei o runepanet.exe" | Copie o `runepanet.exe` da pasta do EPANET Br para a pasta das ferramentas |

Encontrou outro problema ou tem uma sugestão? Abra uma **Issue** neste repositório.

## Créditos e licença

- **EPANET** — U.S. Environmental Protection Agency (USEPA), domínio público. **EPANET 2.2 Brasil** — [LENHS/UFPB](https://www.ct.ufpb.br/lenhs/downlodas/epanet/).
- **Fontes do relatório 6** — Bebas Neue (The Bebas Neue Project Authors) e Fira Sans Condensed (Mozilla Foundation e Telefonica S.A.), sob a SIL Open Font License 1.1.
- **Ferramentas IARHA** — Álvaro Prestes Ribeiro e LUGH Engenharia Ambiental e Sanitária, licença [MIT](LICENSE).

Os relatórios refletem o modelo e os dados de entrada. Calibração e validação de campo são responsabilidade do projetista.

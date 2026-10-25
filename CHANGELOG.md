# Histórico de versões

## 1.1.0 — 2026-10-25

- Nova ferramenta 8, **Imagem de Fundo**: baixa imagem de satélite, ruas, topográfico ou cinza claro
  (serviços de mapa da Esri) já no sistema de coordenadas da rede, grava em BMP e escreve a seção
  `[BACKDROP]` com as dimensões da imagem, para o fundo aparecer alinhado. Também remove o fundo.
- Exemplo do manual para criar ferramentas renomeado para `09_nos_sem_demanda.py`.

## 1.0.0 — 2026-10-25

Primeira versão pública.

- Sete ferramentas para o menu Ferramentas do EPANET 2.2 Brasil: Resumo da Rede, Verificador de
  Consistência, Rugosidade em Lote, Pressões e Velocidades NBR 12218, Relatório de Diagnóstico,
  Relatório de Análise da Rede (padrão IARHA-ATLAS, com 6 mapas temáticos) e Configurar Relatório.
- Simulação pelo `runepanet.exe` do próprio EPANET 2.2 Brasil (a versão brasileira não oferece `$OUTFILE`).
- Caminhos com espaço aceitos com ou sem aspas; parâmetros numéricos aceitam vírgula decimal e
  ignoram caracteres colados por engano.
- Unidades convertidas para SI nos relatórios.

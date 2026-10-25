# -*- coding: utf-8 -*-
"""
Ferramenta 7 — Configurar o Relatório de Análise da Rede
Uso (parâmetros no EPANET):  "<pasta>\\07_configurar_relatorio.py"
Abre a janela de personalização (título, logo, cores, critérios, classes dos mapas e
seções). As escolhas ficam em config_relatorio.json e valem para a ferramenta 6.
Não altera o projeto.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_relatorio import janela
from epanet_comum import avisar

if __name__ == "__main__":
    try:
        janela()
    except Exception as e:
        import traceback
        avisar("Configurar relatório — erro", "%s\n\n%s" % (e, traceback.format_exc()[-700:]), erro=True)

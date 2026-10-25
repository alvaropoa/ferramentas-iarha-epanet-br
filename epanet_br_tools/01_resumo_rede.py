# -*- coding: utf-8 -*-
"""
Ferramenta 1 — Resumo da Rede
Uso (parâmetros no EPANET):  "<pasta>\\01_resumo_rede.py" "$INPFILE"
Lê o projeto atual e abre um relatório HTML com quantitativos:
nós, trechos, extensão por diâmetro, demanda base total.
Não altera o projeto.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import Inp, arg_arquivo, gravar_relatorio, tabela_html, fmt, esc, avisar


def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    si = inp.unidades_si()
    u_comp, u_diam = ("m", "mm") if si else ("ft", "pol")
    u_vazao = (inp.opcao("UNITS", "GPM") or "").upper()

    juncoes = inp.tabela("JUNCTIONS")
    reservs = inp.tabela("RESERVOIRS")
    tanques = inp.tabela("TANKS")
    tubos = inp.tabela("PIPES")
    bombas = inp.tabela("PUMPS")
    valvulas = inp.tabela("VALVES")

    # demanda base: [JUNCTIONS] col 3 + [DEMANDS] (se houver, substitui)
    dem = {t[0]: float(t[2]) for t in juncoes if len(t) > 2}
    dem_sec = inp.tabela("DEMANDS")
    if dem_sec:
        acum = {}
        for t in dem_sec:
            acum[t[0]] = acum.get(t[0], 0.0) + float(t[1])
        dem.update(acum)
    dem_total = sum(dem.values())

    ext_total = 0.0
    por_diam = {}
    por_rug = {}
    for t in tubos:
        L, D, C = float(t[3]), float(t[4]), t[5]
        ext_total += L
        por_diam.setdefault(D, [0, 0.0]); por_diam[D][0] += 1; por_diam[D][1] += L
        por_rug[C] = por_rug.get(C, 0.0) + L

    cotas = [float(t[1]) for t in juncoes if len(t) > 1]

    kpi = lambda v, r: "<div class='kpi'><b>%s</b><span>%s</span></div>" % (v, esc(r))
    corpo = "<div class='kpis'>"
    corpo += kpi(len(juncoes), "nós de consumo")
    corpo += kpi(len(reservs) + len(tanques), "reservatórios (RNF + RNV)")
    corpo += kpi(len(tubos), "tubulações")
    corpo += kpi(len(bombas), "bombas")
    corpo += kpi(len(valvulas), "válvulas")
    corpo += kpi(fmt(ext_total / (1000 if si else 1), 2) + (" km" if si else " ft"), "extensão total")
    corpo += kpi(fmt(dem_total, 2) + " " + u_vazao, "demanda base total")
    if cotas:
        corpo += kpi("%s – %s" % (fmt(min(cotas), 1), fmt(max(cotas), 1)), "faixa de cotas (%s)" % u_comp)
    corpo += "</div>"

    corpo += "<h2>Extensão por diâmetro</h2>"
    maior = max([v[1] for v in por_diam.values()] or [1])
    linhas = []
    for D in sorted(por_diam):
        n, L = por_diam[D]
        barra = "<div class='bar' style='width:%.0f%%'></div>" % (100 * L / maior)
        linhas.append([fmt(D, 0 if si else 1), n, fmt(L, 1), fmt(100 * L / ext_total if ext_total else 0, 1) + " %", barra])
    corpo += tabela_html(["Diâmetro (%s)" % u_diam, "Trechos", "Extensão (%s)" % u_comp, "%", ""], linhas, (0, 1, 2, 3))

    corpo += "<h2>Extensão por coeficiente de rugosidade (%s)</h2>" % esc(inp.formula())
    linhas = [[esc(c), fmt(L, 1), fmt(100 * L / ext_total if ext_total else 0, 1) + " %"]
              for c, L in sorted(por_rug.items(), key=lambda x: -x[1])]
    corpo += tabela_html(["Rugosidade", "Extensão (%s)" % u_comp, "%"], linhas, (1, 2))

    gravar_relatorio("Resumo da Rede", os.path.basename(inp.caminho) +
                     " · unidades " + u_vazao + " · perda de carga " + inp.formula(),
                     corpo, "epanet_resumo_rede.html")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        avisar("Resumo da Rede — erro", str(e), erro=True)
